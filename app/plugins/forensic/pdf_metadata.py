"""
PDF Metadata Extractor Plugin.

Extracts metadata from PDF files including author, creation date,
modification history, and XMP metadata.
"""
import os
from datetime import datetime
from typing import Dict, Any
import pluggy

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

hookimpl = pluggy.HookimplMarker("casemanager")


class PDFMetadataPlugin:
    """Plugin for extracting metadata from PDF files."""

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'pdf_metadata',
            'display_name': 'Extractor Metadatos PDF',
            'description': 'Extrae metadatos de archivos PDF incluyendo autor, fechas y historial de edición',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'forensic',
            'type': 'metadata_extractor',
            'supported_formats': ['.pdf'],
            'available': PYPDF2_AVAILABLE
        }

    @hookimpl
    def analyze_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Extract metadata from a PDF file.

        Args:
            file_path: Path to the PDF file
            **kwargs: Additional arguments

        Returns:
            dict: Extracted PDF metadata
        """
        if not PYPDF2_AVAILABLE:
            return {
                'success': False,
                'error': 'PyPDF2 library not installed'
            }

        # Check file extension
        _, ext = os.path.splitext(file_path)
        if ext.lower() != '.pdf':
            return {
                'success': False,
                'error': f'Not a PDF file: {ext}'
            }

        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PdfReader(f)

                # Get basic info
                num_pages = len(pdf_reader.pages)

                # Get metadata
                metadata = pdf_reader.metadata

                # Parse metadata
                parsed_metadata = {}
                if metadata:
                    parsed_metadata = self._parse_metadata(metadata)

                # Get XMP metadata if available
                xmp_metadata = None
                if hasattr(pdf_reader, 'xmp_metadata') and pdf_reader.xmp_metadata:
                    xmp_metadata = self._parse_xmp_metadata(pdf_reader.xmp_metadata)

                # Analyze document info
                doc_info = {
                    'num_pages': num_pages,
                    'is_encrypted': pdf_reader.is_encrypted
                }

                # Try to get text from first page for analysis
                text_sample = None
                if num_pages > 0:
                    try:
                        first_page = pdf_reader.pages[0]
                        text_sample = first_page.extract_text()[:500]  # First 500 chars
                    except Exception:
                        pass

                return {
                    'success': True,
                    'file_path': file_path,
                    'document_info': doc_info,
                    'metadata': parsed_metadata,
                    'xmp_metadata': xmp_metadata,
                    'text_sample': text_sample,
                    'author_info': self._extract_author_info(parsed_metadata),
                    'date_info': self._extract_date_info(parsed_metadata),
                    'software_info': self._extract_software_info(parsed_metadata)
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Error extracting PDF metadata: {str(e)}'
            }

    def _parse_metadata(self, metadata) -> Dict[str, Any]:
        """
        Parse PDF metadata object.

        Args:
            metadata: PyPDF2 metadata object

        Returns:
            dict: Parsed metadata
        """
        parsed = {}

        # Standard PDF metadata fields
        fields = [
            'title', 'author', 'subject', 'creator', 'producer',
            'creation_date', 'mod_date', 'trapped', 'keywords'
        ]

        for field in fields:
            attr_name = f'/{field.title()}'
            if hasattr(metadata, attr_name.lower().replace('/', '')):
                value = getattr(metadata, attr_name.lower().replace('/', ''))
                if value:
                    parsed[field] = value

        # Also get any custom fields
        if hasattr(metadata, '__dict__'):
            for key, value in metadata.__dict__.items():
                if key.startswith('/') and key[1:].lower() not in [f.lower() for f in fields]:
                    parsed[key[1:]] = value

        return parsed

    def _parse_xmp_metadata(self, xmp_metadata) -> Dict[str, Any]:
        """
        Parse XMP metadata.

        Args:
            xmp_metadata: XMP metadata object

        Returns:
            dict: Parsed XMP metadata
        """
        try:
            xmp_dict = {}

            # Common XMP fields
            if hasattr(xmp_metadata, 'dc_creator'):
                xmp_dict['creator'] = xmp_metadata.dc_creator
            if hasattr(xmp_metadata, 'dc_title'):
                xmp_dict['title'] = xmp_metadata.dc_title
            if hasattr(xmp_metadata, 'dc_description'):
                xmp_dict['description'] = xmp_metadata.dc_description
            if hasattr(xmp_metadata, 'xmp_create_date'):
                xmp_dict['create_date'] = str(xmp_metadata.xmp_create_date)
            if hasattr(xmp_metadata, 'xmp_modify_date'):
                xmp_dict['modify_date'] = str(xmp_metadata.xmp_modify_date)
            if hasattr(xmp_metadata, 'xmp_metadata_date'):
                xmp_dict['metadata_date'] = str(xmp_metadata.xmp_metadata_date)
            if hasattr(xmp_metadata, 'xmp_creator_tool'):
                xmp_dict['creator_tool'] = xmp_metadata.xmp_creator_tool
            if hasattr(xmp_metadata, 'pdf_producer'):
                xmp_dict['producer'] = xmp_metadata.pdf_producer

            return xmp_dict if xmp_dict else None

        except Exception:
            return None

    def _extract_author_info(self, metadata: dict) -> Dict[str, Any]:
        """
        Extract author-related information.

        Args:
            metadata: Parsed metadata

        Returns:
            dict: Author information
        """
        return {
            'author': metadata.get('author'),
            'creator': metadata.get('creator'),
            'company': metadata.get('company'),
            'manager': metadata.get('manager')
        }

    def _extract_date_info(self, metadata: dict) -> Dict[str, Any]:
        """
        Extract date-related information.

        Args:
            metadata: Parsed metadata

        Returns:
            dict: Date information
        """
        date_info = {
            'creation_date': metadata.get('creation_date'),
            'modification_date': metadata.get('mod_date')
        }

        # Try to parse PDF date format (D:YYYYMMDDHHmmSS)
        for key in ['creation_date', 'modification_date']:
            if date_info[key]:
                parsed_date = self._parse_pdf_date(str(date_info[key]))
                if parsed_date:
                    date_info[f'{key}_parsed'] = parsed_date

        return date_info

    def _parse_pdf_date(self, pdf_date: str) -> str:
        """
        Parse PDF date format to ISO format.

        Args:
            pdf_date: PDF date string (D:YYYYMMDDHHmmSS)

        Returns:
            str: ISO format date or None
        """
        try:
            # Remove 'D:' prefix if present
            if pdf_date.startswith('D:'):
                pdf_date = pdf_date[2:]

            # Basic format: YYYYMMDDHHmmSS
            if len(pdf_date) >= 14:
                dt = datetime.strptime(pdf_date[:14], '%Y%m%d%H%M%S')
                return dt.isoformat()
        except Exception:
            pass
        return None

    def _extract_software_info(self, metadata: dict) -> Dict[str, Any]:
        """
        Extract software-related information.

        Args:
            metadata: Parsed metadata

        Returns:
            dict: Software information
        """
        return {
            'creator': metadata.get('creator'),
            'producer': metadata.get('producer'),
            'creator_tool': metadata.get('CreatorTool')
        }

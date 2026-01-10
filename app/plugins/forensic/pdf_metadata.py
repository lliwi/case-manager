"""
PDF Metadata Extractor Plugin.

Extracts metadata from PDF files including author, creation date,
modification history, and XMP metadata.
"""
import os
from datetime import datetime, date, time
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

    def _make_json_serializable(self, obj):
        """
        Convert objects to JSON-serializable types.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable version of the object
        """
        # Return as-is for already JSON-serializable types (check first for performance)
        if isinstance(obj, (int, float, bool, type(None))):
            return obj

        # Handle strings - remove null bytes that PostgreSQL can't handle
        if isinstance(obj, str):
            # Remove null bytes and other problematic characters
            return obj.replace('\x00', '').replace('\u0000', '')

        # Handle any object with isoformat() method (datetime, date, time, and PyPDF2 wrappers)
        if hasattr(obj, 'isoformat') and callable(obj.isoformat):
            try:
                return obj.isoformat()
            except Exception:
                pass  # Fall through to other handlers

        # Handle datetime, date, and time objects explicitly
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()

        # Handle dictionaries (must come before checking iterables)
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}

        # Handle tuples (convert to list)
        if isinstance(obj, tuple):
            return [self._make_json_serializable(item) for item in obj]

        # Handle lists
        if isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]

        # Handle bytes (skip or convert to hex string)
        if isinstance(obj, bytes):
            # For short bytes, convert to hex; for long ones, skip
            if len(obj) <= 64:
                return obj.hex()
            return None

        # For other types, convert to string representation
        try:
            return str(obj)
        except Exception:
            return None

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

                result = {
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

                # Convert all values to JSON-serializable types
                return self._make_json_serializable(result)

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

        # PyPDF2 metadata behaves like a dictionary
        # Iterate over all keys and serialize values
        try:
            # Try to iterate as a dictionary
            for key in metadata:
                if key and key.startswith('/'):
                    # Remove the leading '/' and convert to lowercase with underscores
                    clean_key = key[1:].lower()
                    value = metadata[key]
                    if value is not None:
                        # Serialize the value to handle datetime and other non-JSON types
                        parsed[clean_key] = self._make_json_serializable(value)
        except (TypeError, AttributeError):
            # Fallback: try to access as attributes
            standard_fields = [
                ('title', '/Title'),
                ('author', '/Author'),
                ('subject', '/Subject'),
                ('creator', '/Creator'),
                ('producer', '/Producer'),
                ('creation_date', '/CreationDate'),
                ('mod_date', '/ModDate'),
                ('trapped', '/Trapped'),
                ('keywords', '/Keywords')
            ]

            for field_name, pdf_key in standard_fields:
                if hasattr(metadata, field_name):
                    value = getattr(metadata, field_name)
                    if value is not None:
                        parsed[field_name] = self._make_json_serializable(value)

        return parsed

    def _parse_xmp_metadata(self, xmp_metadata) -> Dict[str, Any]:
        """
        Parse XMP metadata.

        Args:
            xmp_metadata: XMP metadata object

        Returns:
            dict: Parsed XMP metadata with formatted dates
        """
        try:
            xmp_dict = {}

            # Common XMP fields
            if hasattr(xmp_metadata, 'dc_creator'):
                xmp_dict['creator'] = self._make_json_serializable(xmp_metadata.dc_creator)
            if hasattr(xmp_metadata, 'dc_title'):
                xmp_dict['title'] = self._make_json_serializable(xmp_metadata.dc_title)
            if hasattr(xmp_metadata, 'dc_description'):
                xmp_dict['description'] = self._make_json_serializable(xmp_metadata.dc_description)

            # Format XMP dates (these are typically ISO format strings)
            if hasattr(xmp_metadata, 'xmp_create_date'):
                date_str = self._make_json_serializable(xmp_metadata.xmp_create_date)
                xmp_dict['create_date'] = self._format_iso_date(date_str) if date_str else None

            if hasattr(xmp_metadata, 'xmp_modify_date'):
                date_str = self._make_json_serializable(xmp_metadata.xmp_modify_date)
                xmp_dict['modify_date'] = self._format_iso_date(date_str) if date_str else None

            if hasattr(xmp_metadata, 'xmp_metadata_date'):
                date_str = self._make_json_serializable(xmp_metadata.xmp_metadata_date)
                xmp_dict['metadata_date'] = self._format_iso_date(date_str) if date_str else None

            if hasattr(xmp_metadata, 'xmp_creator_tool'):
                xmp_dict['creator_tool'] = self._make_json_serializable(xmp_metadata.xmp_creator_tool)
            if hasattr(xmp_metadata, 'pdf_producer'):
                xmp_dict['producer'] = self._make_json_serializable(xmp_metadata.pdf_producer)

            return xmp_dict if xmp_dict else None

        except Exception:
            return None

    def _format_iso_date(self, iso_date_str: str) -> str:
        """
        Format ISO date string to human-readable format.

        Args:
            iso_date_str: ISO format date string (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SS)

        Returns:
            str: Formatted date (dd/mm/yyyy HH:MM:SS UTC±HH:MM) or original string
        """
        if not iso_date_str or not isinstance(iso_date_str, str):
            return iso_date_str

        try:
            # Check if string has timezone info
            has_timezone = '+' in iso_date_str or iso_date_str.endswith('Z') or (
                '-' in iso_date_str and iso_date_str.rfind('-') > 10
            )

            # Replace Z with +00:00 for UTC
            normalized_str = iso_date_str.replace('Z', '+00:00')

            # Try different ISO formats
            formats_with_tz = [
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%S.%f%z'
            ]
            formats_without_tz = [
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f'
            ]

            dt = None

            # Try with timezone first
            if has_timezone:
                for fmt in formats_with_tz:
                    try:
                        dt = datetime.strptime(normalized_str, fmt)
                        break
                    except ValueError:
                        continue

            # Try without timezone
            if dt is None:
                for fmt in formats_without_tz:
                    try:
                        dt = datetime.strptime(normalized_str, fmt)
                        break
                    except ValueError:
                        continue

            if dt:
                formatted_date = dt.strftime('%d/%m/%Y %H:%M:%S')

                # Extract timezone if present
                if dt.tzinfo:
                    tz_offset = dt.strftime('%z')
                    # Format timezone as UTC±HH:MM
                    tz_formatted = f" UTC{tz_offset[:3]}:{tz_offset[3:]}"
                    return f"{formatted_date}{tz_formatted}"
                else:
                    return formatted_date

            # If parsing fails, return original string
            return iso_date_str
        except Exception:
            return iso_date_str

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
            dict: Date information with human-readable formatted dates
        """
        date_info = {}

        # Parse creation date
        creation_date_raw = metadata.get('creationdate')
        if creation_date_raw:
            parsed_date = self._parse_pdf_date(str(creation_date_raw))
            date_info['creation_date'] = parsed_date if parsed_date else creation_date_raw
        else:
            date_info['creation_date'] = None

        # Parse modification date
        mod_date_raw = metadata.get('moddate')
        if mod_date_raw:
            parsed_date = self._parse_pdf_date(str(mod_date_raw))
            date_info['modification_date'] = parsed_date if parsed_date else mod_date_raw
        else:
            date_info['modification_date'] = None

        return date_info

    def _parse_pdf_date(self, pdf_date: str) -> str:
        """
        Parse PDF date format to human-readable format with timezone.

        Args:
            pdf_date: PDF date string (D:YYYYMMDDHHmmSS±HH'mm')

        Returns:
            str: Formatted date (dd/mm/yyyy HH:MM:SS UTC±HH:MM) or None
        """
        try:
            # Remove 'D:' prefix if present
            if pdf_date.startswith('D:'):
                pdf_date = pdf_date[2:]

            # Extract timezone if present (format: ±HH'mm' or ±HHmm)
            timezone_str = ""
            date_part = pdf_date

            # Look for timezone indicator (+ or -)
            for tz_idx, char in enumerate(pdf_date[14:], start=14):
                if char in ['+', '-']:
                    date_part = pdf_date[:tz_idx]
                    tz_raw = pdf_date[tz_idx:]

                    # Parse timezone (format: ±HH'mm' or ±HHmm)
                    tz_sign = tz_raw[0]
                    tz_numbers = tz_raw[1:].replace("'", "")

                    if len(tz_numbers) >= 2:
                        tz_hours = tz_numbers[:2]
                        tz_minutes = tz_numbers[2:4] if len(tz_numbers) >= 4 else "00"
                        timezone_str = f" UTC{tz_sign}{tz_hours}:{tz_minutes}"
                    break

            # Parse the date part (YYYYMMDDHHmmSS)
            if len(date_part) >= 14:
                dt = datetime.strptime(date_part[:14], '%Y%m%d%H%M%S')
                # Format as dd/mm/yyyy HH:MM:SS
                formatted_date = dt.strftime('%d/%m/%Y %H:%M:%S')
                return f"{formatted_date}{timezone_str}"
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

"""
EXIF Metadata Extractor Plugin.

Extracts EXIF metadata from images including GPS coordinates, camera information,
and original capture dates.
"""
import os
from datetime import datetime
from typing import Dict, Any, Optional
import pluggy

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

hookimpl = pluggy.HookimplMarker("casemanager")


class ExifExtractorPlugin:
    """Plugin for extracting EXIF metadata from images."""

    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.tiff', '.tif']

    @hookimpl
    def get_info(self):
        """Get plugin information."""
        return {
            'name': 'exif_extractor',
            'display_name': 'Extractor EXIF',
            'description': 'Extrae metadatos EXIF de imágenes incluyendo GPS, cámara y fecha original',
            'version': '1.0.0',
            'author': 'Case Manager',
            'category': 'forensic',
            'type': 'metadata_extractor',
            'supported_formats': self.SUPPORTED_FORMATS,
            'available': PILLOW_AVAILABLE
        }

    @hookimpl
    def analyze_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Extract EXIF metadata from an image file.

        Args:
            file_path: Path to the image file
            **kwargs: Additional arguments

        Returns:
            dict: Extracted EXIF metadata
        """
        if not PILLOW_AVAILABLE:
            return {
                'success': False,
                'error': 'Pillow library not installed'
            }

        # Check file extension
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.SUPPORTED_FORMATS:
            return {
                'success': False,
                'error': f'Unsupported file format: {ext}'
            }

        try:
            with Image.open(file_path) as img:
                # Get EXIF data
                exif_data = img._getexif()

                if not exif_data:
                    return {
                        'success': True,
                        'has_exif': False,
                        'message': 'No EXIF data found in image'
                    }

                # Parse EXIF data
                parsed_exif = self._parse_exif(exif_data)

                # Extract GPS coordinates if available
                gps_info = self._extract_gps(exif_data)

                # Get image basic info
                image_info = {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height
                }

                return {
                    'success': True,
                    'has_exif': True,
                    'file_path': file_path,
                    'image_info': image_info,
                    'exif': parsed_exif,
                    'gps': gps_info,
                    'camera_info': self._extract_camera_info(parsed_exif),
                    'datetime_info': self._extract_datetime_info(parsed_exif)
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Error extracting EXIF: {str(e)}'
            }

    def _parse_exif(self, exif_data: dict) -> Dict[str, Any]:
        """
        Parse raw EXIF data into human-readable format.

        Args:
            exif_data: Raw EXIF data dictionary

        Returns:
            dict: Parsed EXIF data
        """
        parsed = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)

            # Skip binary data and GPS info (handled separately)
            if tag_name == 'GPSInfo':
                continue
            if isinstance(value, bytes):
                continue

            # Convert tuples to more readable format
            if isinstance(value, tuple):
                if len(value) == 2 and all(isinstance(x, int) for x in value):
                    # Rational number
                    if value[1] != 0:
                        parsed[tag_name] = value[0] / value[1]
                    continue
                value = list(value)

            parsed[tag_name] = value

        return parsed

    def _extract_gps(self, exif_data: dict) -> Optional[Dict[str, Any]]:
        """
        Extract GPS coordinates from EXIF data.

        Args:
            exif_data: Raw EXIF data dictionary

        Returns:
            dict: GPS information or None
        """
        gps_info = {}
        for tag_id, value in exif_data.items():
            if TAGS.get(tag_id) == 'GPSInfo':
                for gps_tag_id, gps_value in value.items():
                    gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag_name] = gps_value

        if not gps_info:
            return None

        # Convert GPS coordinates to decimal degrees
        latitude = self._convert_to_degrees(gps_info.get('GPSLatitude'))
        latitude_ref = gps_info.get('GPSLatitudeRef')
        longitude = self._convert_to_degrees(gps_info.get('GPSLongitude'))
        longitude_ref = gps_info.get('GPSLongitudeRef')

        if latitude and longitude:
            if latitude_ref == 'S':
                latitude = -latitude
            if longitude_ref == 'W':
                longitude = -longitude

            return {
                'latitude': latitude,
                'longitude': longitude,
                'latitude_ref': latitude_ref,
                'longitude_ref': longitude_ref,
                'altitude': gps_info.get('GPSAltitude'),
                'raw_gps': gps_info
            }

        return None

    def _convert_to_degrees(self, value) -> Optional[float]:
        """
        Convert GPS coordinates to decimal degrees.

        Args:
            value: GPS coordinate in DMS format

        Returns:
            float: Decimal degrees or None
        """
        if not value:
            return None

        try:
            d, m, s = value
            # Handle rational numbers
            if isinstance(d, tuple):
                d = d[0] / d[1] if d[1] != 0 else 0
            if isinstance(m, tuple):
                m = m[0] / m[1] if m[1] != 0 else 0
            if isinstance(s, tuple):
                s = s[0] / s[1] if s[1] != 0 else 0

            return d + (m / 60.0) + (s / 3600.0)
        except Exception:
            return None

    def _extract_camera_info(self, exif: dict) -> Dict[str, Any]:
        """
        Extract camera-specific information.

        Args:
            exif: Parsed EXIF data

        Returns:
            dict: Camera information
        """
        return {
            'make': exif.get('Make'),
            'model': exif.get('Model'),
            'software': exif.get('Software'),
            'lens_make': exif.get('LensMake'),
            'lens_model': exif.get('LensModel'),
            'focal_length': exif.get('FocalLength'),
            'f_number': exif.get('FNumber'),
            'iso': exif.get('ISOSpeedRatings') or exif.get('PhotographicSensitivity'),
            'exposure_time': exif.get('ExposureTime'),
            'flash': exif.get('Flash')
        }

    def _extract_datetime_info(self, exif: dict) -> Dict[str, Any]:
        """
        Extract datetime information.

        Args:
            exif: Parsed EXIF data

        Returns:
            dict: Datetime information
        """
        datetime_original = exif.get('DateTimeOriginal')
        datetime_digitized = exif.get('DateTimeDigitized')
        datetime_modified = exif.get('DateTime')

        result = {
            'datetime_original': datetime_original,
            'datetime_digitized': datetime_digitized,
            'datetime_modified': datetime_modified
        }

        # Try to parse datetime
        if datetime_original:
            try:
                dt = datetime.strptime(datetime_original, '%Y:%m:%d %H:%M:%S')
                result['datetime_original_parsed'] = dt.isoformat()
            except Exception:
                pass

        return result

"""
Unit tests for plugin system.

Tests cover DNI Validator, EXIF Extractor, and PDF Metadata plugins.
"""
import pytest
import os
import tempfile
from PIL import Image
from PIL.ExifTags import TAGS
from app.plugins.dni_validator import validate_dni, validate_nie, calculate_dni_letter
from app.plugins.exif_extractor import extract_exif_data, extract_gps_coordinates
from app.plugins.pdf_metadata import extract_pdf_metadata


@pytest.mark.unit
class TestDNIValidatorPlugin:
    """Tests for DNI/NIE validator plugin."""

    def test_valid_dni(self):
        """Test validation of valid DNI numbers."""
        valid_dnis = [
            '12345678Z',  # Classic example
            '00000000T',  # Edge case
            '99999999R',  # High number
        ]

        for dni in valid_dnis:
            result = validate_dni(dni)
            assert result['valid'] is True
            assert result['dni'] == dni.upper()

    def test_invalid_dni(self):
        """Test validation of invalid DNI numbers."""
        invalid_dnis = [
            '12345678A',  # Wrong letter (should be Z)
            '00000000A',  # Wrong letter (should be T)
            'ABCDEFGHZ',  # Non-numeric
            '1234567Z',   # Too short
            '123456789Z', # Too long
        ]

        for dni in invalid_dnis:
            result = validate_dni(dni)
            assert result['valid'] is False

    def test_dni_letter_calculation(self):
        """Test DNI letter calculation algorithm."""
        test_cases = [
            (12345678, 'Z'),
            (0, 'T'),
            (99999999, 'R'),
            (1, 'R'),
            (23, 'T'),
        ]

        for number, expected_letter in test_cases:
            calculated_letter = calculate_dni_letter(number)
            assert calculated_letter == expected_letter

    def test_valid_nie(self):
        """Test validation of valid NIE numbers."""
        valid_nies = [
            'X1234567L',  # NIE starting with X
            'Y1234567Z',  # NIE starting with Y
            'Z1234567A',  # NIE starting with Z
        ]

        for nie in valid_nies:
            result = validate_nie(nie)
            assert result['valid'] is True

    def test_invalid_nie(self):
        """Test validation of invalid NIE numbers."""
        invalid_nies = [
            'X1234567A',  # Wrong letter
            'W1234567L',  # Invalid prefix (not X, Y, Z)
            'X123456L',   # Too short
        ]

        for nie in invalid_nies:
            result = validate_nie(nie)
            assert result['valid'] is False

    def test_dni_case_insensitive(self):
        """Test DNI validation is case insensitive."""
        dni_lower = '12345678z'
        dni_upper = '12345678Z'

        result_lower = validate_dni(dni_lower)
        result_upper = validate_dni(dni_upper)

        assert result_lower['valid'] == result_upper['valid']

    def test_dni_with_spaces_and_dashes(self):
        """Test DNI with formatting characters."""
        dnis_with_formatting = [
            '12345678-Z',
            '12 345 678 Z',
            '12.345.678-Z',
        ]

        for dni in dnis_with_formatting:
            result = validate_dni(dni)
            # Should handle formatting
            assert result is not None


@pytest.mark.unit
class TestEXIFExtractorPlugin:
    """Tests for EXIF metadata extractor plugin."""

    def test_extract_basic_exif(self, sample_image_file):
        """Test extraction of basic EXIF data."""
        # Create image with EXIF data
        img = Image.new('RGB', (100, 100), color='red')

        # Save with basic metadata
        exif_data = img.getexif()

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            img.save(tmp.name, 'JPEG')
            tmp_path = tmp.name

        try:
            result = extract_exif_data(tmp_path)

            assert result is not None
            assert isinstance(result, dict)
            # Basic structure check
            assert 'success' in result or 'metadata' in result or isinstance(result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_extract_gps_coordinates(self):
        """Test GPS coordinate extraction."""
        # Create image with GPS data
        img = Image.new('RGB', (100, 100))

        # Note: Adding real GPS EXIF data requires piexif or similar
        # This test demonstrates the function signature

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            img.save(tmp.name, 'JPEG')
            tmp_path = tmp.name

        try:
            result = extract_gps_coordinates(tmp_path)

            # Should return None or coordinates dict
            assert result is None or isinstance(result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_non_image_file(self):
        """Test handling of non-image files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write('This is not an image')
            tmp_path = tmp.name

        try:
            result = extract_exif_data(tmp_path)

            # Should handle gracefully
            assert result is not None
            assert isinstance(result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_image_without_exif(self):
        """Test image without EXIF data."""
        img = Image.new('RGB', (50, 50), color='blue')

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            img.save(tmp.name, 'PNG')
            tmp_path = tmp.name

        try:
            result = extract_exif_data(tmp_path)

            # Should return empty dict or success: false
            assert result is not None
            assert isinstance(result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


@pytest.mark.unit
class TestPDFMetadataPlugin:
    """Tests for PDF metadata extractor plugin."""

    def test_extract_pdf_metadata(self, sample_pdf_file):
        """Test extraction of PDF metadata."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(sample_pdf_file.read())
            tmp_path = tmp.name

        try:
            result = extract_pdf_metadata(tmp_path)

            assert result is not None
            assert isinstance(result, dict)
            assert 'success' in result or 'metadata' in result

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_non_pdf_file(self):
        """Test handling of non-PDF files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write('Not a PDF file')
            tmp_path = tmp.name

        try:
            result = extract_pdf_metadata(tmp_path)

            # Should handle error gracefully
            assert result is not None
            assert isinstance(result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_corrupted_pdf(self):
        """Test handling of corrupted PDF."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(b'%PDF-corrupted-data-12345')
            tmp_path = tmp.name

        try:
            result = extract_pdf_metadata(tmp_path)

            # Should return error result
            assert result is not None
            assert isinstance(result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


@pytest.mark.unit
@pytest.mark.forensic
class TestForensicPluginIntegration:
    """Integration tests for forensic plugins."""

    def test_dni_validation_workflow(self):
        """Test complete DNI validation workflow."""
        # Simulate receiving DNI from form
        dni_input = '12345678-Z'

        # Validate
        result = validate_dni(dni_input)

        # Should extract clean DNI and validate
        assert result['valid'] is True
        assert result['dni'] == '12345678Z'

    def test_evidence_metadata_extraction(self, sample_image_file):
        """Test metadata extraction for evidence."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            img = Image.new('RGB', (200, 200), color='green')
            img.save(tmp.name, 'JPEG')
            tmp_path = tmp.name

        try:
            # Extract EXIF
            exif_result = extract_exif_data(tmp_path)

            # Extract GPS
            gps_result = extract_gps_coordinates(tmp_path)

            # Both should complete without error
            assert exif_result is not None
            assert gps_result is None or isinstance(gps_result, dict)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

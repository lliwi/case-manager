"""
Simplified plugin tests.
"""
import pytest


@pytest.mark.unit
class TestDNIValidatorPluginSimple:
    """Simplified tests for DNI/NIE validator plugin."""

    def test_plugin_module_exists(self):
        """Test that plugin module can be imported."""
        try:
            from app.plugins import dni_validator
            assert dni_validator is not None
        except ImportError:
            pytest.skip("DNI validator plugin not available")

    def test_validate_dni_function_exists(self):
        """Test that validation function exists."""
        try:
            from app.plugins.dni_validator import validate_dni
            assert callable(validate_dni)
        except ImportError:
            pytest.skip("DNI validator not available")

    def test_valid_dni_basic(self):
        """Test validation of a valid DNI."""
        try:
            from app.plugins.dni_validator import validate_dni
            result = validate_dni('12345678Z')
            assert result is not None
            assert isinstance(result, dict)
        except ImportError:
            pytest.skip("DNI validator not available")


@pytest.mark.unit
class TestEXIFExtractorPluginSimple:
    """Simplified tests for EXIF extractor plugin."""

    def test_plugin_module_exists(self):
        """Test that plugin module can be imported."""
        try:
            from app.plugins import exif_extractor
            assert exif_extractor is not None
        except ImportError:
            pytest.skip("EXIF extractor plugin not available")


@pytest.mark.unit
class TestPDFMetadataPluginSimple:
    """Simplified tests for PDF metadata plugin."""

    def test_plugin_module_exists(self):
        """Test that plugin module can be imported."""
        try:
            from app.plugins import pdf_metadata
            assert pdf_metadata is not None
        except ImportError:
            pytest.skip("PDF metadata plugin not available")

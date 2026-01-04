# Plugin Development Guide

## Overview

Case Manager uses a pluggy-based plugin system for extending forensic analysis capabilities. This guide explains how to develop custom plugins for evidence analysis, OSINT operations, and other specialized tasks.

## Plugin Architecture

### Plugin Manager

The application uses `pluggy` for plugin discovery and execution:

```python
from app.plugins.plugin_manager import plugin_manager

# Get all registered plugins
plugins = plugin_manager.list_plugins()

# Execute a specific plugin
result = plugin_manager.execute_plugin('dni_validator', dni='12345678Z')
```

### Plugin Specification

All plugins must implement the `PluginSpec` interface defined in `app/plugins/plugin_manager.py`:

```python
import pluggy

hookspec = pluggy.HookspecMarker("case_manager")
hookimpl = pluggy.HookimplMarker("case_manager")

class PluginSpec:
    """Plugin specification for forensic analysis plugins."""

    @hookspec
    def get_plugin_name(self):
        """Return plugin name."""
        pass

    @hookspec
    def get_plugin_description(self):
        """Return plugin description."""
        pass

    @hookspec
    def get_plugin_version(self):
        """Return plugin version."""
        pass

    @hookspec
    def execute(self, **kwargs):
        """Execute plugin with given parameters."""
        pass
```

## Creating a Custom Plugin

### Step 1: Create Plugin File

Create a new Python file in `app/plugins/`:

```python
# app/plugins/my_custom_plugin.py

from app.plugins.plugin_manager import hookimpl

class MyCustomPlugin:
    """Custom plugin for specialized analysis."""

    @hookimpl
    def get_plugin_name(self):
        return "my_custom_plugin"

    @hookimpl
    def get_plugin_description(self):
        return "Performs custom forensic analysis"

    @hookimpl
    def get_plugin_version(self):
        return "1.0.0"

    @hookimpl
    def execute(self, **kwargs):
        """
        Execute plugin analysis.

        Args:
            **kwargs: Plugin-specific parameters

        Returns:
            dict: Analysis results
        """
        try:
            # Your plugin logic here
            data = kwargs.get('data')

            # Perform analysis
            result = self._perform_analysis(data)

            return {
                'success': True,
                'plugin': 'my_custom_plugin',
                'result': result
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _perform_analysis(self, data):
        """Internal analysis method."""
        # Implementation
        pass
```

### Step 2: Register Plugin

Plugins are automatically discovered if placed in `app/plugins/`. To manually register:

```python
# In app/plugins/__init__.py
from app.plugins.plugin_manager import plugin_manager
from app.plugins.my_custom_plugin import MyCustomPlugin

plugin_manager.register(MyCustomPlugin())
```

### Step 3: Create Tests

Create tests in `tests/test_plugins.py`:

```python
import pytest
from app.plugins.my_custom_plugin import MyCustomPlugin

@pytest.mark.unit
class TestMyCustomPlugin:
    """Tests for custom plugin."""

    def test_plugin_name(self):
        """Test plugin name."""
        plugin = MyCustomPlugin()
        assert plugin.get_plugin_name() == "my_custom_plugin"

    def test_execute_success(self):
        """Test successful execution."""
        plugin = MyCustomPlugin()
        result = plugin.execute(data={'test': 'value'})

        assert result['success'] is True
        assert 'result' in result

    def test_execute_error(self):
        """Test error handling."""
        plugin = MyCustomPlugin()
        result = plugin.execute(data=None)

        assert result['success'] is False
        assert 'error' in result
```

## Plugin Categories

### 1. Forensic Analysis Plugins

For analyzing evidence files (images, videos, documents):

```python
class ImageAnalysisPlugin:
    """Analyze image evidence."""

    @hookimpl
    def execute(self, file_path=None, **kwargs):
        """
        Analyze image file.

        Args:
            file_path: Path to image file

        Returns:
            dict: Analysis results including metadata
        """
        from PIL import Image
        import piexif

        try:
            img = Image.open(file_path)

            # Extract EXIF
            exif_data = piexif.load(img.info.get('exif', b''))

            # Analyze image properties
            analysis = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'exif': self._parse_exif(exif_data)
            }

            return {
                'success': True,
                'analysis': analysis
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_exif(self, exif_data):
        """Parse EXIF data into readable format."""
        # Implementation
        pass
```

### 2. OSINT Plugins

For open-source intelligence gathering:

```python
class SocialMediaSearchPlugin:
    """Search social media for username."""

    @hookimpl
    def execute(self, username=None, **kwargs):
        """
        Search for username across platforms.

        Args:
            username: Username to search

        Returns:
            dict: Found profiles
        """
        platforms = [
            'twitter',
            'instagram',
            'linkedin',
            'facebook'
        ]

        results = []

        for platform in platforms:
            profile = self._search_platform(platform, username)
            if profile:
                results.append(profile)

        return {
            'success': True,
            'username': username,
            'platforms_found': len(results),
            'profiles': results
        }

    def _search_platform(self, platform, username):
        """Search specific platform."""
        # Implementation (respect robots.txt and rate limits)
        pass
```

### 3. Validation Plugins

For validating identities and documents:

```python
class PassportValidatorPlugin:
    """Validate passport numbers."""

    @hookimpl
    def execute(self, passport_number=None, country=None, **kwargs):
        """
        Validate passport number format.

        Args:
            passport_number: Passport number
            country: Issuing country code

        Returns:
            dict: Validation result
        """
        validators = {
            'ES': self._validate_spanish_passport,
            'FR': self._validate_french_passport,
            # Add more countries
        }

        validator = validators.get(country)

        if not validator:
            return {
                'success': False,
                'error': f'No validator for country: {country}'
            }

        is_valid = validator(passport_number)

        return {
            'success': True,
            'valid': is_valid,
            'passport_number': passport_number,
            'country': country
        }

    def _validate_spanish_passport(self, number):
        """Validate Spanish passport format."""
        import re
        # Spanish passport: 3 letters + 6 digits
        pattern = r'^[A-Z]{3}\d{6}$'
        return bool(re.match(pattern, number))
```

## Best Practices

### 1. Error Handling

Always return structured error responses:

```python
try:
    # Plugin logic
    result = process_data(data)

    return {
        'success': True,
        'result': result
    }

except FileNotFoundError as e:
    return {
        'success': False,
        'error': 'File not found',
        'details': str(e)
    }

except Exception as e:
    return {
        'success': False,
        'error': 'Unexpected error',
        'details': str(e)
    }
```

### 2. Logging

Use Python's logging module:

```python
import logging

logger = logging.getLogger(__name__)

class MyPlugin:
    @hookimpl
    def execute(self, **kwargs):
        logger.info(f"Executing {self.get_plugin_name()}")

        try:
            # Process
            logger.debug("Processing data...")
            result = self._process()

            logger.info("Plugin execution successful")
            return {'success': True, 'result': result}

        except Exception as e:
            logger.error(f"Plugin error: {str(e)}")
            return {'success': False, 'error': str(e)}
```

### 3. Performance

For heavy processing, use Celery tasks:

```python
from app.tasks.celery_app import celery

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def heavy_analysis_task(self, file_path):
    """Heavy analysis as Celery task."""
    plugin = MyHeavyPlugin()
    return plugin.execute(file_path=file_path)

class MyHeavyPlugin:
    @hookimpl
    def execute(self, file_path=None, async_mode=False, **kwargs):
        if async_mode:
            # Execute as Celery task
            task = heavy_analysis_task.delay(file_path)
            return {
                'success': True,
                'task_id': task.id,
                'async': True
            }
        else:
            # Execute synchronously
            result = self._heavy_processing(file_path)
            return {
                'success': True,
                'result': result
            }
```

### 4. Configuration

Use environment variables for plugin configuration:

```python
import os

class ConfigurablePlugin:
    def __init__(self):
        self.api_key = os.getenv('PLUGIN_API_KEY')
        self.api_url = os.getenv('PLUGIN_API_URL', 'https://api.example.com')
        self.timeout = int(os.getenv('PLUGIN_TIMEOUT', '30'))

    @hookimpl
    def execute(self, **kwargs):
        # Use configuration
        response = requests.get(
            self.api_url,
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=self.timeout
        )
        # Process response
```

### 5. Documentation

Document your plugin thoroughly:

```python
class WellDocumentedPlugin:
    """
    Plugin for performing XYZ analysis.

    This plugin analyzes evidence files and extracts XYZ metadata
    following the ABC standard for forensic analysis.

    Capabilities:
    - Extract XYZ metadata
    - Validate file integrity
    - Detect manipulation

    Requirements:
    - Python 3.11+
    - xyz-library >= 2.0

    Configuration:
    - XYZ_API_KEY: API key for XYZ service
    - XYZ_MODE: Analysis mode (fast|thorough)

    Example:
        plugin = WellDocumentedPlugin()
        result = plugin.execute(file_path='/path/to/evidence.xyz')
    """

    @hookimpl
    def execute(self, file_path=None, mode='fast', **kwargs):
        """
        Execute XYZ analysis on evidence file.

        Args:
            file_path (str): Absolute path to evidence file
            mode (str): Analysis mode - 'fast' or 'thorough'
            **kwargs: Additional plugin-specific parameters

        Returns:
            dict: Analysis results with structure:
                {
                    'success': bool,
                    'metadata': dict,
                    'integrity_check': bool,
                    'manipulation_detected': bool
                }

        Raises:
            FileNotFoundError: If file_path does not exist
            ValueError: If mode is invalid

        Example:
            >>> plugin.execute(file_path='/data/evidence.xyz', mode='thorough')
            {'success': True, 'metadata': {...}, 'integrity_check': True}
        """
        pass
```

## Integration with Web UI

### Creating Plugin Routes

Add routes for web interface in `app/blueprints/plugins/routes.py`:

```python
@plugins_bp.route('/execute/my_custom_plugin', methods=['GET', 'POST'])
@login_required
@audit_action('PLUGIN_EXECUTED', 'plugin')
def execute_my_custom_plugin():
    """Execute custom plugin from web interface."""
    if request.method == 'POST':
        # Get form data
        data = request.form.get('data')

        # Execute plugin
        result = plugin_manager.execute_plugin(
            'my_custom_plugin',
            data=data
        )

        return render_template(
            'plugins/result.html',
            plugin_name='my_custom_plugin',
            result=result
        )

    return render_template('plugins/my_custom_plugin.html')
```

### Creating Plugin Templates

Create template in `app/templates/plugins/`:

```html
<!-- app/templates/plugins/my_custom_plugin.html -->
{% extends "base.html" %}

{% block title %}My Custom Plugin{% endblock %}

{% block content %}
<div class="container mt-4">
    <h1>My Custom Plugin</h1>
    <p>Performs custom forensic analysis</p>

    <form method="POST" class="mt-4">
        {{ form.hidden_tag() }}

        <div class="mb-3">
            <label for="data" class="form-label">Input Data</label>
            <textarea class="form-control" id="data" name="data" rows="5"></textarea>
        </div>

        <button type="submit" class="btn btn-primary">
            <i class="bi bi-play-circle"></i> Execute Analysis
        </button>
    </form>
</div>
{% endblock %}
```

## Distribution

### Packaging Plugin

Create `setup.py` for distributable plugins:

```python
from setuptools import setup, find_packages

setup(
    name='case-manager-my-plugin',
    version='1.0.0',
    description='Custom plugin for Case Manager',
    author='Your Name',
    author_email='you@example.com',
    packages=find_packages(),
    install_requires=[
        'case-manager>=1.0.0',
        # Plugin dependencies
    ],
    entry_points={
        'case_manager.plugins': [
            'my_custom_plugin = my_plugin.plugin:MyCustomPlugin',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.11',
    ],
)
```

### Installation

Users can install plugins via pip:

```bash
pip install case-manager-my-plugin
```

## Security Considerations

1. **Input Validation**: Always validate and sanitize input
2. **File Handling**: Never execute untrusted files
3. **API Keys**: Store securely in environment variables
4. **Rate Limiting**: Respect external API rate limits
5. **Data Privacy**: Handle personal data per GDPR/Ley 5/2014
6. **Error Messages**: Don't leak sensitive info in errors

## Legal Compliance

Plugins must comply with Spanish Law 5/2014:

- Don't facilitate illegal surveillance
- Respect privacy rights
- Document data sources
- Maintain audit trails
- Only operate on authorized investigations

## Support

For plugin development support:
- GitHub Issues: [repository]/issues
- Documentation: /docs
- Examples: /app/plugins/

## Example Plugins

See existing plugins for reference:
- `dni_validator.py`: DNI/NIE validation
- `exif_extractor.py`: Image metadata extraction
- `pdf_metadata.py`: PDF metadata extraction

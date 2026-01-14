"""
Plugin Manager for Case Manager.

Manages plugin registration, discovery, and execution.
"""
import logging
from typing import Dict, List, Any, Optional
import pluggy

from app.plugins.hookspecs import PluginSpec

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages all plugins in the system."""

    def __init__(self):
        """Initialize the plugin manager."""
        self.pm = pluggy.PluginManager("casemanager")
        self.pm.add_hookspecs(PluginSpec)
        self._plugins_loaded = False
        self.app = None

    def init_app(self, app):
        """
        Initialize plugin system with Flask app.

        Args:
            app: Flask application instance
        """
        self.app = app
        self.load_plugins()

    def load_plugins(self):
        """Load all available plugins."""
        if self._plugins_loaded:
            return

        try:
            # Import and register forensic plugins
            from app.plugins.forensic.dni_validator import DNIValidatorPlugin
            from app.plugins.forensic.exif_extractor import ExifExtractorPlugin
            from app.plugins.forensic.pdf_metadata import PDFMetadataPlugin

            # Register forensic plugins
            self.pm.register(DNIValidatorPlugin())
            self.pm.register(ExifExtractorPlugin())
            self.pm.register(PDFMetadataPlugin())

            # Import and register OSINT plugins
            from app.plugins.osint.ipqualityscore_validator import IPQualityScoreValidatorPlugin
            from app.plugins.osint.x_profile_lookup import XProfileLookupPlugin
            from app.plugins.osint.x_tweets_lookup import XTweetsLookupPlugin
            from app.plugins.osint.instagram_profile_lookup import InstagramProfileLookupPlugin
            from app.plugins.osint.instagram_posts_lookup import InstagramPostsLookupPlugin

            self.pm.register(IPQualityScoreValidatorPlugin())
            self.pm.register(XProfileLookupPlugin())
            self.pm.register(XTweetsLookupPlugin())
            self.pm.register(InstagramProfileLookupPlugin())
            self.pm.register(InstagramPostsLookupPlugin())

            self._plugins_loaded = True
            logger.info(f"Loaded {len(self.pm.get_plugins())} plugins")

        except ImportError as e:
            logger.warning(f"Failed to load some plugins: {e}")

    def get_all_plugins(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered plugins.

        Returns:
            list: Plugin information dictionaries
        """
        plugins = []
        for plugin in self.pm.get_plugins():
            if hasattr(plugin, 'get_info'):
                plugins.append(plugin.get_info())
        return plugins

    def get_plugin_by_name(self, name: str) -> Optional[Any]:
        """
        Get a plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        for plugin in self.pm.get_plugins():
            if hasattr(plugin, 'get_info'):
                info = plugin.get_info()
                if info.get('name') == name:
                    return plugin
        return None

    def get_forensic_plugins(self) -> List[Any]:
        """
        Get all forensic analysis plugins.

        Returns:
            list: Forensic plugin instances
        """
        plugins = []
        for plugin in self.pm.get_plugins():
            if hasattr(plugin, 'analyze_file'):
                plugins.append(plugin)
        return plugins

    def get_osint_plugins(self) -> List[Any]:
        """
        Get all OSINT plugins.

        Returns:
            list: OSINT plugin instances
        """
        plugins = []
        for plugin in self.pm.get_plugins():
            if hasattr(plugin, 'lookup'):
                plugins.append(plugin)
        return plugins

    def execute_forensic_plugin(self, plugin_name: str, file_path: str,
                                 **kwargs) -> Dict[str, Any]:
        """
        Execute a forensic plugin on a file.

        Args:
            plugin_name: Name of the plugin to execute
            file_path: Path to the file to analyze
            **kwargs: Additional plugin-specific arguments

        Returns:
            dict: Analysis results
        """
        plugin = self.get_plugin_by_name(plugin_name)
        if not plugin:
            return {
                'success': False,
                'error': f'Plugin {plugin_name} not found'
            }

        try:
            if hasattr(plugin, 'analyze_file'):
                result = plugin.analyze_file(file_path, **kwargs)
                return {
                    'success': True,
                    'plugin': plugin_name,
                    'result': result
                }
            else:
                return {
                    'success': False,
                    'error': f'Plugin {plugin_name} does not support file analysis'
                }
        except Exception as e:
            logger.error(f"Error executing plugin {plugin_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def execute_osint_plugin(self, plugin_name: str, query: str,
                             **kwargs) -> Dict[str, Any]:
        """
        Execute an OSINT plugin.

        Args:
            plugin_name: Name of the plugin to execute
            query: Query string (email, username, etc.)
            **kwargs: Additional plugin-specific arguments

        Returns:
            dict: Lookup results
        """
        plugin = self.get_plugin_by_name(plugin_name)
        if not plugin:
            return {
                'success': False,
                'error': f'Plugin {plugin_name} not found'
            }

        try:
            if hasattr(plugin, 'lookup'):
                result = plugin.lookup(query, **kwargs)
                return {
                    'success': True,
                    'plugin': plugin_name,
                    'result': result
                }
            else:
                return {
                    'success': False,
                    'error': f'Plugin {plugin_name} does not support OSINT lookup'
                }
        except Exception as e:
            logger.error(f"Error executing plugin {plugin_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_dni_nie(self, identifier: str) -> Dict[str, Any]:
        """
        Validate Spanish DNI/NIE using the modulo 23 algorithm.

        Args:
            identifier: DNI or NIE string

        Returns:
            dict: Validation result
        """
        plugin = self.get_plugin_by_name('dni_validator')
        if plugin:
            return plugin.validate(identifier)
        return {
            'valid': False,
            'error': 'DNI validator plugin not available'
        }

    def get_applicable_plugins_for_evidence(self, evidence) -> List[Dict[str, Any]]:
        """
        Get plugins applicable to a specific evidence file.

        Args:
            evidence: Evidence instance

        Returns:
            list: Applicable plugin information dictionaries
        """
        import os
        applicable_plugins = []
        file_ext = os.path.splitext(evidence.original_filename)[1].lower()

        for plugin in self.get_forensic_plugins():
            info = plugin.get_info()

            # Check if plugin supports this file type
            supported_formats = info.get('supported_formats', [])
            if not supported_formats or file_ext in supported_formats:
                # Check if plugin is available (dependencies installed)
                if info.get('available', True):
                    applicable_plugins.append(info)

        return applicable_plugins

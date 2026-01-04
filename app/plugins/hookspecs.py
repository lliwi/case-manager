"""
Plugin hook specifications.

Defines the interfaces that plugins must implement.
"""
import pluggy

hookspec = pluggy.HookspecMarker("casemanager")


class PluginSpec:
    """Hook specifications for all plugins."""

    @hookspec
    def get_info(self):
        """
        Get plugin information.

        Returns:
            dict: Plugin metadata (name, description, version, author, etc.)
        """

    @hookspec
    def analyze_file(self, file_path, **kwargs):
        """
        Analyze a file and extract metadata/information (forensic plugins).

        Args:
            file_path: Path to the file to analyze
            **kwargs: Additional plugin-specific arguments

        Returns:
            dict: Analysis results
        """

    @hookspec
    def lookup(self, query, **kwargs):
        """
        Perform an OSINT lookup (OSINT plugins).

        Args:
            query: Query string (email, username, phone, etc.)
            **kwargs: Additional plugin-specific arguments

        Returns:
            dict: Lookup results
        """

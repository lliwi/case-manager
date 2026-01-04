"""
Plugin system for Case Manager.

This module implements a pluggy-based plugin system for forensic analysis
and OSINT tasks.
"""
from app.plugins.manager import PluginManager

# Global plugin manager instance
plugin_manager = PluginManager()

__all__ = ['plugin_manager', 'PluginManager']

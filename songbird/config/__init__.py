# songbird/config/__init__.py
"""Configuration management for Songbird."""

from .config_manager import ConfigManager, get_config

__all__ = ["ConfigManager", "get_config"]
"""Abstract base class for plugin modules."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import Registry


class PluginModule(ABC):
    """Common interface for plugin modules."""
    
    def __init__(self, registry: Registry):
        self.registry = registry
        self._running = False

    @property
    @abstractmethod
    def key(self) -> str:
        """System name of the plugin."""
        pass

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable name for UI."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the plugin."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the plugin."""
        pass

    def is_external_service(self) -> bool:
        """Return True if this plugin runs as external systemd service."""
        return False

    def external_service_name(self) -> Optional[str]:
        """Return systemd service name if external, None otherwise."""
        return None

    def has_web_interface(self) -> bool:
        """Return True if plugin provides web interface."""
        return False

    def get_web_routes(self) -> Optional[str]:
        """Return URL prefix for plugin web routes (e.g., '/plugins/myplugin')."""
        return None

    def register_web_routes(self, app):
        """Register plugin web routes with Flask app."""
        pass

    def get_config_schema(self) -> dict:
        """Return JSON schema for plugin configuration."""
        return {}

    def get_config(self) -> dict:
        """Return current plugin configuration."""
        return {}

    def update_config(self, config: dict) -> bool:
        """Update plugin configuration. Return True if successful."""
        return True

    @property
    def running(self) -> bool:
        """Return running status."""
        return self._running
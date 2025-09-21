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
        self._enabled = True  # Plugins are enabled by default when instantiated

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

    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True

    def disable(self) -> None:
        """Disable the plugin.""" 
        self._enabled = False

    def is_external_service(self) -> bool:
        """Return True if this plugin runs as external systemd service."""
        return False

    def external_service_name(self) -> Optional[str]:
        """Return systemd service name if external, None otherwise."""
        return None

    def has_main_interface(self) -> bool:
        """Return True if plugin provides main user interface."""
        return False
    
    def get_main_routes(self) -> Optional[str]:
        """Return URL prefix for main plugin interface (e.g., '/plugins/myplugin')."""
        return None
    
    def has_settings_interface(self) -> bool:
        """Return True if plugin provides settings interface."""
        return False
        
    def get_settings_routes(self) -> Optional[str]:
        """Return URL prefix for plugin settings (e.g., '/plugins/myplugin/settings')."""
        return None
    
    def get_card_info(self) -> dict:
        """Return information for plugin card on main page."""
        return {
            "title": self.label,
            "description": "Plugin functionality",
            "icon": "🔧",
            "status": "enabled" if self.enabled else "disabled"
        }

    def has_web_interface(self) -> bool:
        """Return True if plugin provides web interface (legacy compatibility)."""
        return self.has_main_interface() or self.has_settings_interface()

    def get_web_routes(self) -> Optional[str]:
        """Return URL prefix for plugin web routes (legacy compatibility)."""
        return self.get_main_routes()

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

    def supports_per_rig_config(self) -> bool:
        """Return True if plugin supports per-rig daemon configuration."""
        return False
    
    def get_daemon_config_for_rig(self, rig_id: str) -> dict:
        """Get daemon configuration for specific rig."""
        if not self.supports_per_rig_config():
            return {}
        
        config_manager = getattr(self.registry, 'config_manager', None)
        if config_manager:
            return config_manager.get_daemon_config(self.key, rig_id)
        return {}
    
    def update_daemon_config_for_rig(self, rig_id: str, config: dict) -> bool:
        """Update daemon configuration for specific rig."""
        if not self.supports_per_rig_config():
            return False
        
        try:
            config_manager = getattr(self.registry, 'config_manager', None)
            if config_manager:
                config_manager.save_daemon_config(self.key, rig_id, config)
                return True
            return False
        except Exception:
            return False
    
    def list_configured_rigs(self) -> list:
        """List rig IDs that have daemon configuration for this plugin."""
        if not self.supports_per_rig_config():
            return []
        
        config_manager = getattr(self.registry, 'config_manager', None)
        if config_manager:
            return config_manager.list_daemon_configs(self.key)
        return []
    
    def get_daemon_service_name(self, rig_id: str) -> Optional[str]:
        """Return systemd service name for daemon on specific rig."""
        if self.is_external_service() and self.supports_per_rig_config():
            return f"rig-plugin@{self.key}-{rig_id}.service"
        elif self.is_external_service():
            return f"rig-plugin@{self.key}.service"
        return None

    @property
    def enabled(self) -> bool:
        """Return enabled status."""
        return self._enabled
    
    @property
    def running(self) -> bool:
        """Return running status (legacy compatibility)."""
        return self._enabled

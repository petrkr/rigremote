"""Registry for radio drivers and plugins with autodiscovery."""

import os
import sys
import importlib
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from .interfaces.radio_driver import RadioDriver
from .interfaces.plugin_module import PluginModule
from .events import event_bus

logger = logging.getLogger(__name__)


class Registry:
    """Central registry for radio drivers and plugin modules."""
    
    def __init__(self, config_manager=None):
        self.radio_drivers: Dict[str, Type[RadioDriver]] = {}
        self.radio_instances: Dict[str, RadioDriver] = {}
        self.plugin_classes: Dict[str, Type[PluginModule]] = {}
        self.plugin_instances: Dict[str, PluginModule] = {}
        self.config_manager = config_manager
        
    def discover_drivers(self, radios_path: str = "radios") -> None:
        """Discover and register radio drivers from radios/ directory."""
        logger.info(f"Discovering radio drivers in {radios_path}/")
        
        # Add radios directory to Python path
        radios_dir = Path(radios_path)
        if not radios_dir.exists():
            logger.warning(f"Radios directory {radios_path} not found")
            return
            
        sys.path.insert(0, str(radios_dir.parent))
        
        # Scan Python files in radios directory
        for py_file in radios_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
                
            module_name = f"{radios_path}.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                
                # Find classes that inherit from RadioDriver
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, RadioDriver) and 
                        obj != RadioDriver and 
                        not inspect.isabstract(obj) and
                        obj.__module__ == module.__name__):  # Only classes defined in this module
                        
                        driver_type = getattr(obj, 'DRIVER_TYPE', py_file.stem)
                        self.radio_drivers[driver_type] = obj
                        logger.info(f"Registered radio driver: {driver_type} ({name})")
                        
            except Exception as e:
                logger.error(f"Failed to load radio driver from {py_file}: {e}")
    
    def discover_plugins(self, plugins_path: str = "plugins") -> None:
        """Discover and register plugins from plugins/ directory."""
        logger.info(f"Discovering plugins in {plugins_path}/")
        
        # Add plugins directory to Python path
        plugins_dir = Path(plugins_path)
        if not plugins_dir.exists():
            logger.warning(f"Plugins directory {plugins_path} not found")
            return
            
        sys.path.insert(0, str(plugins_dir.parent))
        
        # Scan Python files in plugins directory
        for py_file in plugins_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
                
            module_name = f"{plugins_path}.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                
                # Find classes that inherit from PluginModule
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, PluginModule) and 
                        obj != PluginModule and 
                        not inspect.isabstract(obj)):
                        
                        # Instantiate plugin to get its key
                        try:
                            temp_instance = obj(self)
                            plugin_key = temp_instance.key
                            self.plugin_classes[plugin_key] = obj
                            logger.info(f"Registered plugin: {plugin_key} ({name})")
                        except Exception as e:
                            logger.error(f"Failed to instantiate plugin {name}: {e}")
                        
            except Exception as e:
                logger.error(f"Failed to load plugin from {py_file}: {e}")
    
    def create_radio(self, radio_id: str, driver_type: str, name: str, config: Dict[str, Any]) -> Optional[RadioDriver]:
        """Create a radio instance."""
        if driver_type not in self.radio_drivers:
            logger.error(f"Unknown radio driver type: {driver_type}")
            return None
            
        try:
            driver_class = self.radio_drivers[driver_type]
            radio = driver_class(radio_id, name, config)
            self.radio_instances[radio_id] = radio
            logger.info(f"Created radio instance: {radio_id} ({driver_type})")
            return radio
        except Exception as e:
            logger.error(f"Failed to create radio {radio_id}: {e}")
            return None
    
    def create_plugin(self, plugin_key: str) -> Optional[PluginModule]:
        """Create a plugin instance."""
        if plugin_key not in self.plugin_classes:
            logger.error(f"Unknown plugin: {plugin_key}")
            return None
            
        try:
            plugin_class = self.plugin_classes[plugin_key]
            plugin = plugin_class(self)
            self.plugin_instances[plugin_key] = plugin
            logger.info(f"Created plugin instance: {plugin_key}")
            return plugin
        except Exception as e:
            logger.error(f"Failed to create plugin {plugin_key}: {e}")
            return None
    
    def list_radios(self) -> List[str]:
        """List all radio instance IDs."""
        return list(self.radio_instances.keys())
    
    def get_radio(self, radio_id: str) -> Optional[RadioDriver]:
        """Get radio instance by ID."""
        return self.radio_instances.get(radio_id)
    
    def list_plugins(self) -> List[str]:
        """List all available plugin keys."""
        return list(self.plugin_classes.keys())
    
    def get_plugin(self, plugin_key: str) -> Optional[PluginModule]:
        """Get plugin instance by key."""
        return self.plugin_instances.get(plugin_key)
    
    def broadcast_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Broadcast an event through the event bus."""
        event_bus.emit(event_name, payload)
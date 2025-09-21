"""Configuration management for RIG Remote Control."""

import os
import sys
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# Python 3.11+ has tomllib built-in, for older versions use tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("tomli package required for Python < 3.11. Install with: pip install tomli")

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration."""
    debug: bool = False
    secret_key: str = "dev-secret-key"
    host: str = "0.0.0.0"
    port: int = 5000
    log_level: str = "INFO"
    log_file: str = ""


@dataclass
class SecurityConfig:
    """Security configuration."""
    enable_api_auth: bool = False
    api_key_header: str = "X-API-Key"
    jwt_secret: str = "jwt-secret-key"
    session_timeout: int = 3600
    enable_cors: bool = False
    allowed_origins: List[str] = field(default_factory=list)


@dataclass
class WebSocketConfig:
    """WebSocket configuration."""
    ping_interval: int = 30
    broadcast_interval: float = 2.0
    max_connections: int = 100


@dataclass
class RadioInstanceConfig:
    """Configuration for a radio instance."""
    id: str
    name: str
    driver_type: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RadiosConfig:
    """Radio configuration."""
    instances: List[RadioInstanceConfig] = field(default_factory=list)


@dataclass
class PluginsConfig:
    """Plugin configuration."""
    auto_discover: bool = True
    enabled_plugins: List[str] = field(default_factory=list)
    config_dir: str = "config/plugins"


@dataclass
class SystemdConfig:
    """Systemd configuration."""
    service_template: str = "systemd/plugin@.service"
    enable_status_check: bool = True
    service_timeout: int = 5


@dataclass
class PathsConfig:
    """Path configuration."""
    radios_dir: str = "radios"
    plugins_dir: str = "plugins"
    config_dir: str = "config"
    templates_dir: str = "web/ui/templates"
    static_dir: str = "web/ui/static"


@dataclass
class Configuration:
    """Main configuration container."""
    app: AppConfig = field(default_factory=AppConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    radios: RadiosConfig = field(default_factory=RadiosConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    systemd: SystemdConfig = field(default_factory=SystemdConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)


class ConfigManager:
    """Configuration manager with TOML loading and environment overrides."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._find_config_file()
        self.config = Configuration()
        self._load_configuration()
    
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations."""
        possible_paths = [
            "config/settings.toml",
            "settings.toml",
            "/etc/rig-web/settings.toml",
            os.path.expanduser("~/.config/rig-web/settings.toml")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found configuration file: {path}")
                return path
        
        logger.warning("No configuration file found, using defaults")
        return None
    
    def _load_configuration(self):
        """Load configuration from file and apply environment overrides."""
        # Load from TOML file if exists
        if self.config_file and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'rb') as f:
                    toml_data = tomllib.load(f)
                self._apply_toml_config(toml_data)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Error loading configuration file {self.config_file}: {e}")
                logger.info("Using default configuration")
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        # Validate configuration
        self._validate_configuration()
    
    def _apply_toml_config(self, toml_data: Dict[str, Any]):
        """Apply TOML configuration data to config objects."""
        
        # App configuration
        if 'app' in toml_data:
            app_data = toml_data['app']
            self.config.app = AppConfig(
                debug=app_data.get('debug', self.config.app.debug),
                secret_key=app_data.get('secret_key', self.config.app.secret_key),
                host=app_data.get('host', self.config.app.host),
                port=app_data.get('port', self.config.app.port),
                log_level=app_data.get('log_level', self.config.app.log_level),
                log_file=app_data.get('log_file', self.config.app.log_file)
            )
        
        # Security configuration
        if 'security' in toml_data:
            sec_data = toml_data['security']
            self.config.security = SecurityConfig(
                enable_api_auth=sec_data.get('enable_api_auth', self.config.security.enable_api_auth),
                api_key_header=sec_data.get('api_key_header', self.config.security.api_key_header),
                jwt_secret=sec_data.get('jwt_secret', self.config.security.jwt_secret),
                session_timeout=sec_data.get('session_timeout', self.config.security.session_timeout),
                enable_cors=sec_data.get('enable_cors', self.config.security.enable_cors),
                allowed_origins=sec_data.get('allowed_origins', self.config.security.allowed_origins)
            )
        
        # WebSocket configuration
        if 'websocket' in toml_data:
            ws_data = toml_data['websocket']
            self.config.websocket = WebSocketConfig(
                ping_interval=ws_data.get('ping_interval', self.config.websocket.ping_interval),
                broadcast_interval=ws_data.get('broadcast_interval', self.config.websocket.broadcast_interval),
                max_connections=ws_data.get('max_connections', self.config.websocket.max_connections)
            )
        
        # Radio configuration
        if 'radios' in toml_data:
            radios_data = toml_data['radios']
            radio_instances = []
            
            for instance_data in radios_data.get('instances', []):
                radio_instance = RadioInstanceConfig(
                    id=instance_data['id'],
                    name=instance_data['name'],
                    driver_type=instance_data['driver_type'],
                    enabled=instance_data.get('enabled', True),
                    config=instance_data.get('config', {})
                )
                radio_instances.append(radio_instance)
            
            self.config.radios = RadiosConfig(instances=radio_instances)
        
        # Plugin configuration
        if 'plugins' in toml_data:
            plugins_data = toml_data['plugins']
            self.config.plugins = PluginsConfig(
                auto_discover=plugins_data.get('auto_discover', self.config.plugins.auto_discover),
                enabled_plugins=plugins_data.get('enabled_plugins', self.config.plugins.enabled_plugins),
                config_dir=plugins_data.get('config_dir', self.config.plugins.config_dir)
            )
        
        # Systemd configuration
        if 'systemd' in toml_data:
            systemd_data = toml_data['systemd']
            self.config.systemd = SystemdConfig(
                service_template=systemd_data.get('service_template', self.config.systemd.service_template),
                enable_status_check=systemd_data.get('enable_status_check', self.config.systemd.enable_status_check),
                service_timeout=systemd_data.get('service_timeout', self.config.systemd.service_timeout)
            )
        
        # Paths configuration
        if 'paths' in toml_data:
            paths_data = toml_data['paths']
            self.config.paths = PathsConfig(
                radios_dir=paths_data.get('radios_dir', self.config.paths.radios_dir),
                plugins_dir=paths_data.get('plugins_dir', self.config.paths.plugins_dir),
                config_dir=paths_data.get('config_dir', self.config.paths.config_dir),
                templates_dir=paths_data.get('templates_dir', self.config.paths.templates_dir),
                static_dir=paths_data.get('static_dir', self.config.paths.static_dir)
            )
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        env_mappings = {
            # App settings
            'RIG_DEBUG': ('app', 'debug', bool),
            'RIG_SECRET_KEY': ('app', 'secret_key', str),
            'RIG_HOST': ('app', 'host', str),
            'RIG_PORT': ('app', 'port', int),
            'RIG_LOG_LEVEL': ('app', 'log_level', str),
            'RIG_LOG_FILE': ('app', 'log_file', str),
            
            # Security settings
            'RIG_API_AUTH': ('security', 'enable_api_auth', bool),
            'RIG_API_KEY_HEADER': ('security', 'api_key_header', str),
            'RIG_JWT_SECRET': ('security', 'jwt_secret', str),
            'RIG_SESSION_TIMEOUT': ('security', 'session_timeout', int),
            
            # WebSocket settings
            'RIG_WS_PING_INTERVAL': ('websocket', 'ping_interval', int),
            'RIG_WS_BROADCAST_INTERVAL': ('websocket', 'broadcast_interval', float),
            'RIG_WS_MAX_CONNECTIONS': ('websocket', 'max_connections', int),
        }
        
        for env_var, (section, key, value_type) in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    # Convert value to appropriate type
                    if value_type == bool:
                        converted_value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif value_type == int:
                        converted_value = int(env_value)
                    elif value_type == float:
                        converted_value = float(env_value)
                    else:
                        converted_value = env_value
                    
                    # Apply to configuration
                    section_obj = getattr(self.config, section)
                    setattr(section_obj, key, converted_value)
                    logger.debug(f"Applied environment override: {env_var}={converted_value}")
                    
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid environment variable {env_var}={env_value}: {e}")
    
    def _validate_configuration(self):
        """Validate configuration values."""
        errors = []
        
        # Validate app config
        if self.config.app.port < 1 or self.config.app.port > 65535:
            errors.append(f"Invalid port: {self.config.app.port}")
        
        if self.config.app.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append(f"Invalid log level: {self.config.app.log_level}")
        
        # Validate WebSocket config
        if self.config.websocket.ping_interval < 1:
            errors.append(f"Invalid ping interval: {self.config.websocket.ping_interval}")
        
        if self.config.websocket.broadcast_interval < 0.1:
            errors.append(f"Invalid broadcast interval: {self.config.websocket.broadcast_interval}")
        
        # Validate radio instances
        radio_ids = set()
        for radio in self.config.radios.instances:
            if not radio.id:
                errors.append("Radio instance missing ID")
            elif radio.id in radio_ids:
                errors.append(f"Duplicate radio ID: {radio.id}")
            else:
                radio_ids.add(radio.id)
            
            if not radio.name:
                errors.append(f"Radio {radio.id} missing name")
            
            if not radio.driver_type:
                errors.append(f"Radio {radio.id} missing driver_type")
        
        if errors:
            error_msg = "Configuration validation errors:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def get_radio_configs(self) -> List[RadioInstanceConfig]:
        """Get list of radio instance configurations."""
        return self.config.radios.instances
    
    def get_enabled_radio_configs(self) -> List[RadioInstanceConfig]:
        """Get list of enabled radio instance configurations."""
        return [radio for radio in self.config.radios.instances if radio.enabled]
    
    def get_plugin_config(self, plugin_key: str) -> Dict[str, Any]:
        """Get configuration for specific plugin."""
        plugin_config_file = os.path.join(self.config.plugins.config_dir, f"{plugin_key}.toml")
        
        if os.path.exists(plugin_config_file):
            try:
                with open(plugin_config_file, 'rb') as f:
                    plugin_data = tomllib.load(f)
                return plugin_data
            except Exception as e:
                logger.error(f"Error loading plugin config {plugin_config_file}: {e}")
                return {}
        else:
            logger.warning(f"Plugin config file not found: {plugin_config_file}")
            return {}
    
    def save_plugin_config(self, plugin_key: str, config_data: Dict[str, Any]):
        """Save configuration for specific plugin."""
        import toml
        from datetime import datetime
        
        # Ensure plugins config directory exists
        os.makedirs(self.config.plugins.config_dir, exist_ok=True)
        
        plugin_config_file = os.path.join(self.config.plugins.config_dir, f"{plugin_key}.toml")
        
        try:
            # Create backup if file exists
            if os.path.exists(plugin_config_file):
                backup_path = f"{plugin_config_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(plugin_config_file, backup_path)
                logger.info(f"Created plugin config backup: {backup_path}")
            
            # Write configuration
            with open(plugin_config_file, 'w', encoding='utf-8') as f:
                toml.dump(config_data, f)
            
            logger.info(f"Plugin configuration saved: {plugin_config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save plugin configuration {plugin_config_file}: {e}")
            raise
    
    def list_plugin_configs(self) -> List[str]:
        """List available plugin configuration files."""
        plugin_configs = []
        if os.path.exists(self.config.plugins.config_dir):
            for file in os.listdir(self.config.plugins.config_dir):
                if file.endswith('.toml') and not file.startswith('.'):
                    plugin_key = file[:-5]  # Remove .toml extension
                    plugin_configs.append(plugin_key)
        return plugin_configs
    
    def reload(self):
        """Reload configuration from file."""
        logger.info("Reloading configuration...")
        old_config = self.config
        self.config = Configuration()
        
        try:
            self._load_configuration()
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            self.config = old_config  # Restore old config
            raise
    
    def save_example_config(self, path: str = "config/settings.example.toml"):
        """Save an example configuration file."""
        # This would save the current example we already have
        logger.info(f"Example configuration available at {path}")


# Global configuration instance
config_manager: Optional[ConfigManager] = None


def get_config() -> Configuration:
    """Get the global configuration instance."""
    global config_manager
    if config_manager is None:
        config_manager = ConfigManager()
    return config_manager.config


def init_config(config_file: Optional[str] = None) -> ConfigManager:
    """Initialize global configuration manager."""
    global config_manager
    config_manager = ConfigManager(config_file)
    return config_manager
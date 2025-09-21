"""Configuration API for web-based management."""

import os
import logging
from flask import Blueprint, jsonify, request, current_app
from typing import Dict, Any

logger = logging.getLogger(__name__)

config_api_bp = Blueprint('config_api', __name__, url_prefix='/api/config')


def get_registry():
    """Get registry from Flask app context."""
    return current_app.config['REGISTRY']


def get_config_manager():
    """Get config manager from Flask app context."""
    return current_app.config['CONFIG_MANAGER']


@config_api_bp.route('/radios', methods=['GET'])
def list_radio_configs():
    """Get all radio configurations."""
    config_manager = get_config_manager()
    config = config_manager.config
    
    radios = []
    for radio_config in config.radios.instances:
        radios.append({
            "id": radio_config.id,
            "name": radio_config.name,
            "driver_type": radio_config.driver_type,
            "enabled": radio_config.enabled,
            "config": radio_config.config
        })
    
    return jsonify({"radios": radios})


@config_api_bp.route('/radios', methods=['POST'])
def add_radio_config():
    """Add new radio configuration."""
    data = request.get_json()
    
    if not data or not all(k in data for k in ['name', 'driver_type']):
        return jsonify({"error": "Missing required fields: name, driver_type"}), 400
    
    config_manager = get_config_manager()
    config = config_manager.config
    registry = get_registry()
    
    # Generate unique radio ID from name
    from core.utils import generate_radio_id
    existing_ids = [r.id for r in config.radios.instances]
    radio_id = generate_radio_id(data['name'], existing_ids)
    
    # Check if driver type is available
    available_drivers = list(registry.radio_drivers.keys())
    if data['driver_type'] not in available_drivers:
        return jsonify({
            "error": f"Unknown driver type: {data['driver_type']}",
            "available_drivers": available_drivers
        }), 400
    
    # Create new radio config
    from core.config import RadioInstanceConfig
    new_radio = RadioInstanceConfig(
        id=radio_id,
        name=data['name'],
        driver_type=data['driver_type'],
        enabled=data.get('enabled', True),
        config=data.get('config', {})
    )
    
    # Add to configuration
    config.radios.instances.append(new_radio)
    
    # Try to save configuration
    try:
        _save_configuration(config_manager)
        
        # Create and connect radio instance if enabled
        if new_radio.enabled:
            radio = registry.create_radio(
                new_radio.id,
                new_radio.driver_type,
                new_radio.name,
                new_radio.config
            )
            if radio:
                try:
                    radio.connect()
                    logger.info(f"Created and connected radio: {new_radio.id}")
                except Exception as e:
                    logger.error(f"Failed to connect radio {new_radio.id}: {e}")
        
        return jsonify({"success": True, "radio": {
            "id": new_radio.id,
            "name": new_radio.name,
            "driver_type": new_radio.driver_type,
            "enabled": new_radio.enabled
        }}), 201
        
    except Exception as e:
        # Remove from config on save failure
        config.radios.instances.remove(new_radio)
        logger.error(f"Failed to save configuration: {e}")
        return jsonify({"error": f"Failed to save configuration: {e}"}), 500


@config_api_bp.route('/radios/<radio_id>', methods=['PUT'])
def update_radio_config(radio_id: str):
    """Update radio configuration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    config_manager = get_config_manager()
    config = config_manager.config
    registry = get_registry()
    
    # Find radio config
    radio_config = None
    for r in config.radios.instances:
        if r.id == radio_id:
            radio_config = r
            break
    
    if not radio_config:
        return jsonify({"error": "Radio not found"}), 404
    
    # Update fields
    if 'name' in data:
        radio_config.name = data['name']
    if 'enabled' in data:
        radio_config.enabled = data['enabled']
    if 'config' in data:
        radio_config.config.update(data['config'])
    
    try:
        _save_configuration(config_manager)
        
        # Update registry instance
        existing_radio = registry.get_radio(radio_id)
        if existing_radio:
            if radio_config.enabled:
                # Reconnect with new config
                existing_radio.disconnect()
                existing_radio.config = radio_config.config
                existing_radio.name = radio_config.name
                existing_radio.connect()
            else:
                # Disable radio
                existing_radio.disconnect()
        elif radio_config.enabled:
            # Create new instance
            radio = registry.create_radio(
                radio_config.id,
                radio_config.driver_type,
                radio_config.name,
                radio_config.config
            )
            if radio:
                radio.connect()
        
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Failed to update radio configuration: {e}")
        return jsonify({"error": str(e)}), 500


@config_api_bp.route('/radios/<radio_id>', methods=['DELETE'])
def delete_radio_config(radio_id: str):
    """Delete radio configuration."""
    config_manager = get_config_manager()
    config = config_manager.config
    registry = get_registry()
    
    # Find and remove radio config
    radio_config = None
    for i, r in enumerate(config.radios.instances):
        if r.id == radio_id:
            radio_config = config.radios.instances.pop(i)
            break
    
    if not radio_config:
        return jsonify({"error": "Radio not found"}), 404
    
    try:
        _save_configuration(config_manager)
        
        # Remove from registry and disconnect
        existing_radio = registry.get_radio(radio_id)
        if existing_radio:
            existing_radio.disconnect()
            del registry.radio_instances[radio_id]
        
        return jsonify({"success": True})
        
    except Exception as e:
        # Restore config on failure
        config.radios.instances.append(radio_config)
        logger.error(f"Failed to delete radio configuration: {e}")
        return jsonify({"error": str(e)}), 500


@config_api_bp.route('/radio-drivers', methods=['GET'])
def list_radio_drivers():
    """Get available radio driver types."""
    registry = get_registry()
    
    drivers = []
    for driver_type, driver_class in registry.radio_drivers.items():
        # Get driver info
        driver_info = {
            "type": driver_type,
            "name": getattr(driver_class, 'DISPLAY_NAME', driver_type.title()),
            "description": driver_class.__doc__ or "",
            "config_fields": []
        }
        
        # Try to get config schema if available
        if hasattr(driver_class, 'get_config_schema'):
            try:
                schema = driver_class.get_config_schema()
                driver_info["config_schema"] = schema
            except Exception as e:
                logger.warning(f"Failed to get config schema for {driver_type}: {e}")
        
        # Add display name
        if hasattr(driver_class, 'DISPLAY_NAME'):
            driver_info["name"] = driver_class.DISPLAY_NAME
        
        drivers.append(driver_info)
    
    return jsonify({"drivers": drivers})


@config_api_bp.route('/plugins', methods=['GET'])
def list_plugin_configs():
    """Get all plugin configurations."""
    config_manager = get_config_manager()
    config = config_manager.config
    registry = get_registry()
    
    plugins = []
    
    # Get configuration for each available plugin
    for plugin_key in registry.list_plugins():
        plugin_instance = registry.get_plugin(plugin_key)
        
        if plugin_instance:
            plugin_info = {
                "key": plugin_instance.key,
                "label": plugin_instance.label,
                "enabled": plugin_key in config.plugins.enabled_plugins,
                "running": plugin_instance.running,
                "external_service": plugin_instance.is_external_service(),
                "has_web_interface": plugin_instance.has_web_interface(),
                "web_routes": plugin_instance.get_web_routes(),
                "config": plugin_instance.get_config(),
                "config_schema": plugin_instance.get_config_schema()
            }
        else:
            # Plugin class exists but not instantiated
            plugin_class = registry.plugin_classes.get(plugin_key)
            if plugin_class:
                temp_instance = plugin_class(registry)
                plugin_info = {
                    "key": temp_instance.key,
                    "label": temp_instance.label,
                    "enabled": plugin_key in config.plugins.enabled_plugins,
                    "running": False,
                    "external_service": temp_instance.is_external_service(),
                    "has_web_interface": temp_instance.has_web_interface(),
                    "web_routes": temp_instance.get_web_routes(),
                    "config": {},
                    "config_schema": temp_instance.get_config_schema()
                }
            else:
                continue
        
        plugins.append(plugin_info)
    
    return jsonify({"plugins": plugins})


@config_api_bp.route('/plugins/<plugin_key>/enable', methods=['POST'])
def enable_plugin(plugin_key: str):
    """Enable a plugin."""
    config_manager = get_config_manager()
    config = config_manager.config
    registry = get_registry()
    
    if plugin_key not in registry.plugin_classes:
        return jsonify({"error": "Plugin not found"}), 404
    
    if plugin_key not in config.plugins.enabled_plugins:
        config.plugins.enabled_plugins.append(plugin_key)
    
    try:
        _save_configuration(config_manager)
        
        # Create plugin instance if not exists
        if not registry.get_plugin(plugin_key):
            plugin = registry.create_plugin(plugin_key)
            if not plugin:
                return jsonify({"error": "Failed to create plugin instance"}), 500
        
        return jsonify({"success": True})
        
    except Exception as e:
        # Remove from enabled list on failure
        if plugin_key in config.plugins.enabled_plugins:
            config.plugins.enabled_plugins.remove(plugin_key)
        logger.error(f"Failed to enable plugin: {e}")
        return jsonify({"error": str(e)}), 500


@config_api_bp.route('/plugins/<plugin_key>/disable', methods=['POST'])
def disable_plugin(plugin_key: str):
    """Disable a plugin."""
    config_manager = get_config_manager()
    config = config_manager.config
    registry = get_registry()
    
    if plugin_key in config.plugins.enabled_plugins:
        config.plugins.enabled_plugins.remove(plugin_key)
    
    try:
        _save_configuration(config_manager)
        
        # Stop and remove plugin instance
        plugin = registry.get_plugin(plugin_key)
        if plugin:
            plugin.stop()
            del registry.plugin_instances[plugin_key]
        
        return jsonify({"success": True})
        
    except Exception as e:
        # Add back to enabled list on failure
        if plugin_key not in config.plugins.enabled_plugins:
            config.plugins.enabled_plugins.append(plugin_key)
        logger.error(f"Failed to disable plugin: {e}")
        return jsonify({"error": str(e)}), 500


@config_api_bp.route('/plugins/<plugin_key>/config', methods=['GET'])
def get_plugin_config(plugin_key: str):
    """Get plugin configuration."""
    config_manager = get_config_manager()
    registry = get_registry()
    
    # Get plugin configuration from file
    plugin_config = config_manager.get_plugin_config(plugin_key)
    
    # Get schema from plugin instance if available
    plugin = registry.get_plugin(plugin_key)
    schema = {}
    if plugin and hasattr(plugin, 'get_config_schema'):
        try:
            schema = plugin.get_config_schema()
        except Exception as e:
            logger.warning(f"Failed to get config schema for {plugin_key}: {e}")
    
    return jsonify({
        "config": plugin_config,
        "schema": schema
    })


@config_api_bp.route('/plugins/<plugin_key>/config', methods=['PUT'])
def update_plugin_config(plugin_key: str):
    """Update plugin configuration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No configuration data provided"}), 400
    
    config_manager = get_config_manager()
    registry = get_registry()
    
    try:
        # Save plugin configuration to its own file
        config_manager.save_plugin_config(plugin_key, data)
        
        # Update plugin instance if it exists
        plugin = registry.get_plugin(plugin_key)
        if plugin and hasattr(plugin, 'update_config'):
            try:
                plugin.update_config(data)
            except Exception as e:
                logger.warning(f"Plugin {plugin_key} failed to update config: {e}")
        
        return jsonify({"success": True})
            
    except Exception as e:
        logger.error(f"Failed to update plugin configuration: {e}")
        return jsonify({"error": str(e)}), 500


@config_api_bp.route('/app', methods=['GET'])
def get_app_config():
    """Get application configuration."""
    config_manager = get_config_manager()
    config = config_manager.config
    
    return jsonify({
        "app": {
            "debug": config.app.debug,
            "host": config.app.host,
            "port": config.app.port,
            "log_level": config.app.log_level,
            "log_file": config.app.log_file
        },
        "websocket": {
            "ping_interval": config.websocket.ping_interval,
            "broadcast_interval": config.websocket.broadcast_interval,
            "max_connections": config.websocket.max_connections
        },
        "security": {
            "enable_api_auth": config.security.enable_api_auth,
            "enable_cors": config.security.enable_cors
        }
    })


@config_api_bp.route('/app', methods=['PUT'])
def update_app_config():
    """Update application configuration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No configuration data provided"}), 400
    
    config_manager = get_config_manager()
    config = config_manager.config
    
    try:
        # Update app settings
        if 'app' in data:
            app_data = data['app']
            if 'log_level' in app_data:
                config.app.log_level = app_data['log_level']
            if 'log_file' in app_data:
                config.app.log_file = app_data['log_file']
        
        # Update WebSocket settings
        if 'websocket' in data:
            ws_data = data['websocket']
            if 'ping_interval' in ws_data:
                config.websocket.ping_interval = ws_data['ping_interval']
            if 'broadcast_interval' in ws_data:
                config.websocket.broadcast_interval = ws_data['broadcast_interval']
            if 'max_connections' in ws_data:
                config.websocket.max_connections = ws_data['max_connections']
        
        # Update security settings
        if 'security' in data:
            sec_data = data['security']
            if 'enable_api_auth' in sec_data:
                config.security.enable_api_auth = sec_data['enable_api_auth']
            if 'enable_cors' in sec_data:
                config.security.enable_cors = sec_data['enable_cors']
        
        _save_configuration(config_manager)
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Failed to update app configuration: {e}")
        return jsonify({"error": str(e)}), 500


def _save_configuration(config_manager):
    """Save configuration to file."""
    import toml
    import shutil
    from datetime import datetime
    
    if not config_manager.config_file:
        logger.error("No config file path available, cannot save configuration")
        return
    
    try:
        # Create backup of existing config
        backup_path = f"{config_manager.config_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if os.path.exists(config_manager.config_file):
            shutil.copy2(config_manager.config_file, backup_path)
            logger.info(f"Created backup: {backup_path}")
        
        # Convert configuration to TOML structure
        toml_data = _config_to_toml(config_manager.config)
        
        # Write to file
        with open(config_manager.config_file, 'w', encoding='utf-8') as f:
            toml.dump(toml_data, f)
        
        logger.info(f"Configuration saved to {config_manager.config_file}")
        
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise


def _config_to_toml(config):
    """Convert Configuration object to TOML-serializable dictionary."""
    toml_data = {}
    
    # App configuration
    toml_data['app'] = {
        'debug': config.app.debug,
        'secret_key': config.app.secret_key,
        'host': config.app.host,
        'port': config.app.port,
        'log_level': config.app.log_level,
        'log_file': config.app.log_file
    }
    
    # Security configuration
    toml_data['security'] = {
        'enable_api_auth': config.security.enable_api_auth,
        'api_key_header': config.security.api_key_header,
        'jwt_secret': config.security.jwt_secret,
        'session_timeout': config.security.session_timeout,
        'enable_cors': config.security.enable_cors,
        'allowed_origins': config.security.allowed_origins
    }
    
    # WebSocket configuration
    toml_data['websocket'] = {
        'ping_interval': config.websocket.ping_interval,
        'broadcast_interval': config.websocket.broadcast_interval,
        'max_connections': config.websocket.max_connections
    }
    
    # Radio configuration
    toml_data['radios'] = {
        'instances': []
    }
    
    for radio in config.radios.instances:
        radio_data = {
            'id': radio.id,
            'name': radio.name,
            'driver_type': radio.driver_type,
            'enabled': radio.enabled,
            'config': radio.config
        }
        toml_data['radios']['instances'].append(radio_data)
    
    # Plugin configuration (only general settings, not plugin-specific configs)
    toml_data['plugins'] = {
        'auto_discover': config.plugins.auto_discover,
        'enabled_plugins': config.plugins.enabled_plugins,
        'config_dir': config.plugins.config_dir
    }
    
    # Systemd configuration
    toml_data['systemd'] = {
        'service_template': config.systemd.service_template,
        'enable_status_check': config.systemd.enable_status_check,
        'service_timeout': config.systemd.service_timeout
    }
    
    # Paths configuration
    toml_data['paths'] = {
        'radios_dir': config.paths.radios_dir,
        'plugins_dir': config.paths.plugins_dir,
        'config_dir': config.paths.config_dir,
        'templates_dir': config.paths.templates_dir,
        'static_dir': config.paths.static_dir
    }
    
    return toml_data
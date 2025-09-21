#!/usr/bin/env python3
"""RIG Remote Control Web Application."""

import logging
import sys
import os
from pathlib import Path
from flask import Flask, render_template
from flask_sock import Sock

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.registry import Registry
from core.events import event_bus
from core.config import init_config, get_config
from web.api import api_bp
from web.config_api import config_api_bp
from web.ws import init_websocket, setup_event_listeners, start_background_broadcaster

logger = logging.getLogger(__name__)


def setup_logging(config):
    """Setup logging based on configuration."""
    log_level = getattr(logging, config.app.log_level.upper())
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure handlers
    if config.app.log_file:
        # File logging
        handler = logging.FileHandler(config.app.log_file)
    else:
        # Console logging
        handler = logging.StreamHandler(sys.stdout)
    
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def create_app(config_file: str = None):
    """Create and configure the Flask application."""
    # Initialize configuration
    config_manager = init_config(config_file)
    config = get_config()
    
    # Setup logging first
    setup_logging(config)
    logger.info("Starting RIG Remote Control Application")
    
    # Create Flask app with configured paths
    app = Flask(__name__, 
                template_folder=config.paths.templates_dir,
                static_folder=config.paths.static_dir)
    
    # Apply Flask configuration
    app.config['SECRET_KEY'] = config.app.secret_key
    app.config['DEBUG'] = config.app.debug
    app.config['CONFIG'] = config
    app.config['CONFIG_MANAGER'] = config_manager
    
    # Initialize components
    registry = Registry(config_manager)
    app.config['REGISTRY'] = registry
    
    # Discover and load radio drivers and plugins
    logger.info("Discovering radio drivers and plugins...")
    registry.discover_drivers(config.paths.radios_dir)
    registry.discover_plugins(config.paths.plugins_dir)
    
    # Debug: Log discovered drivers
    logger.info(f"Discovered radio drivers: {list(registry.radio_drivers.keys())}")
    logger.info(f"Discovered plugins: {list(registry.plugin_classes.keys())}")
    
    # Create radio instances from configuration
    logger.info("Creating radio instances from configuration...")
    for radio_config in config.radios.instances:
        if radio_config.enabled:
            logger.info(f"Creating radio: {radio_config.id} ({radio_config.driver_type})")
            
            # Check if driver type exists
            if radio_config.driver_type not in registry.radio_drivers:
                logger.error(f"Radio driver '{radio_config.driver_type}' not found for radio {radio_config.id}")
                logger.error(f"Available drivers: {list(registry.radio_drivers.keys())}")
                continue
            
            radio = registry.create_radio(
                radio_config.id,
                radio_config.driver_type,
                radio_config.name,
                radio_config.config
            )
            if radio:
                try:
                    radio.connect()
                    logger.info(f"Connected radio: {radio_config.id}")
                except Exception as e:
                    logger.error(f"Failed to connect radio {radio_config.id}: {e}")
            else:
                logger.error(f"Failed to create radio {radio_config.id}")
        else:
            logger.info(f"Skipping disabled radio: {radio_config.id}")
    
    # Create plugin instances from configuration
    logger.info("Creating plugin instances...")
    if config.plugins.auto_discover:
        # Auto-create all discovered plugins
        for plugin_key in registry.list_plugins():
            if not config.plugins.enabled_plugins or plugin_key in config.plugins.enabled_plugins:
                plugin = registry.create_plugin(plugin_key)
                if plugin:
                    logger.info(f"Created plugin: {plugin_key}")
                else:
                    logger.error(f"Failed to create plugin: {plugin_key}")
    else:
        # Only create explicitly enabled plugins
        for plugin_key in config.plugins.enabled_plugins:
            plugin = registry.create_plugin(plugin_key)
            if plugin:
                logger.info(f"Created plugin: {plugin_key}")
            else:
                logger.error(f"Failed to create plugin: {plugin_key}")
    
    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(config_api_bp)
    
    # Register plugin web interfaces
    for plugin_key in registry.list_plugins():
        plugin = registry.get_plugin(plugin_key)
        if plugin and plugin.has_web_interface():
            try:
                plugin.register_web_routes(app)
                logger.info(f"Registered web interface for plugin: {plugin_key}")
            except Exception as e:
                logger.error(f"Failed to register web interface for plugin {plugin_key}: {e}")
    
    # Initialize WebSocket support
    sock = Sock(app)
    init_websocket(app, sock)
    
    # Setup event listeners for WebSocket broadcasting
    setup_event_listeners()
    
    # Start background broadcaster for real-time updates
    start_background_broadcaster(app, interval=config.websocket.broadcast_interval)
    
    # Main route
    @app.route('/')
    def index():
        return render_template('index.html')
    
    # Health check route
    @app.route('/health')
    def health():
        return {
            "status": "ok", 
            "radios": len(registry.list_radios()),
            "plugins": len(registry.list_plugins()),
            "config_file": config_manager.config_file or "default"
        }
    
    # Configuration info route (for debugging)
    @app.route('/config-info')
    def config_info():
        if not config.app.debug:
            return {"error": "Not available in production"}, 403
        
        return {
            "config_file": config_manager.config_file,
            "app": {
                "debug": config.app.debug,
                "host": config.app.host,
                "port": config.app.port,
                "log_level": config.app.log_level
            },
            "radios": {
                "count": len(config.radios.instances),
                "enabled": len([r for r in config.radios.instances if r.enabled])
            },
            "plugins": {
                "auto_discover": config.plugins.auto_discover,
                "enabled_count": len(config.plugins.enabled_plugins)
            }
        }
    
    logger.info("Application initialized successfully")
    return app


def main():
    """Main entry point."""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='RIG Remote Control Web Application')
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--host', help='Host address (overrides config)')
    parser.add_argument('--port', type=int, help='Port number (overrides config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Set environment variables from command line arguments
    if args.host:
        os.environ['RIG_HOST'] = args.host
    if args.port:
        os.environ['RIG_PORT'] = str(args.port)
    if args.debug:
        os.environ['RIG_DEBUG'] = 'true'
    
    # Create application
    app = create_app(args.config)
    config = get_config()
    
    # Run the application
    try:
        logger.info(f"Starting RIG Remote Control Web Application on {config.app.host}:{config.app.port}")
        app.run(
            host=config.app.host,
            port=config.app.port,
            debug=config.app.debug,
            use_reloader=False  # Disable reloader to prevent double initialization
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
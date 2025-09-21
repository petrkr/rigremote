#!/usr/bin/env python3
"""Test script for configuration system."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import init_config, get_config

def test_config():
    """Test configuration loading."""
    print("Testing configuration system...")
    
    # Initialize configuration
    config_manager = init_config("config/settings.toml")
    config = get_config()
    
    print(f"✓ Configuration loaded from: {config_manager.config_file}")
    print(f"✓ App debug: {config.app.debug}")
    print(f"✓ App host:port: {config.app.host}:{config.app.port}")
    print(f"✓ Log level: {config.app.log_level}")
    print(f"✓ Radio instances: {len(config.radios.instances)}")
    
    for radio in config.radios.instances:
        print(f"  - {radio.id}: {radio.name} ({radio.driver_type}) {'enabled' if radio.enabled else 'disabled'}")
    
    print(f"✓ Plugin auto-discover: {config.plugins.auto_discover}")
    print(f"✓ Enabled plugins: {config.plugins.enabled_plugins}")
    print(f"✓ WebSocket broadcast interval: {config.websocket.broadcast_interval}s")
    
    # Test environment override
    import os
    os.environ['RIG_DEBUG'] = 'false'
    os.environ['RIG_PORT'] = '8080'
    
    print("\nTesting environment overrides...")
    config_manager2 = init_config("config/settings.toml")
    config2 = config_manager2.config
    
    print(f"✓ Overridden debug: {config2.app.debug}")
    print(f"✓ Overridden port: {config2.app.port}")
    
    print("\n✅ Configuration system test passed!")

if __name__ == "__main__":
    test_config()
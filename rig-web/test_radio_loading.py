#!/usr/bin/env python3
"""Test script to verify radio loading and configuration."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import init_config, get_config
from core.registry import Registry

def test_radio_loading():
    """Test radio discovery and loading."""
    print("Testing radio loading system...")
    
    # Initialize configuration
    config_manager = init_config("config/settings.toml")
    config = get_config()
    
    print(f"✓ Configuration loaded from: {config_manager.config_file}")
    print(f"✓ Found {len(config.radios.instances)} radio(s) in configuration")
    
    # Initialize registry
    registry = Registry()
    
    # Discover drivers
    print("\nDiscovering radio drivers...")
    registry.discover_drivers(config.paths.radios_dir)
    
    print(f"✓ Discovered radio drivers: {list(registry.radio_drivers.keys())}")
    
    # Create radio instances from configuration
    print("\nCreating radio instances from configuration...")
    for radio_config in config.radios.instances:
        print(f"\nProcessing radio: {radio_config.id}")
        print(f"  - Name: {radio_config.name}")
        print(f"  - Type: {radio_config.driver_type}")
        print(f"  - Enabled: {radio_config.enabled}")
        print(f"  - Config: {radio_config.config}")
        
        if radio_config.enabled:
            if radio_config.driver_type in registry.radio_drivers:
                radio = registry.create_radio(
                    radio_config.id,
                    radio_config.driver_type,
                    radio_config.name,
                    radio_config.config
                )
                if radio:
                    print(f"  ✓ Created radio instance")
                    try:
                        radio.connect()
                        print(f"  ✓ Connected successfully")
                        
                        # Test radio functionality
                        state = radio.get_state()
                        print(f"  ✓ Radio state: {state}")
                        
                        radio.disconnect()
                        print(f"  ✓ Disconnected")
                    except Exception as e:
                        print(f"  ✗ Connection failed: {e}")
                else:
                    print(f"  ✗ Failed to create radio instance")
            else:
                print(f"  ✗ Driver type '{radio_config.driver_type}' not found")
                print(f"      Available: {list(registry.radio_drivers.keys())}")
        else:
            print(f"  - Skipped (disabled)")
    
    # Test radio listing
    print(f"\n✓ Active radios in registry: {registry.list_radios()}")
    
    print("\n✅ Radio loading test completed!")

if __name__ == "__main__":
    test_radio_loading()
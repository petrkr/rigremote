"""Fake radio driver for testing and demonstration."""

import random
import time
import threading
from typing import Dict, Any

from core.interfaces.radio_driver import RadioDriver


class FakeRadio(RadioDriver):
    """Simulated radio for testing purposes."""
    
    DRIVER_TYPE = "fake"
    DISPLAY_NAME = "Demo Radio (Fake)"
    
    def __init__(self, radio_id: str, name: str, config: Dict[str, Any]):
        super().__init__(radio_id, name, config)
        
        # Internal state
        self._frequency = config.get('default_frequency', 145500000)  # 145.5 MHz (2m band)
        self._mode = config.get('default_mode', "FM")
        self._ptt = False
        self._rssi = -80  # dBm
        self._modes = ["FM", "AM", "USB", "LSB", "CW"]
        
        # Simulation thread
        self._simulation_thread = None
        self._stop_simulation = threading.Event()
    
    @classmethod
    def get_config_schema(cls):
        """Return configuration schema for this driver."""
        return {
            "default_frequency": {
                "type": "integer",
                "title": "Default Frequency (Hz)",
                "description": "Starting frequency for the fake radio",
                "default": 145500000,
                "minimum": 1000000,
                "maximum": 30000000000
            },
            "default_mode": {
                "type": "string",
                "title": "Default Mode",
                "description": "Starting mode for the fake radio",
                "default": "FM",
                "enum": ["FM", "AM", "USB", "LSB", "CW"]
            },
            "rssi_range": {
                "type": "object",
                "title": "RSSI Range",
                "description": "Range for random RSSI simulation",
                "properties": {
                    "min": {"type": "integer", "default": -120},
                    "max": {"type": "integer", "default": -40}
                },
                "default": {"min": -120, "max": -40}
            }
        }
    
    def connect(self) -> None:
        """Simulate connection to radio."""
        if not self._connected:
            # Simulate connection delay
            time.sleep(0.1)
            self._connected = True
            
            # Start RSSI simulation
            self._start_simulation()
            
    def disconnect(self) -> None:
        """Simulate disconnection from radio."""
        if self._connected:
            self._connected = False
            self._stop_simulation.set()
            
            if self._simulation_thread and self._simulation_thread.is_alive():
                self._simulation_thread.join(timeout=1.0)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current radio state."""
        return {
            "frequency": self._frequency,
            "mode": self._mode,
            "ptt": self._ptt,
            "rssi": self._rssi,
            "connected": self._connected,
            "available_modes": self._modes
        }
    
    def set_frequency(self, hz: int) -> None:
        """Set radio frequency."""
        if not self._connected:
            raise RuntimeError("Radio not connected")
            
        # Validate frequency range (arbitrary limits for demo)
        if hz < 1000000 or hz > 30000000000:  # 1 MHz to 30 GHz
            raise ValueError(f"Frequency {hz} Hz out of range")
            
        self._frequency = hz
        
        # Simulate frequency-dependent RSSI change
        self._update_rssi_for_frequency()
    
    def set_mode(self, mode: str) -> None:
        """Set radio mode."""
        if not self._connected:
            raise RuntimeError("Radio not connected")
            
        if mode not in self._modes:
            raise ValueError(f"Invalid mode: {mode}. Available: {', '.join(self._modes)}")
            
        self._mode = mode
    
    def ptt(self, on: bool) -> None:
        """Control Push-to-Talk."""
        if not self._connected:
            raise RuntimeError("Radio not connected")
            
        self._ptt = on
        
        # Simulate RSSI change during PTT
        if on:
            self._rssi = 0  # Strong signal when transmitting
        else:
            self._update_rssi_for_frequency()
    
    def _start_simulation(self) -> None:
        """Start background simulation thread."""
        self._stop_simulation.clear()
        self._simulation_thread = threading.Thread(target=self._simulate_rssi, daemon=True)
        self._simulation_thread.start()
    
    def _simulate_rssi(self) -> None:
        """Simulate changing RSSI values."""
        while not self._stop_simulation.wait(1.0):  # Update every second
            if self._connected and not self._ptt:
                # Add some random variation to RSSI
                variation = random.uniform(-5, 5)
                base_rssi = self._get_base_rssi_for_frequency()
                self._rssi = int(base_rssi + variation)
    
    def _get_base_rssi_for_frequency(self) -> float:
        """Get base RSSI for current frequency (simulates propagation)."""
        # Simple simulation: higher frequencies have weaker signals
        if self._frequency < 50000000:  # HF
            return random.uniform(-70, -40)
        elif self._frequency < 200000000:  # VHF
            return random.uniform(-80, -50)
        else:  # UHF and above
            return random.uniform(-90, -60)
    
    def _update_rssi_for_frequency(self) -> None:
        """Update RSSI when frequency changes."""
        if not self._ptt:
            self._rssi = int(self._get_base_rssi_for_frequency())
"""Fake radio driver for testing and demonstration."""

import random
import time
import threading
from typing import Dict, Any
import Hamlib

from core.interfaces.radio_driver import RadioDriver

HAMLIB_MODE_MAP = {
    Hamlib.RIG_MODE_USB: "USB",
    Hamlib.RIG_MODE_LSB: "LSB",
    Hamlib.RIG_MODE_CW: "CW",
    Hamlib.RIG_MODE_CWR: "CWR",
    Hamlib.RIG_MODE_AM: "AM",
    Hamlib.RIG_MODE_FM: "FM",
    Hamlib.RIG_MODE_WFM: "WFM",
    Hamlib.RIG_MODE_RTTY: "RTTY"
}

class HamlibNetRadio(RadioDriver):
    """Hamlib radio"""
    
    DRIVER_TYPE = "hamlib"
    DISPLAY_NAME = "Hamlib"
    
    def __init__(self, radio_id: str, name: str, config: Dict[str, Any]):
        super().__init__(radio_id, name, config)

        rig_address = config.get('address', "127.0.0.1")

        Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)

        self._rig = Hamlib.Rig(Hamlib.RIG_MODEL_NETRIGCTL)
        self._rig.set_conf("rig_pathname", rig_address)

        self._ptt = False
        self._frequency = 0
        self._mode = [0, 0]
        self._rssi = 0
        self._modes = ["FM", "AM", "USB", "LSB"] # TODO: Read from Hamlib


        # Reading thread
        self._thread = None
        self._stopthread = threading.Event()
    
    @classmethod
    def get_config_schema(cls):
        """Return configuration schema for this driver."""
        return {
            "address": {
                "type": "string",
                "title": "Hamlib address",
                "description": "IP or hostname of rigctld",
                "default": "127.0.0.1"
            }
        }

    def connect(self) -> None:
        """Connect to radio."""
        if not self._connected:
            self._rig.open()
            print(f"Connected to rig")
            print(f"Rig model: {self._rig.get_info()}")
            print(f"Rig frequency: {self._rig.get_freq()} Hz")
            print(f"Rig mode: {self._rig.get_mode()}")
            print(f"Rig power: {int(self._rig.get_level_f('RFPOWER') * 100)} W")

            self._start()
            self._connected = True

            
    def disconnect(self) -> None:
        """Simulate disconnection from radio."""
        if self._connected:
            self._stopthread.set()

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            
            self._rig.close()
            self._connected = False


    def get_state(self) -> Dict[str, Any]:
        """Get current radio state."""
        mode, bandwidth = self._mode

        return {
            "frequency": self._frequency,
            "mode": HAMLIB_MODE_MAP.get(mode, f"Unknown({mode})"),
            "ptt": self._ptt,
            "rssi": self._rssi,
            "connected": self._connected,
            "available_modes": self._modes
        }


    def set_frequency(self, hz: int) -> None:
        """Set radio frequency."""
        if not self._connected:
            raise RuntimeError("Radio not connected")

        self._rig.set_freq(Hamlib.RIG_VFO_CURR, hz)
        self._update_rssi_for_frequency()


    def set_mode(self, mode: str) -> None:
        """Set radio mode."""
        if not self._connected:
            raise RuntimeError("Radio not connected")
            
        if mode not in self._modes:
            raise ValueError(f"Invalid mode: {mode}. Available: {', '.join(self._modes)}")

        self._rig.set_mode(mode)
        self._mode = mode


    def ptt(self, on: bool) -> None:
        """Control Push-to-Talk."""
        if not self._connected:
            raise RuntimeError("Radio not connected")
            
        self._rig.set_ptt(Hamlib.RIG_VFO_CURR, Hamlib.RIG_PTT_ON if on else Hamlib.RIG_PTT_OFF)


    def _start(self) -> None:
        """Start background thread."""
        self._stopthread.clear()
        self._thread = threading.Thread(target=self._read_rig, daemon=True)
        self._thread.start()


    def _read_rig(self) -> None:
        """Reading RIG status"""
        while not self._stopthread.wait(1.0):  # Update every second
            if self._connected:
                self._ptt = self._rig.get_ptt(Hamlib.RIG_VFO_CURR)
                self._rssi = self._rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH)
                self._frequency = self._rig.get_freq()
                self._mode = self._rig.get_mode()


    def _update_rssi_for_frequency(self) -> None:
        """Update RSSI when frequency changes."""
        self._rssi = self._rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH)
"""Abstract base class for radio drivers."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class RadioDriver(ABC):
    """Common interface for radio drivers."""
    
    def __init__(self, radio_id: str, name: str, config: Dict[str, Any]):
        self.id = radio_id
        self.name = name
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Connect to the radio."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the radio."""
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get current radio state (frequency, mode, ptt, rssi, etc.)."""
        pass

    @abstractmethod
    def set_frequency(self, hz: int) -> None:
        """Set radio frequency in Hz."""
        pass

    @abstractmethod
    def set_mode(self, mode: str) -> None:
        """Set radio mode (FM, AM, USB, LSB, etc.)."""
        pass

    @abstractmethod
    def ptt(self, on: bool) -> None:
        """Control Push-to-Talk."""
        pass

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected
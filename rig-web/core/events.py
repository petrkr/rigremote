"""Simple event system for radio and plugin events."""

import logging
from typing import Dict, Any, Callable, List
from threading import Lock

logger = logging.getLogger(__name__)


class EventBus:
    """Simple event bus for broadcasting events between components."""
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = Lock()
    
    def subscribe(self, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe to an event."""
        with self._lock:
            if event_name not in self._listeners:
                self._listeners[event_name] = []
            self._listeners[event_name].append(callback)
            logger.debug(f"Subscribed to event '{event_name}'")
    
    def unsubscribe(self, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Unsubscribe from an event."""
        with self._lock:
            if event_name in self._listeners:
                try:
                    self._listeners[event_name].remove(callback)
                    logger.debug(f"Unsubscribed from event '{event_name}'")
                except ValueError:
                    pass
    
    def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Emit an event to all subscribers."""
        with self._lock:
            listeners = self._listeners.get(event_name, []).copy()
        
        logger.debug(f"Emitting event '{event_name}' to {len(listeners)} listeners")
        
        for callback in listeners:
            try:
                callback(payload)
            except Exception as e:
                logger.error(f"Error in event callback for '{event_name}': {e}")


# Global event bus instance
event_bus = EventBus()
"""WebSocket support for real-time radio updates."""

import json
import logging
import threading
import time
from typing import Set, Dict, Any
from flask import request, current_app
from flask_sock import Sock

logger = logging.getLogger(__name__)

# WebSocket connections registry
ws_connections: Set = set()
ws_lock = threading.Lock()


def init_websocket(app, sock: Sock):
    """Initialize WebSocket support with Flask-Sock."""
    
    @sock.route('/ws')
    def websocket_handler(ws):
        """Handle WebSocket connections."""
        client_id = f"{request.remote_addr}:{request.environ.get('REMOTE_PORT', 'unknown')}"
        logger.info(f"WebSocket client connected: {client_id}")
        
        # TODO: Add authentication here when implementing security
        # if not authenticate_websocket_client(ws):
        #     ws.close(code=4001, message="Authentication required")
        #     return
        
        # Register connection
        with ws_lock:
            ws_connections.add(ws)
        
        try:
            # Send initial state
            _send_initial_state(ws)
            
            # Handle incoming messages
            while True:
                try:
                    message = ws.receive(timeout=1.0)
                    if message:
                        _handle_websocket_message(ws, message)
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        logger.error(f"WebSocket error for {client_id}: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"WebSocket connection error for {client_id}: {e}")
        finally:
            # Unregister connection
            with ws_lock:
                ws_connections.discard(ws)
            logger.info(f"WebSocket client disconnected: {client_id}")


def _send_initial_state(ws):
    """Send initial radio and plugin state to new WebSocket client."""
    try:
        registry = current_app.config['REGISTRY']
        
        # Send radio list and states
        radios_data = []
        for radio_id in registry.list_radios():
            radio = registry.get_radio(radio_id)
            if radio:
                try:
                    state = radio.get_state()
                    radios_data.append({
                        "id": radio.id,
                        "name": radio.name,
                        "connected": radio.connected,
                        **state
                    })
                except Exception as e:
                    logger.error(f"Error getting initial state for radio {radio_id}: {e}")
        
        _send_to_client(ws, {
            "type": "initial_state",
            "radios": radios_data,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error sending initial state: {e}")


def _handle_websocket_message(ws, message: str):
    """Handle incoming WebSocket messages from client."""
    try:
        data = json.loads(message)
        msg_type = data.get("type")
        
        # TODO: Add authorization check for message types
        # if not authorize_websocket_action(ws, msg_type, data):
        #     _send_error(ws, "Unauthorized action")
        #     return
        
        if msg_type == "ping":
            _send_to_client(ws, {"type": "pong", "timestamp": time.time()})
            
        elif msg_type == "subscribe_radio":
            # Client wants updates for specific radio
            radio_id = data.get("radio_id")
            if radio_id:
                _send_to_client(ws, {
                    "type": "subscription_ack",
                    "radio_id": radio_id,
                    "subscribed": True
                })
                
        elif msg_type == "unsubscribe_radio":
            # Client no longer wants updates for specific radio
            radio_id = data.get("radio_id")
            if radio_id:
                _send_to_client(ws, {
                    "type": "subscription_ack", 
                    "radio_id": radio_id,
                    "subscribed": False
                })
                
        else:
            logger.warning(f"Unknown WebSocket message type: {msg_type}")
            _send_error(ws, f"Unknown message type: {msg_type}")
            
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in WebSocket message: {message}")
        _send_error(ws, "Invalid JSON format")
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        _send_error(ws, "Internal server error")


def _send_to_client(ws, data: Dict[str, Any]):
    """Send data to specific WebSocket client."""
    try:
        message = json.dumps(data)
        ws.send(message)
    except Exception as e:
        logger.error(f"Error sending WebSocket message: {e}")


def _send_error(ws, error_message: str):
    """Send error message to WebSocket client."""
    _send_to_client(ws, {
        "type": "error",
        "message": error_message,
        "timestamp": time.time()
    })


def broadcast_to_all_clients(data: Dict[str, Any]):
    """Broadcast message to all connected WebSocket clients."""
    if not ws_connections:
        return
        
    message = json.dumps(data)
    disconnected = set()
    
    with ws_lock:
        for ws in ws_connections.copy():
            try:
                ws.send(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket client: {e}")
                disconnected.add(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            ws_connections.discard(ws)


def broadcast_radio_state_change(radio_id: str, state: Dict[str, Any]):
    """Broadcast radio state change to all WebSocket clients."""
    broadcast_to_all_clients({
        "type": "radio_state_changed",
        "radio_id": radio_id,
        "state": state,
        "timestamp": time.time()
    })


def broadcast_plugin_event(plugin_key: str, event_type: str, data: Dict[str, Any] = None):
    """Broadcast plugin event to all WebSocket clients."""
    broadcast_to_all_clients({
        "type": "plugin_event",
        "plugin_key": plugin_key,
        "event_type": event_type,
        "data": data or {},
        "timestamp": time.time()
    })


# Event bus integration
def setup_event_listeners():
    """Setup event bus listeners for WebSocket broadcasting."""
    from core.events import event_bus
    
    def handle_radio_event(payload: Dict[str, Any]):
        """Handle radio events from event bus."""
        event_type = payload.get("event_type", "unknown")
        radio_id = payload.get("radio_id")
        
        if radio_id:
            # Get current radio state and broadcast
            try:
                from flask import current_app
                registry = current_app.config['REGISTRY']
                radio = registry.get_radio(radio_id)
                if radio:
                    state = radio.get_state()
                    broadcast_radio_state_change(radio_id, state)
            except Exception as e:
                logger.error(f"Error broadcasting radio state change: {e}")
    
    def handle_plugin_event(payload: Dict[str, Any]):
        """Handle plugin events from event bus."""
        plugin_key = payload.get("plugin_key")
        event_type = payload.get("event_type", "unknown")
        data = payload.get("data", {})
        
        if plugin_key:
            broadcast_plugin_event(plugin_key, event_type, data)
    
    # Subscribe to events
    event_bus.subscribe("radio_frequency_changed", handle_radio_event)
    event_bus.subscribe("radio_mode_changed", handle_radio_event)
    event_bus.subscribe("radio_ptt_changed", handle_radio_event)
    event_bus.subscribe("plugin_event", handle_plugin_event)


# Background state broadcaster (optional)
def start_background_broadcaster(app, interval: float = 2.0):
    """Start background thread to broadcast radio states periodically."""
    
    def broadcast_loop():
        """Background loop to broadcast radio states."""
        while True:
            try:
                with app.app_context():
                    if ws_connections:
                        registry = app.config['REGISTRY']
                        
                        for radio_id in registry.list_radios():
                            radio = registry.get_radio(radio_id)
                            if radio and radio.connected:
                                try:
                                    state = radio.get_state()
                                    broadcast_radio_state_change(radio_id, state)
                                except Exception as e:
                                    logger.error(f"Error in background broadcast for {radio_id}: {e}")
                    
                    time.sleep(interval)
                    
            except Exception as e:
                logger.error(f"Error in background broadcaster: {e}")
                time.sleep(interval)
    
    # Start background thread
    thread = threading.Thread(target=broadcast_loop, daemon=True)
    thread.start()
    logger.info(f"Started background WebSocket broadcaster (interval: {interval}s)")


# TODO: Authentication and authorization functions for future implementation
def authenticate_websocket_client(ws) -> bool:
    """Authenticate WebSocket client (placeholder for future implementation)."""
    # TODO: Implement API key or JWT token validation
    # Example:
    # token = request.headers.get('Authorization')
    # return validate_api_token(token)
    return True


def authorize_websocket_action(ws, action_type: str, data: Dict[str, Any]) -> bool:
    """Authorize WebSocket action (placeholder for future implementation)."""
    # TODO: Implement action-based authorization
    # Example:
    # user_role = get_user_role_from_websocket(ws)
    # return check_permission(user_role, action_type)
    return True
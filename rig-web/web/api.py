"""REST API Blueprint for radio control."""

import logging
import subprocess
import platform
from flask import Blueprint, jsonify, request, current_app
from typing import Dict, Any

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_registry():
    """Get registry from Flask app context."""
    return current_app.config['REGISTRY']


@api_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "version": "1.0.0"})


@api_bp.route('/radios', methods=['GET'])
def list_radios():
    """List all radios and their basic state."""
    registry = get_registry()
    radios = []
    
    for radio_id in registry.list_radios():
        radio = registry.get_radio(radio_id)
        if radio:
            try:
                state = radio.get_state()
                radios.append({
                    "id": radio.id,
                    "name": radio.name,
                    "connected": radio.connected,
                    "frequency": state.get("frequency"),
                    "mode": state.get("mode"),
                    "ptt": state.get("ptt", False)
                })
            except Exception as e:
                logger.error(f"Error getting state for radio {radio_id}: {e}")
                radios.append({
                    "id": radio.id,
                    "name": radio.name,
                    "connected": False,
                    "error": str(e)
                })
    
    return jsonify({"radios": radios})


@api_bp.route('/radios/<radio_id>', methods=['GET'])
def get_radio_state(radio_id: str):
    """Get detailed state of a specific radio."""
    registry = get_registry()
    radio = registry.get_radio(radio_id)
    
    if not radio:
        return jsonify({"error": "Radio not found"}), 404
    
    try:
        state = radio.get_state()
        return jsonify({
            "id": radio.id,
            "name": radio.name,
            "connected": radio.connected,
            **state
        })
    except Exception as e:
        logger.error(f"Error getting state for radio {radio_id}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/radios/<radio_id>/frequency', methods=['POST'])
def set_radio_frequency(radio_id: str):
    """Set radio frequency."""
    registry = get_registry()
    radio = registry.get_radio(radio_id)
    
    if not radio:
        return jsonify({"error": "Radio not found"}), 404
    
    data = request.get_json()
    if not data or 'hz' not in data:
        return jsonify({"error": "Missing 'hz' field"}), 400
    
    try:
        hz = int(data['hz'])
        radio.set_frequency(hz)
        
        # Broadcast event
        registry.broadcast_event('radio_frequency_changed', {
            'radio_id': radio_id,
            'frequency': hz
        })
        
        return jsonify({"success": True, "frequency": hz})
    except ValueError as e:
        return jsonify({"error": f"Invalid frequency: {e}"}), 400
    except Exception as e:
        logger.error(f"Error setting frequency for radio {radio_id}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/radios/<radio_id>/mode', methods=['POST'])
def set_radio_mode(radio_id: str):
    """Set radio mode."""
    registry = get_registry()
    radio = registry.get_radio(radio_id)
    
    if not radio:
        return jsonify({"error": "Radio not found"}), 404
    
    data = request.get_json()
    if not data or 'mode' not in data:
        return jsonify({"error": "Missing 'mode' field"}), 400
    
    try:
        mode = data['mode']
        radio.set_mode(mode)
        
        # Broadcast event
        registry.broadcast_event('radio_mode_changed', {
            'radio_id': radio_id,
            'mode': mode
        })
        
        return jsonify({"success": True, "mode": mode})
    except ValueError as e:
        return jsonify({"error": f"Invalid mode: {e}"}), 400
    except Exception as e:
        logger.error(f"Error setting mode for radio {radio_id}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/radios/<radio_id>/ptt', methods=['POST'])
def set_radio_ptt(radio_id: str):
    """Control radio PTT."""
    registry = get_registry()
    radio = registry.get_radio(radio_id)
    
    if not radio:
        return jsonify({"error": "Radio not found"}), 404
    
    data = request.get_json()
    if not data or 'on' not in data:
        return jsonify({"error": "Missing 'on' field"}), 400
    
    try:
        ptt_on = bool(data['on'])
        radio.ptt(ptt_on)
        
        # Broadcast event
        registry.broadcast_event('radio_ptt_changed', {
            'radio_id': radio_id,
            'ptt': ptt_on
        })
        
        return jsonify({"success": True, "ptt": ptt_on})
    except Exception as e:
        logger.error(f"Error setting PTT for radio {radio_id}: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/plugins', methods=['GET'])
def list_plugins():
    """List all plugins and their status."""
    registry = get_registry()
    plugins = []
    
    # Available plugins
    for plugin_key in registry.list_plugins():
        plugin = registry.get_plugin(plugin_key)
        if plugin:
            plugins.append({
                "key": plugin.key,
                "label": plugin.label,
                "enabled": plugin.enabled,
                "external_service": plugin.is_external_service(),
                "service_name": plugin.external_service_name()
            })
        else:
            plugin_class = registry.plugin_classes.get(plugin_key)
            if plugin_class:
                temp_instance = plugin_class(registry)
                plugins.append({
                    "key": temp_instance.key,
                    "label": temp_instance.label,
                    "enabled": False,
                    "external_service": temp_instance.is_external_service(),
                    "service_name": temp_instance.external_service_name()
                })
    
    return jsonify({"plugins": plugins})


@api_bp.route('/plugin-cards', methods=['GET'])
def get_plugin_cards():
    """Get plugin card information for main page."""
    registry = get_registry()
    cards = []
    
    for plugin_key in registry.list_plugins():
        plugin = registry.get_plugin(plugin_key)
        if plugin and plugin.enabled and plugin.has_main_interface():
            try:
                card_info = plugin.get_card_info()
                card_info.update({
                    "key": plugin.key,
                    "main_url": plugin.get_main_routes(),
                    "settings_url": plugin.get_settings_routes() if plugin.has_settings_interface() else None
                })
                cards.append(card_info)
            except Exception as e:
                logger.error(f"Failed to get card info for plugin {plugin_key}: {e}")
    
    return jsonify({"cards": cards})


@api_bp.route('/plugins/<plugin_key>/status', methods=['GET'])
def get_plugin_status(plugin_key: str):
    """Get plugin status (including systemd service status if external)."""
    registry = get_registry()
    
    # Check if plugin class exists
    if plugin_key not in registry.plugin_classes:
        return jsonify({"error": "Plugin not found"}), 404
    
    plugin = registry.get_plugin(plugin_key)
    if not plugin:
        # Create temporary instance to get service info
        plugin_class = registry.plugin_classes[plugin_key]
        plugin = plugin_class(registry)
    
    result = {
        "key": plugin.key,
        "label": plugin.label,
        "enabled": plugin.enabled,
        "external_service": plugin.is_external_service()
    }
    
    # Check systemd service status if external
    if plugin.is_external_service() and platform.system() == "Linux":
        service_name = plugin.external_service_name()
        if service_name:
            try:
                result_cmd = subprocess.run(
                    ['systemctl', 'is-active', service_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                result["systemd_status"] = result_cmd.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                result["systemd_status"] = "unknown"
            except Exception as e:
                logger.error(f"Error checking systemd status for {service_name}: {e}")
                result["systemd_status"] = "error"
    
    return jsonify(result)

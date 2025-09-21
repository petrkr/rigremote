"""Scheduled transmitter plugin with CSV editor and per-rig daemon support."""

import os
import logging
import shutil
from glob import glob
from pathlib import Path
from flask import Blueprint, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import pandas as pd
from core.interfaces.plugin_module import PluginModule

logger = logging.getLogger(__name__)


class ScheduledTransmitter(PluginModule):
    """Plugin for scheduled radio transmissions with CSV editor and per-rig daemon configuration."""
    
    # Plugin configuration schema with defaults
    PLUGIN_CONFIG_SCHEMA = {
        "transmission_path": {
            "type": "string",
            "title": "Transmission Path", 
            "description": "Directory containing transmission sets",
            "default": "/mnt/data/sstv"
        }
    }
    
    # Daemon configuration schema with defaults
    DAEMON_CONFIG_SCHEMA = {
        "daemon": {
            "enabled": {"default": False},
            "transmission_sets_path": {"default": "/mnt/data/sstv"},
            "check_interval": {"default": 60},
            "audio_device_name": {"default": "pulse"}
        },
        "rig": {
            "address": {"default": "localhost:4532"},
            "signal_power_threshold": {"default": -80},
            "max_waiting_time": {"default": 300}
        },
        "logging": {
            "level": {"default": "INFO"},
            "file": {"default": "/var/log/rig-web/scheduled_transmitter_{rig_id}.log"}
        }
    }
    
    def __init__(self, registry):
        super().__init__(registry)
        self._load_config()
        self.base_dir = self._get_config_value('transmission_path')
        self._ensure_base_dir()
    
    def _get_config_value(self, key):
        """Get configuration value with fallback to schema default."""
        value = self.config.get(key)
        if value is not None:
            return value
        
        # Fallback to schema default
        schema_field = self.PLUGIN_CONFIG_SCHEMA.get(key, {})
        return schema_field.get('default')
    
    def _get_daemon_config_value(self, config_dict, section, key, rig_id=None):
        """Get daemon configuration value with fallback to schema default."""
        section_data = config_dict.get(section, {})
        value = section_data.get(key)
        if value is not None:
            # Handle template variables
            if isinstance(value, str) and rig_id and '{rig_id}' in value:
                return value.format(rig_id=rig_id)
            return value
        
        # Fallback to schema default
        schema_section = self.DAEMON_CONFIG_SCHEMA.get(section, {})
        schema_field = schema_section.get(key, {})
        default = schema_field.get('default')
        
        # Handle template variables in defaults
        if isinstance(default, str) and rig_id and '{rig_id}' in default:
            return default.format(rig_id=rig_id)
        return default
    
    def get_daemon_config_for_rig(self, rig_id: str) -> dict:
        """Get daemon configuration for specific rig with proper defaults."""
        # First try to get from config manager
        config_manager = getattr(self.registry, 'config_manager', None)
        if config_manager:
            stored_config = config_manager.get_daemon_config(self.key, rig_id)
            if stored_config:
                return stored_config
        
        # Return default config based on schema
        default_config = {}
        for section, fields in self.DAEMON_CONFIG_SCHEMA.items():
            default_config[section] = {}
            for key, field_def in fields.items():
                default_config[section][key] = self._get_daemon_config_value({}, section, key, rig_id)
        
        return default_config
    
    def _load_config(self):
        """Load configuration from config manager."""
        try:
            config_manager = getattr(self.registry, 'config_manager', None)
            if config_manager:
                plugin_config = config_manager.get_plugin_config(self.key)
                self.config = plugin_config.get('settings', {})
            else:
                self.config = {}
        except Exception as e:
            logger.warning(f"Failed to load config for {self.key}, using defaults: {e}")
            self.config = {}
    
    def _ensure_base_dir(self):
        """Ensure base directory exists."""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create base directory {self.base_dir}: {e}")
    
    def _get_secure_path(self, folder_name, filename=None):
        """Get secure path within base directory."""
        base_dir_abs = os.path.abspath(self.base_dir)
        folder_path = os.path.abspath(os.path.join(base_dir_abs, secure_filename(folder_name)))
        
        # Security check: ensure path is within base directory
        if not folder_path.startswith(base_dir_abs):
            raise ValueError("Path traversal detected")
        
        if filename:
            file_path = os.path.abspath(os.path.join(folder_path, secure_filename(filename)))
            if not file_path.startswith(base_dir_abs):
                raise ValueError("Path traversal detected")
            return file_path
        
        return folder_path
    
    @property
    def key(self) -> str:
        return "scheduled_transmitter"
    
    @property
    def label(self) -> str:
        return "Scheduled Transmitter"
    
    def enable(self) -> None:
        """Enable the scheduled transmitter plugin."""
        logger.info("Enabling scheduled transmitter plugin")
        self._enabled = True
        
    def disable(self) -> None:
        """Disable the scheduled transmitter plugin."""
        logger.info("Disabling scheduled transmitter plugin")
        self._enabled = False
    
    def is_external_service(self) -> bool:
        """This plugin can run as external systemd service."""
        return True
    
    def external_service_name(self) -> str:
        """Return systemd service name."""
        return f"rig-plugin@{self.key}.service"
    
    def supports_per_rig_config(self) -> bool:
        """This plugin supports per-rig daemon configuration."""
        return True
    
    def has_main_interface(self) -> bool:
        """This plugin provides a main user interface."""
        return True
    
    def get_main_routes(self) -> str:
        """Return URL prefix for main plugin interface."""
        return f"/plugins/{self.key}"
    
    def has_settings_interface(self) -> bool:
        """Hide settings link from feature cards (UI still reachable via direct URL)."""
        return False
        
    def get_settings_routes(self) -> str:
        """Return URL prefix for plugin settings."""
        return f"/plugins/{self.key}/settings"
    
    def get_card_info(self) -> dict:
        """Return information for plugin card on main page."""
        return {
            "title": "Scheduled Transmitter",
            "description": "Schedule automatic radio transmissions with audio files",
            "icon": "📻",
            "status": "enabled" if self.enabled else "disabled",
            "color": "#3498db"
        }
    
    def get_folders(self):
        """Get list of transmission set folders."""
        try:
            if not os.path.exists(self.base_dir):
                return []
            
            folders = []
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                if os.path.isdir(item_path):
                    folders.append(item)
            
            return sorted(folders)
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            return []
    
    def create_folder(self, folder_name):
        """Create new transmission set folder with schedule.csv."""
        try:
            folder_path = self._get_secure_path(folder_name)
            
            if os.path.exists(folder_path):
                raise ValueError("Folder already exists")
            
            os.makedirs(folder_path)
            
            # Create initial schedule.csv
            csv_path = os.path.join(folder_path, 'schedule.csv')
            df = pd.DataFrame(columns=[
                'Start Date', 'End Date', 'Start Time', 'Duration (minutes)',
                'Frequency (MHz)', 'Mode', 'Power (W)', 'Pause (sec)'
            ])
            df.to_csv(csv_path, index=False, sep=';')
            
            logger.info(f"Created transmission set: {folder_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create folder {folder_name}: {e}")
            raise
    
    def delete_folder(self, folder_name):
        """Delete transmission set folder and all its contents."""
        try:
            folder_path = self._get_secure_path(folder_name)
            
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
                logger.info(f"Deleted transmission set: {folder_name}")
                return True
            else:
                raise ValueError("Folder not found")
        except Exception as e:
            logger.error(f"Failed to delete folder {folder_name}: {e}")
            raise
    
    def get_schedule(self, folder_name):
        """Get schedule data from CSV file."""
        try:
            folder_path = self._get_secure_path(folder_name)
            csv_path = os.path.join(folder_path, 'schedule.csv')
            
            if not os.path.exists(csv_path):
                # Create empty schedule if not exists
                df = pd.DataFrame(columns=[
                    'Start Date', 'End Date', 'Start Time', 'Duration (minutes)',
                    'Frequency (MHz)', 'Mode', 'Power (W)', 'Pause (sec)'
                ])
                df.to_csv(csv_path, index=False, sep=';')
                return []
            
            df = pd.read_csv(csv_path, sep=';')
            return df.fillna('').to_dict(orient='records')
        except Exception as e:
            logger.error(f"Failed to load schedule for {folder_name}: {e}")
            return []
    
    def save_schedule(self, folder_name, schedule_data):
        """Save schedule data to CSV file."""
        try:
            folder_path = self._get_secure_path(folder_name)
            csv_path = os.path.join(folder_path, 'schedule.csv')
            
            df = pd.DataFrame(schedule_data)
            df.to_csv(csv_path, index=False, sep=';')
            
            logger.info(f"Saved schedule for {folder_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save schedule for {folder_name}: {e}")
            raise
    
    def get_audio_files(self, folder_name):
        """Get list of audio files in folder."""
        try:
            folder_path = self._get_secure_path(folder_name)
            
            if not os.path.exists(folder_path):
                return []
            
            audio_files = []
            for pattern in ["*.wav", "*.mp3"]:
                audio_files.extend(glob(pattern, root_dir=folder_path))
            
            return sorted(audio_files)
        except Exception as e:
            logger.error(f"Failed to list audio files in {folder_name}: {e}")
            return []
    
    def save_audio_file(self, folder_name, file):
        """Save uploaded audio file."""
        try:
            if not file.filename.lower().endswith(('.wav', '.mp3')):
                raise ValueError("Invalid file type. Only WAV and MP3 files are allowed.")
            
            folder_path = self._get_secure_path(folder_name)
            
            if not os.path.exists(folder_path):
                raise ValueError("Folder not found")
            
            file_path = self._get_secure_path(folder_name, file.filename)
            file.save(file_path)
            
            logger.info(f"Saved audio file: {file.filename} to {folder_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save audio file {file.filename} to {folder_name}: {e}")
            raise
    
    def delete_audio_file(self, folder_name, filename):
        """Delete audio file."""
        try:
            file_path = self._get_secure_path(folder_name, filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted audio file: {filename} from {folder_name}")
                return True
            else:
                raise ValueError("File not found")
        except Exception as e:
            logger.error(f"Failed to delete audio file {filename} from {folder_name}: {e}")
            raise
    
    def stream_audio_file(self, folder_name, filename):
        """Stream audio file for playback."""
        try:
            folder_path = self._get_secure_path(folder_name)
            file_path = self._get_secure_path(folder_name, filename)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(
                    directory=folder_path,
                    path=filename,
                    as_attachment=False
                )
            else:
                abort(404)
        except Exception as e:
            logger.error(f"Failed to stream audio file {filename} from {folder_name}: {e}")
            abort(404)

    def register_web_routes(self, app):
        """Register plugin web routes with Flask app."""
        # Main interface blueprint
        bp_main = Blueprint(f'{self.key}_main', __name__, url_prefix=self.get_main_routes())
        
        # Settings interface blueprint  
        bp_settings = Blueprint(f'{self.key}_settings', __name__, url_prefix=self.get_settings_routes())
        
        # Main interface routes (transmission sets, scheduling, audio)
        @bp_main.route('/')
        def main_interface():
            # Load main template from plugin directory
            plugin_dir = os.path.dirname(__file__)
            template_path = os.path.join(plugin_dir, 'templates', 'main.html')
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # Simple template variable replacement
                template_content = template_content.replace('{{ plugin.label }}', self.label)
                template_content = template_content.replace('{{ config.get(\'transmission_path\', \'/mnt/data/sstv\') }}', self._get_config_value('transmission_path'))
                
                return template_content
            except Exception as e:
                logger.error(f"Failed to load template from {template_path}: {e}")
                return f"<h1>{self.label}</h1><p>Template not found at {template_path}</p>"
        
        # Main interface: Folders management
        @bp_main.route('/folders', methods=['GET'])
        def get_folders():
            folders = self.get_folders()
            return jsonify({"folders": folders})
        
        @bp_main.route('/folders', methods=['POST'])
        def create_folder():
            data = request.get_json()
            folder_name = data.get('name', '').strip()
            
            if not folder_name:
                return jsonify({"error": "Folder name is required"}), 400
            
            try:
                self.create_folder(folder_name)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        @bp_main.route('/folders/<folder_name>', methods=['DELETE'])
        def delete_folder(folder_name):
            try:
                self.delete_folder(folder_name)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        # Main interface: Schedule management
        @bp_main.route('/schedule/<folder_name>', methods=['GET'])
        def get_schedule(folder_name):
            schedule = self.get_schedule(folder_name)
            return jsonify({"schedule": schedule})
        
        @bp_main.route('/schedule/<folder_name>', methods=['POST'])
        def save_schedule(folder_name):
            data = request.get_json()
            schedule_data = data.get('schedule', [])
            
            try:
                self.save_schedule(folder_name, schedule_data)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        # Main interface: Audio file management
        @bp_main.route('/audio/<folder_name>', methods=['GET'])
        def get_audio_files(folder_name):
            files = self.get_audio_files(folder_name)
            return jsonify({"files": files})
        
        @bp_main.route('/audio/<folder_name>', methods=['POST'])
        def upload_audio_file(folder_name):
            if 'audio_file' not in request.files:
                return jsonify({"error": "No file provided"}), 400
            
            file = request.files['audio_file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            try:
                self.save_audio_file(folder_name, file)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        @bp_main.route('/audio/<folder_name>/<filename>', methods=['DELETE'])
        def delete_audio_file(folder_name, filename):
            try:
                self.delete_audio_file(folder_name, filename)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        @bp_main.route('/audio/<folder_name>/<filename>', methods=['GET'])
        def stream_audio_file(folder_name, filename):
            return self.stream_audio_file(folder_name, filename)
        
        # Settings interface: Plugin configuration 
        @bp_settings.route('/')
        def settings_interface():
            # Get current config for form population
            current_transmission_path = self._get_config_value('transmission_path')
            
            return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings - {self.label}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #1a1a1a;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: #2c2c2c;
            border-radius: 8px;
            padding: 2rem;
            border: 1px solid #444;
        }}
        h1, h2 {{
            color: #3498db;
            margin-bottom: 1rem;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }}
        h2 {{
            margin-top: 2rem;
            border-bottom: 1px solid #555;
        }}
        .form-section {{
            background-color: #333;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border: 1px solid #555;
        }}
        .form-group {{
            margin-bottom: 1rem;
        }}
        label {{
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
            color: #f39c12;
        }}
        input[type="text"], input[type="number"], select {{
            width: 100%;
            padding: 0.8rem;
            border: 2px solid #555;
            border-radius: 5px;
            background-color: #2c2c2c;
            color: #e0e0e0;
            font-size: 1rem;
        }}
        input:focus, select:focus {{
            border-color: #3498db;
            outline: none;
        }}
        .btn {{
            padding: 0.8rem 1.5rem;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            margin-right: 0.5rem;
        }}
        .btn-primary {{
            background-color: #3498db;
            color: white;
        }}
        .btn-primary:hover {{
            background-color: #2980b9;
        }}
        .btn-secondary {{
            background-color: #95a5a6;
            color: white;
        }}
        .btn-secondary:hover {{
            background-color: #7f8c8d;
        }}
        .status-indicator {{
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.9rem;
            font-weight: bold;
            margin-bottom: 1rem;
            display: inline-block;
        }}
        .status-indicator.enabled {{
            background: #27ae60;
            color: white;
        }}
        .status-indicator.disabled {{
            background: #e74c3c;
            color: white;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        small {{
            color: #95a5a6;
            font-size: 0.8rem;
            display: block;
            margin-top: 0.3rem;
        }}
        .nav-links {{
            margin-bottom: 2rem;
        }}
        .nav-links a {{
            margin-right: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Settings - {self.label}</h1>
        
        <div class="nav-links">
            <a href="/">← Main Interface</a>
        </div>

        <!-- Plugin Status -->
        <div class="form-section">
            <h2>Plugin Status</h2>
            <div class="status-indicator {'enabled' if self.enabled else 'disabled'}">
                {'Enabled' if self.enabled else 'Disabled'}
            </div>
            <p><strong>External Service:</strong> {'Yes' if self.is_external_service() else 'No'}</p>
            <p><strong>Service Name:</strong> {self.external_service_name() or 'N/A'}</p>
        </div>

        <!-- Plugin Configuration -->
        <div class="form-section">
            <h2>Plugin Configuration</h2>
            <form id="plugin-config-form">
                <div class="form-group">
                    <label for="transmission_path">Transmission Path:</label>
                    <input type="text" id="transmission_path" name="transmission_path" 
                           value="{current_transmission_path}" required>
                    <small>Directory containing transmission sets (default: /mnt/data/sstv)</small>
                </div>
                
                <button type="submit" class="btn btn-primary">Save Configuration</button>
                <button type="button" class="btn btn-secondary" onclick="location.reload()">Cancel</button>
            </form>
        </div>

        <!-- Daemon Configuration (Per-Rig) -->
        <div class="form-section">
            <h2>Daemon Configuration (Per-Rig)</h2>
            <p>Configure daemon settings for each radio. All radios currently share the same transmission sets directory.</p>
            
            <div class="form-group">
                <label for="rig-selector">Select Radio:</label>
                <select id="rig-selector" onchange="loadSelectedRigConfig()">
                    <option value="">-- Choose Radio --</option>
                </select>
                <button type="button" class="btn btn-secondary" onclick="loadRigList()" style="margin-left: 0.5rem;">🔄 Refresh</button>
            </div>
            
            <div id="selected-rig-config" style="display: none;">
                <!-- Selected rig configuration will be loaded here -->
            </div>
        </div>
    </div>

    <script>
        // Handle plugin configuration form submission
        document.getElementById('plugin-config-form').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const config = Object.fromEntries(formData.entries());
            
            try {{
                const response = await fetch('/plugins/{self.key}/settings/config', {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ settings: config }})
                }});
                
                if (response.ok) {{
                    alert('Configuration saved successfully!');
                    location.reload();
                }} else {{
                    const error = await response.json();
                    alert('Failed to save configuration: ' + (error.error || 'Unknown error'));
                }}
            }} catch (error) {{
                alert('Failed to save configuration: ' + error.message);
            }}
        }});

        // Load radio list for dropdown
        async function loadRigList() {{
            try {{
                const response = await fetch('/api/config/radios');
                const data = await response.json();
                
                const selector = document.getElementById('rig-selector');
                const currentValue = selector.value;
                
                // Clear and populate dropdown
                selector.innerHTML = '<option value="">-- Choose Radio --</option>';
                
                if (data.radios.length === 0) {{
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'No radios configured';
                    option.disabled = true;
                    selector.appendChild(option);
                    
                    document.getElementById('selected-rig-config').style.display = 'none';
                    return;
                }}
                
                data.radios.forEach(radio => {{
                    const option = document.createElement('option');
                    option.value = radio.id;
                    option.textContent = `${{radio.name}} (${{radio.id}})`;
                    if (radio.id === currentValue) {{
                        option.selected = true;
                    }}
                    selector.appendChild(option);
                }});
                
                // Reload config if radio was previously selected
                if (currentValue && data.radios.some(r => r.id === currentValue)) {{
                    loadSelectedRigConfig();
                }}
            }} catch (error) {{
                console.error('Failed to load radio list:', error);
                document.getElementById('rig-selector').innerHTML = '<option value="">Error loading radios</option>';
            }}
        }}

        // Load selected rig configuration
        async function loadSelectedRigConfig() {{
            const rigId = document.getElementById('rig-selector').value;
            const container = document.getElementById('selected-rig-config');
            
            if (!rigId) {{
                container.style.display = 'none';
                return;
            }}
            
            try {{
                const response = await fetch('/plugins/{self.key}/settings/daemon-config/' + rigId);
                const data = await response.json();
                const config = data.config || {{}};
                
                const rigName = document.getElementById('rig-selector').selectedOptions[0].textContent;
                
                container.innerHTML = `
                    <h3 style="color: #f39c12; margin-top: 1rem;">Configuration for: ${{rigName}}</h3>
                    <form id="selected-rig-form" onsubmit="saveSelectedRigConfig(event)">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
                            <div class="form-group">
                                <label>Daemon Enabled:</label>
                                <select name="daemon_enabled" required>
                                    <option value="true" ${{(config.daemon?.enabled === true || config.daemon?.enabled === 'true') ? 'selected' : ''}}>Yes</option>
                                    <option value="false" ${{(config.daemon?.enabled === false || config.daemon?.enabled === 'false') ? 'selected' : ''}}>No</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Check Interval (seconds):</label>
                                <input type="number" name="check_interval" value="${{config.daemon?.check_interval || 60}}" min="1" required>
                            </div>
                            <div class="form-group">
                                <label>Audio Device:</label>
                                <input type="text" name="audio_device_name" value="${{config.daemon?.audio_device_name || 'pulse'}}" required>
                            </div>
                            <div class="form-group">
                                <label>Rig Address:</label>
                                <input type="text" name="rig_address" value="${{config.rig?.address || 'localhost:4532'}}" required>
                                <small>Format: hostname:port</small>
                            </div>
                            <div class="form-group">
                                <label>Signal Power Threshold (dBm):</label>
                                <input type="number" name="signal_power_threshold" value="${{config.rig?.signal_power_threshold || -80}}" required>
                            </div>
                            <div class="form-group">
                                <label>Max Waiting Time (seconds):</label>
                                <input type="number" name="max_waiting_time" value="${{config.rig?.max_waiting_time || 300}}" min="1" required>
                            </div>
                        </div>
                        <div style="margin-top: 1rem;">
                            <button type="submit" class="btn btn-primary">Save Configuration</button>
                            <button type="button" class="btn btn-secondary" onclick="loadSelectedRigConfig()">Reset</button>
                        </div>
                    </form>
                `;
                
                container.style.display = 'block';
            }} catch (error) {{
                console.error(`Failed to load config for rig ${{rigId}}:`, error);
                container.innerHTML = '<p style="color: #e74c3c;">Failed to load configuration</p>';
                container.style.display = 'block';
            }}
        }}

        // Save selected rig configuration
        async function saveSelectedRigConfig(event) {{
            event.preventDefault();
            
            const rigId = document.getElementById('rig-selector').value;
            if (!rigId) {{
                alert('No radio selected');
                return;
            }}
            
            const form = event.target;
            const formData = new FormData(form);
            
            const config = {{
                daemon: {{
                    enabled: formData.get('daemon_enabled') === 'true',
                    transmission_sets_path: '{current_transmission_path}', // Use shared path
                    check_interval: parseInt(formData.get('check_interval')),
                    audio_device_name: formData.get('audio_device_name')
                }},
                rig: {{
                    address: formData.get('rig_address'),
                    signal_power_threshold: parseInt(formData.get('signal_power_threshold')),
                    max_waiting_time: parseInt(formData.get('max_waiting_time'))
                }},
                logging: {{
                    level: 'INFO',
                    file: `/var/log/rig-web/scheduled_transmitter_${{rigId}}.log`
                }}
            }};
            
            try {{
                const response = await fetch('/plugins/{self.key}/settings/daemon-config/' + rigId, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(config)
                }});
                
                if (response.ok) {{
                    alert(`Configuration saved successfully for radio ${{rigId}}!`);
                }} else {{
                    const error = await response.json();
                    alert('Failed to save configuration: ' + (error.error || 'Unknown error'));
                }}
            }} catch (error) {{
                alert('Failed to save configuration: ' + error.message);
            }}
        }}

        // Load rig list on page load
        window.addEventListener('DOMContentLoaded', loadRigList);
    </script>
</body>
</html>"""
        
        @bp_settings.route('/config', methods=['GET'])
        def get_plugin_config():
            return jsonify(self.config)
        
        @bp_settings.route('/config', methods=['PUT'])
        def update_plugin_config():
            data = request.get_json()
            if data:
                try:
                    # Update local config
                    if 'settings' in data:
                        self.config.update(data['settings'])
                        # Update transmission path if changed
                        self.base_dir = self._get_config_value('transmission_path')
                        self._ensure_base_dir()
                    else:
                        self.config.update(data)
                    
                    # Save to config file via config manager
                    config_manager = getattr(self.registry, 'config_manager', None)
                    if config_manager:
                        plugin_config = config_manager.get_plugin_config(self.key)
                        plugin_config['settings'] = self.config
                        config_manager.save_plugin_config(self.key, plugin_config)
                    
                    return jsonify({"success": True, "config": self.config})
                except Exception as e:
                    return jsonify({"error": str(e)}), 500
            return jsonify({"error": "No data provided"}), 400
        
        # Settings interface: Per-rig daemon configuration
        @bp_settings.route('/daemon-config/<rig_id>', methods=['GET'])
        def get_daemon_config(rig_id):
            config = self.get_daemon_config_for_rig(rig_id)
            return jsonify({"config": config})
        
        @bp_settings.route('/daemon-config/<rig_id>', methods=['PUT'])
        def update_daemon_config(rig_id):
            data = request.get_json()
            if not data:
                return jsonify({"error": "No configuration data provided"}), 400
            
            try:
                success = self.update_daemon_config_for_rig(rig_id, data)
                if success:
                    return jsonify({"success": True})
                else:
                    return jsonify({"error": "Failed to update daemon configuration"}), 500
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @bp_settings.route('/configured-rigs', methods=['GET'])
        def get_configured_rigs():
            rigs = self.list_configured_rigs()
            return jsonify({"rigs": rigs})
        
        # Register both blueprints
        app.register_blueprint(bp_main)
        app.register_blueprint(bp_settings)
    
    def update_config(self, new_config: dict) -> bool:
        """Update plugin configuration."""
        try:
            if 'settings' in new_config:
                self.config.update(new_config['settings'])
            else:
                self.config.update(new_config)
            
            # Update base directory if transmission_path changed
            self.base_dir = self._get_config_value('transmission_path')
            self._ensure_base_dir()
            
            logger.info(f"Updated config for {self.key}")
            return True
        except Exception as e:
            logger.error(f"Failed to update config for {self.key}: {e}")
            return False
    
    def get_config_schema(self) -> dict:
        """Return JSON schema for plugin configuration."""
        return self.PLUGIN_CONFIG_SCHEMA

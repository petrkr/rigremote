"""Scheduled transmitter plugin with CSV editor and audio upload."""

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
    """Plugin for scheduled radio transmissions with CSV editor and audio upload."""
    
    def __init__(self, registry):
        super().__init__(registry)
        self._load_config()
        self.base_dir = self.config.get('transmission_path', '/mnt/data/sstv')
        self._ensure_base_dir()
    
    def _load_config(self):
        """Load configuration from config manager."""
        try:
            config_manager = getattr(self.registry, 'config_manager', None)
            if config_manager:
                plugin_config = config_manager.get_plugin_config(self.key)
                self.config = plugin_config.get('settings', {})
            else:
                self.config = {
                    "transmission_path": "/mnt/data/sstv",
                    "check_interval": 60,
                    "max_file_size": "10MB"
                }
        except Exception as e:
            logger.warning(f"Failed to load config for {self.key}, using defaults: {e}")
            self.config = {
                "transmission_path": "/mnt/data/sstv",
                "check_interval": 60,
                "max_file_size": "10MB"
            }
    
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
    
    def start(self) -> None:
        """Start the scheduled transmitter."""
        logger.info("Starting scheduled transmitter plugin")
        self._running = True
        # TODO: Implement scheduling logic
        
    def stop(self) -> None:
        """Stop the scheduled transmitter."""
        logger.info("Stopping scheduled transmitter plugin")
        self._running = False
        # TODO: Cleanup scheduling
    
    def is_external_service(self) -> bool:
        """This plugin can run as external systemd service."""
        return True
    
    def external_service_name(self) -> str:
        """Return systemd service name."""
        return f"rig-plugin@{self.key}.service"
    
    def has_web_interface(self) -> bool:
        """This plugin provides a web interface."""
        return True
    
    def get_web_routes(self) -> str:
        """Return URL prefix for plugin web routes."""
        return f"/plugins/{self.key}"
    
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
        bp = Blueprint(self.key, __name__, url_prefix=self.get_web_routes())
        
        @bp.route('/')
        def plugin_home():
            # Load template from plugin directory
            plugin_dir = os.path.dirname(__file__)
            template_path = os.path.join(plugin_dir, 'scheduled_transmitter', 'templates', 'main.html')
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # Simple template variable replacement
                template_content = template_content.replace('{{ plugin.label }}', self.label)
                template_content = template_content.replace('{{ config.get(\'transmission_path\', \'/mnt/data/sstv\') }}', self.config.get('transmission_path', '/mnt/data/sstv'))
                template_content = template_content.replace('{{ config.get(\'check_interval\', 60) }}', str(self.config.get('check_interval', 60)))
                
                return template_content
            except Exception as e:
                logger.error(f"Failed to load template from {template_path}: {e}")
                return f"<h1>{self.label}</h1><p>Template not found at {template_path}</p>"
        
        # Folders management
        @bp.route('/folders', methods=['GET'])
        def get_folders():
            folders = self.get_folders()
            return jsonify({"folders": folders})
        
        @bp.route('/folders', methods=['POST'])
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
        
        @bp.route('/folders/<folder_name>', methods=['DELETE'])
        def delete_folder(folder_name):
            try:
                self.delete_folder(folder_name)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        # Schedule management
        @bp.route('/schedule/<folder_name>', methods=['GET'])
        def get_schedule(folder_name):
            schedule = self.get_schedule(folder_name)
            return jsonify({"schedule": schedule})
        
        @bp.route('/schedule/<folder_name>', methods=['POST'])
        def save_schedule(folder_name):
            data = request.get_json()
            schedule_data = data.get('schedule', [])
            
            try:
                self.save_schedule(folder_name, schedule_data)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        # Audio file management
        @bp.route('/audio/<folder_name>', methods=['GET'])
        def get_audio_files(folder_name):
            files = self.get_audio_files(folder_name)
            return jsonify({"files": files})
        
        @bp.route('/audio/<folder_name>', methods=['POST'])
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
        
        @bp.route('/audio/<folder_name>/<filename>', methods=['DELETE'])
        def delete_audio_file(folder_name, filename):
            try:
                self.delete_audio_file(folder_name, filename)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        @bp.route('/audio/<folder_name>/<filename>', methods=['GET'])
        def stream_audio_file(folder_name, filename):
            return self.stream_audio_file(folder_name, filename)
        
        # Configuration
        @bp.route('/config', methods=['GET'])
        def get_plugin_config():
            return jsonify(self.config)
        
        @bp.route('/config', methods=['PUT'])
        def update_plugin_config():
            data = request.get_json()
            if data:
                try:
                    # Update local config
                    if 'settings' in data:
                        self.config.update(data['settings'])
                        # Update transmission path if changed
                        self.base_dir = self.config.get('transmission_path', '/mnt/data/sstv')
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
        
        app.register_blueprint(bp)
    
    def update_config(self, new_config: dict) -> bool:
        """Update plugin configuration."""
        try:
            if 'settings' in new_config:
                self.config.update(new_config['settings'])
            else:
                self.config.update(new_config)
            
            # Update base directory if transmission_path changed
            self.base_dir = self.config.get('transmission_path', '/mnt/data/sstv')
            self._ensure_base_dir()
            
            logger.info(f"Updated config for {self.key}")
            return True
        except Exception as e:
            logger.error(f"Failed to update config for {self.key}: {e}")
            return False
    
    def get_config_schema(self) -> dict:
        """Return JSON schema for plugin configuration."""
        return {
            "transmission_path": {
                "type": "string",
                "title": "Transmission Path",
                "description": "Directory containing transmission sets",
                "default": "/mnt/data/sstv"
            },
            "check_interval": {
                "type": "integer",
                "title": "Check Interval (seconds)",
                "description": "How often to check for scheduled transmissions",
                "minimum": 1,
                "maximum": 3600,
                "default": 60
            },
            "max_file_size": {
                "type": "string",
                "title": "Max File Size",
                "description": "Maximum audio file size",
                "default": "10MB"
            }
        }
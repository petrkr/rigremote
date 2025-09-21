# RIG Web - Plugin System Redesign

## Project Overview
Ham radio control web application with plugin system for scheduled transmissions and external services.

## Recent Work Summary (Session: 2025-09-21)

### Completed Plugin System Redesign
**Goal**: Transform plugin system from running/start/stop paradigm to more user-friendly card-based navigation with separated main/settings interfaces.

**User Feedback**: Current system required too much navigation: "najedes na hlavni stranku, sjedes dolu na nastaveni, tam si vyberes pluginy, tam si vyberes otevirt stranku pluginu a az tam to najdes"

### ✅ Completed Tasks

1. **Plugin Lifecycle Redesign**
   - Changed from `running/start/stop` to `enabled/disabled` paradigm
   - Plugins enabled by default when instantiated
   - Better fits editor-style plugins vs daemon services

2. **Feature Cards on Main Page**
   - Added prominent feature cards section above plugin management
   - Cards display: title, description, icon, status
   - Direct click access to main plugin interface
   - Settings button for quick configuration access
   - Modern CSS with hover effects and gradients

3. **Dual Plugin Interface System**
   - **Main Interface** (`/plugins/{plugin}/`) - Primary user functionality
   - **Settings Interface** (`/plugins/{plugin}/settings/`) - Configuration and daemon settings
   - Separate Flask blueprints for clean route organization
   - Cross-navigation links between interfaces

4. **Plugin Configuration Migration**
   - Moved full configuration from main page to settings interface
   - Added comprehensive settings page with form handling
   - Removed "Open Plugin Interface" from plugin management
   - Added "⚙️ Settings" button to plugin management

5. **Per-Rig Daemon Configuration**
   - Dropdown selector for radio selection (scalable design)
   - Individual daemon config per radio
   - Shared transmission path across all radios (current limitation)
   - Settings: daemon enabled, check interval, audio device, rig address, thresholds

### Technical Implementation Details

#### Extended PluginModule Interface (`core/interfaces/plugin_module.py`)
```python
def has_main_interface(self) -> bool
def get_main_routes(self) -> str  
def has_settings_interface(self) -> bool
def get_settings_routes(self) -> str
def get_card_info(self) -> dict
@property
def enabled(self) -> bool
```

#### New API Endpoints (`web/api.py`)
- `/api/plugin-cards` - Returns card info for enabled plugins with main interfaces

#### Plugin Configuration Schema (`plugins/scheduled_transmitter/__init__.py`)
```python
PLUGIN_CONFIG_SCHEMA = {
    "transmission_path": {
        "type": "string", 
        "title": "Transmission Path",
        "description": "Directory containing transmission sets",
        "default": "/mnt/data/sstv"
    }
}

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
```

#### Frontend Changes (`web/ui/static/app.js`)
- Added `loadFeatureCards()` method called during initialization
- Removed "Open Plugin Interface" from plugin management
- Added "⚙️ Settings" button with proper CSS styling

#### CSS Enhancements (`web/ui/static/style.css`)
- Feature card grid layout with hover effects
- Modern gradient borders and animations
- Button styling for links (`a.btn` classes)

### Current Architecture Status

**Working Features:**
- ✅ Feature cards with main interface access
- ✅ Settings interface with plugin configuration form
- ✅ Per-rig daemon configuration with dropdown
- ✅ Dual blueprint route system
- ✅ Centralized configuration schemas with defaults
- ✅ API integration for card loading

**Current Limitations:**
- Single transmission path shared across all radios
- Per-rig daemon config prepared but radios share same base directory
- Settings interface functional but could be enhanced with more validation

### Key Files Modified

1. `core/interfaces/plugin_module.py` - Extended base interface
2. `plugins/scheduled_transmitter/__init__.py` - Complete redesign with dual interfaces
3. `web/api.py` - Added plugin-cards endpoint
4. `web/ui/static/app.js` - Feature cards loading and updated plugin management
5. `web/ui/static/style.css` - Feature card styling
6. `web/ui/templates/index.html` - Added features grid section

### Testing Commands

```bash
# Test server startup
source venv/bin/activate && python3 -m flask run --host=0.0.0.0 --port=5000 --debug

# Test API endpoints
curl -s http://localhost:5000/api/plugin-cards | python3 -m json.tool
curl -s http://localhost:5000/plugins/scheduled_transmitter/settings/config
curl -s http://localhost:5000/plugins/scheduled_transmitter/settings/daemon-config/local_hamlib

# Test configuration save
curl -s -X PUT -H "Content-Type: application/json" \
  -d '{"settings":{"transmission_path":"/tmp/test"}}' \
  http://localhost:5000/plugins/scheduled_transmitter/settings/config
```

### Next Steps (Future Work)

1. **Enhanced Per-Rig Support**
   - Multiple transmission paths per radio
   - Radio-specific transmission set management
   - Advanced daemon configuration validation

2. **Plugin Template System**
   - Standardized settings page templates
   - Common configuration components
   - Plugin development guidelines

3. **System Integration**
   - Systemd service management from UI
   - Real-time daemon status monitoring
   - Log file viewing in settings interface

### Development Notes

- Server runs on port 5000 with debug mode
- Plugin system uses folder-based architecture (`plugins/scheduled_transmitter/`)
- Configuration stored in TOML format under `config/plugins/{plugin_name}/`
- Per-rig configs stored as `{rig_id}.toml` files
- All changes are backwards compatible with existing plugin loading

### User Experience Improvements

**Before**: Main page → Configuration tab → Plugins → Open Plugin Interface → Find functionality
**After**: Main page → Feature card click → Direct functionality access
**Settings**: Feature card → Settings button → Complete configuration interface

The redesign successfully addresses user feedback about complex navigation while maintaining all functionality and preparing for future enhancements.
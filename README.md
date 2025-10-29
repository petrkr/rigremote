# RIG Remote Control

Proof of concept scripts for remote control TX SSTV images by using FT-991A TRX, but it should work with any hamlib supported RIG.

## Features

- **Editor**: Web interface for managing SSTV transmission schedules
  - Real-time rig status monitoring via WebSocket
  - Schedule editor with calendar picker
  - Audio file management (upload/delete WAV/MP3 files)
  - Live server time and rig frequency/mode/power display

- **Transmitter**: Automatic SSTV transmission daemon
  - Schedule-based automatic transmissions
  - Signal power monitoring before TX
  - Automatic retry if rig or audio device unavailable
  - File system monitoring for schedule changes
  - PTT control with configurable pauses

## Installation

Tested on Raspbian Pi OS 11/12/13, Debian 12/13, and Arch Linux.

### System Dependencies

#### Debian/Ubuntu
```bash
# Hamlib and audio libraries
sudo apt install libhamlib-dev python3-hamlib libsndfile1 libmpg123-0

# For venv
sudo apt install python3-venv
```

#### Arch Linux
```bash
# Hamlib and audio libraries
sudo pacman -S hamlib libsndfile mpg123

# Python venv is included in the python package
```

### Setup Virtual Environment

**Option 1: Symlink Hamlib (recommended)**

Create a clean venv and symlink only Hamlib from system:

```bash
cd /path/to/rigremote
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Symlink Hamlib from system
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ln -s /usr/lib/python${PYVER}/site-packages/Hamlib.py venv/lib/python${PYVER}/site-packages/
ln -s /usr/lib/python${PYVER}/site-packages/_Hamlib.so venv/lib/python${PYVER}/site-packages/
```

**Option 2: System site packages**

Use `--system-site-packages` to access all system packages:

```bash
cd /path/to/rigremote
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Copy and edit config.yaml:

```bash
cp config.yaml.example config.yaml
vim config.yaml
```

Configure:
- `rig_address`: IP address of rigctld (e.g., `127.0.0.1` or `192.168.1.100`)
- `audio_device_name`: Audio device name (run transmitter once to see available devices)
- `transmission_sets_path`: Path to SSTV files (e.g., `/mnt/data/sstv/`)

## Running

### Editor (web interface)
```bash
source venv/bin/activate
python3 editor.py
```

Editor runs on http://[::]:5000

### Transmitter (automatic transmission daemon)
```bash
source venv/bin/activate
python3 transmitter.py
```

## Systemd Services

Systemd service files are included in the repository. Install to `/opt/rigremote` and they will work out of the box.

```bash
sudo cp rigremote-*.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rigremote-editor.service
sudo systemctl enable --now rigremote-transmitter.service
```

## Troubleshooting

### Audio device not found
Transmitter prints available audio devices:
```
INFO: Available audio devices:
INFO:   [0] HDA Intel PCH: HDMI 0 (hw:0,3) (ALSA)
INFO:   [5] pipewire (ALSA)
INFO:   [6] pulse (ALSA)
INFO:   [7] default (ALSA)
```

Set `audio_device_name` in config.yaml to part of the name (e.g., `pulse` or `pipewire`).

### Hamlib import error in venv
Make sure you created venv with `--system-site-packages`:
```bash
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### Rig unavailable at startup
Services wait until rig becomes available. Check that rigctld is running:
```bash
ps aux | grep rigctld
```

Start rigctld manually for testing:
```bash
rigctld -m 1  # dummy rig for testing
```

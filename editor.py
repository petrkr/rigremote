from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, jsonify
from flask_socketio import SocketIO, emit
from glob import glob
import os
import pandas as pd
from datetime import datetime
import time
import threading
import yaml
import Hamlib

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Directory containing subfolders with schedule.csv files
BASE_DIR = '/mnt/data/sstv'

# Load configuration
def load_config(config_file='config.yaml'):
    try:
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
        return None

CONFIG = load_config()

# Global cache for current rig status
current_rig_status = {'status': 'unavailable'}

@app.route('/')
def index():
    folders = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]
    return render_template('index.html', folders=folders)

@app.route('/create', methods=['GET', 'POST'])
def create_folder():
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_path = os.path.join(BASE_DIR, folder_name)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            csv_path = os.path.join(folder_path, 'schedule.csv')
            df = pd.DataFrame(columns=[
                'Start Date', 'End Date', 'Start Time', 'Duration (minutes)',
                'Frequency (MHz)', 'Mode', 'Power (W)', 'Pause (sec)'
            ])
            df.to_csv(csv_path, index=False, sep=';')
            flash('Folder created successfully!', 'success')
        else:
            flash('Folder already exists!', 'error')

        return redirect(url_for('index'))

    return render_template('create_folder.html')

@app.route('/edit/<folder_name>', methods=['GET', 'POST'])
def edit_schedule(folder_name):
    base_dir = os.path.abspath(BASE_DIR)

    # Securely join paths
    csv_path = os.path.abspath(os.path.join(base_dir, folder_name, 'schedule.csv'))

    # Check if the paths are within the base directory
    if not csv_path.startswith(base_dir):
        abort(403)  # Forbidden access

    if request.method == 'POST':
        data = request.form.to_dict(flat=False)
        df = pd.DataFrame(data)

        df.to_csv(csv_path, index=False, sep=';')
        flash('Schedule updated successfully!', 'success')
        return redirect(url_for('index'))

    df = pd.read_csv(csv_path, sep=';')
    return render_template('edit_schedule.html', folder_name=folder_name, data=df.to_dict(orient='records'))

# Route to Manage Audio Files
@app.route('/manage_audio/<folder_name>', methods=['GET'])
def manage_audio(folder_name):
    base_dir = os.path.abspath(BASE_DIR)

    # Securely join paths
    safe_folder_path = os.path.abspath(os.path.join(base_dir, folder_name))

    # Check if the paths are within the base directory
    if not safe_folder_path.startswith(base_dir):
        abort(403)  # Forbidden access

    audio_files = []
    for f in ("*.wav", "*.mp3"):
        audio_files.extend(sorted(glob(f, root_dir=safe_folder_path)))

    return render_template('audio_files.html', folder_name=folder_name, audio_files=audio_files)

# Route to Upload Audio File
@app.route('/upload_audio/<folder_name>', methods=['POST'])
def upload_audio_file(folder_name):
    if 'audio_file' not in request.files:
        return "No file part", 400

    base_dir = os.path.abspath(BASE_DIR)

    # Securely join paths
    safe_folder_path = os.path.abspath(os.path.join(base_dir, folder_name))


    file = request.files['audio_file']
    if file.filename == '':
        return "No selected file", 400

    if file.filename.lower().endswith(('.wav', '.mp3')):
        safe_file_path = os.path.abspath(os.path.join(safe_folder_path, file.filename))
        if not safe_file_path.startswith(base_dir):
            abort(403)

        file.save(safe_file_path)
        return '', 200

    return "Invalid file", 400

# Route to Delete Audio File
@app.route('/delete_audio/<folder_name>/<file_name>', methods=['POST'])
def delete_audio_file(folder_name, file_name):
    base_dir = os.path.abspath(BASE_DIR)

    # Securely join paths
    safe_folder_path = os.path.abspath(os.path.join(base_dir, folder_name))
    safe_file_path = os.path.abspath(os.path.join(safe_folder_path, file_name))

    # Check if the paths are within the base directory
    if not safe_file_path.startswith(base_dir):
        abort(403)  # Forbidden access

    if os.path.exists(safe_file_path):
        os.remove(safe_file_path)

    return redirect(url_for('manage_audio', folder_name=folder_name))

# Route to stream audio files
@app.route('/stream_audio/<folder_name>/<file_name>')
def stream_audio(folder_name, file_name):
    base_dir = os.path.abspath(BASE_DIR)

    # Securely join paths
    safe_folder_path = os.path.abspath(os.path.join(base_dir, folder_name))
    safe_file_path = os.path.abspath(os.path.join(safe_folder_path, file_name))

    # Check if the paths are within the base directory
    if not safe_file_path.startswith(base_dir):
        abort(403)  # Forbidden access

    # Check if the file exists and is a file
    if os.path.exists(safe_file_path) and os.path.isfile(safe_file_path):
        return send_from_directory(directory=safe_folder_path, path=os.path.basename(safe_file_path), as_attachment=False)
    else:
        abort(404)  # File not found

# API endpoint to get server time
@app.route('/api/server_time')
def get_server_time():
    now = datetime.now().astimezone()

    return jsonify({
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M:%S'),
        "timezone": now.tzname(),
        "utc_offset": now.strftime("UTC%z"),
        "timestamp": now.timestamp()
    })


def initialize_rig(rig_address):
    """Initialize connection to rig via rigctld"""
    rig = None
    try:
        Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
        rig = Hamlib.Rig(Hamlib.RIG_MODEL_NETRIGCTL)
        rig.set_conf("rig_pathname", rig_address)
        rig.set_conf("retry", "0")  # Don't retry on failure
        rig.set_conf("timeout", "2000")  # 2 second timeout
        rig.open()

        # Check error status after open - THIS IS CRITICAL
        if rig.error_status != 0:
            raise Exception(f"Open failed with error_status: {rig.error_status}")

        # Test connection by reading frequency
        test_freq = rig.get_freq()
        if rig.error_status != 0:
            raise Exception(f"Test read failed with error_status: {rig.error_status}")

        if test_freq is None or test_freq < 100000:
            raise Exception(f"Invalid test frequency: {test_freq}")

        return rig
    except Exception as e:
        print(f"Error connecting to rig: {e}")
        # Clean up on failure - MUST close before returning None
        if rig:
            try:
                rig.close()
            except:
                pass
        return None


def background_rig_status():
    """Background thread monitoring rig status and emitting changes"""
    global current_rig_status

    if not CONFIG or 'global_settings' not in CONFIG:
        print("Config not available, rig monitoring disabled")
        return

    rig_address = CONFIG['global_settings'].get('rig_address')
    if not rig_address:
        print("Rig address not configured, rig monitoring disabled")
        return

    rig = None
    last_frequency = None
    last_mode = None
    last_power = None
    last_ptt = None
    last_smeter = None
    consecutive_errors = 0

    while True:
        try:
            # Try to connect if not connected
            if rig is None:
                rig = initialize_rig(rig_address)
                if rig is None:
                    current_rig_status = {'status': 'unavailable'}
                    socketio.emit('rig_status_update', {'status': 'unavailable'}, namespace='/')
                    socketio.sleep(3)  # Wait 3 seconds before retry
                    continue

            # Check error status before reading
            if rig.error_status != 0:
                raise Exception(f"Rig error status: {rig.error_status}")

            # Read rig status
            frequency = rig.get_freq()

            # Check error status after each critical operation
            if rig.error_status != 0:
                raise Exception(f"Rig error after get_freq: {rig.error_status}")

            if frequency is None or frequency < 100000 or frequency > 1e12:
                raise Exception(f"Invalid frequency received: {frequency}")
            frequency = frequency / 1e6  # Convert Hz to MHz

            mode_tuple = rig.get_mode()
            if rig.error_status != 0:
                raise Exception(f"Rig error after get_mode: {rig.error_status}")

            # Handle different return types: tuple, list, or integer
            if mode_tuple is None:
                raise Exception("Mode is None")
            if isinstance(mode_tuple, (tuple, list)):
                mode = mode_tuple[0] if len(mode_tuple) > 0 else None
            elif isinstance(mode_tuple, int):
                mode = mode_tuple
            else:
                raise Exception(f"Invalid mode type: {type(mode_tuple)}")

            if mode is None or not isinstance(mode, int) or mode > 100000:
                raise Exception(f"Invalid mode value: {mode}")

            power_level = rig.get_level_f(Hamlib.RIG_LEVEL_RFPOWER)
            if rig.error_status != 0:
                raise Exception(f"Rig error after get_level_f: {rig.error_status}")

            if power_level is None or power_level < 0 or power_level > 1.0:
                raise Exception(f"Invalid power level: {power_level}")
            power = round(power_level * 100)

            ptt = rig.get_ptt()
            # Error -11 (RIG_EINVAL) means function not implemented - that's OK, use default
            if rig.error_status != 0:
                if rig.error_status == -11:  # RIG_EINVAL - not implemented
                    ptt = Hamlib.RIG_PTT_OFF  # Default to RX
                else:
                    raise Exception(f"Rig error after get_ptt: {rig.error_status}")

            if ptt is None or (ptt != Hamlib.RIG_PTT_OFF and ptt != Hamlib.RIG_PTT_ON):
                ptt = Hamlib.RIG_PTT_OFF  # Default to RX if invalid

            smeter = rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH)
            # Error -11 (RIG_EINVAL) means function not implemented - that's OK, use default
            if rig.error_status != 0:
                if rig.error_status == -11:  # RIG_EINVAL - not implemented
                    smeter = 0  # Default to S0
                else:
                    raise Exception(f"Rig error after get_level_i: {rig.error_status}")

            if smeter is None:
                smeter = 0  # Default to S0 if None

            # Build update with only changed fields
            update = {}

            if frequency != last_frequency:
                update['frequency'] = f"{frequency:.3f}"
                last_frequency = frequency

            if mode != last_mode:
                # Convert Hamlib mode constants to string
                mode_names = {
                    Hamlib.RIG_MODE_USB: 'USB',
                    Hamlib.RIG_MODE_LSB: 'LSB',
                    Hamlib.RIG_MODE_FM: 'FM',
                    Hamlib.RIG_MODE_FMN: 'FMN',
                    Hamlib.RIG_MODE_AM: 'AM',
                    Hamlib.RIG_MODE_PKTUSB: 'PKT USB',
                    Hamlib.RIG_MODE_PKTLSB: 'PKT LSB',
                }
                update['mode'] = mode_names.get(mode, f"Mode {mode}")
                last_mode = mode

            if power != last_power:
                update['power'] = str(power)
                last_power = power

            if ptt != last_ptt:
                update['ptt'] = 'TX' if ptt == Hamlib.RIG_PTT_ON else 'RX'
                last_ptt = ptt

            if smeter != last_smeter:
                update['smeter'] = str(smeter)
                last_smeter = smeter

            # Convert mode to string for cache
            mode_names = {
                Hamlib.RIG_MODE_USB: 'USB',
                Hamlib.RIG_MODE_LSB: 'LSB',
                Hamlib.RIG_MODE_FM: 'FM',
                Hamlib.RIG_MODE_FMN: 'FMN',
                Hamlib.RIG_MODE_AM: 'AM',
                Hamlib.RIG_MODE_PKTUSB: 'PKT USB',
                Hamlib.RIG_MODE_PKTLSB: 'PKT LSB',
            }
            mode_str = mode_names.get(mode, f"Mode {mode}")

            # Update global cache with current values
            current_rig_status = {
                'status': 'connected',
                'frequency': f"{frequency:.3f}",
                'mode': mode_str,
                'power': str(power),
                'ptt': 'TX' if ptt == Hamlib.RIG_PTT_ON else 'RX',
                'smeter': str(smeter)
            }

            # Send update if anything changed
            if update:
                update['status'] = 'connected'
                socketio.emit('rig_status_update', update, namespace='/')

            # Reset error counter on successful read
            consecutive_errors = 0

            socketio.sleep(1)  # Check every second

        except Exception as e:
            print(f"Error reading rig status: {e}")
            consecutive_errors += 1

            # Close rig connection if exists
            if rig:
                try:
                    rig.close()
                except:
                    pass
            rig = None  # Force reconnect

            # Reset tracking variables so full update is sent on reconnect
            last_frequency = None
            last_mode = None
            last_power = None
            last_ptt = None
            last_smeter = None

            # Update cache and emit unavailable status
            current_rig_status = {'status': 'unavailable'}
            socketio.emit('rig_status_update', {'status': 'unavailable'}, namespace='/')

            # Exponential backoff based on consecutive errors (max 5 seconds)
            retry_delay = min(consecutive_errors, 5)
            socketio.sleep(retry_delay)


def background_server_time():
    """Background thread emitting server time every second"""
    last_date = None
    while True:
        now = datetime.now().astimezone()
        current_date = now.strftime('%Y-%m-%d')

        # Send full update if date changed (or first run)
        if current_date != last_date:
            socketio.emit('server_time_update', {
                'date': current_date,
                'time': now.strftime('%H:%M:%S'),
                'timezone': now.tzname(),
                'utc_offset': now.strftime("UTC%z")
            }, namespace='/')
            last_date = current_date
        else:
            # Send only time update
            socketio.emit('server_time_update', {
                'time': now.strftime('%H:%M:%S')
            }, namespace='/')

        socketio.sleep(1)


@socketio.on('connect')
def handle_connect():
    # Send full server time data to newly connected client
    now = datetime.now().astimezone()
    emit('server_time_update', {
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M:%S'),
        'timezone': now.tzname(),
        'utc_offset': now.strftime("UTC%z")
    })

    # Send current rig status to newly connected client
    emit('rig_status_update', current_rig_status)


@socketio.on('disconnect')
def handle_disconnect():
    pass


if __name__ == '__main__':
    # Start background threads
    socketio.start_background_task(background_server_time)
    socketio.start_background_task(background_rig_status)

    socketio.run(app, host="::", debug=True, allow_unsafe_werkzeug=True)

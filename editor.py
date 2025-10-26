from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, jsonify
from glob import glob
import os
import pandas as pd
from datetime import datetime
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Directory containing subfolders with schedule.csv files
BASE_DIR = '/mnt/data/sstv'

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


if __name__ == '__main__':
    app.run("::", debug=True)

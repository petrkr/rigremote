from flask import Flask, render_template, request, redirect, url_for, flash
import os
import pandas as pd

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
            df.to_csv(csv_path, index=False)
            flash('Folder created successfully!', 'success')
        else:
            flash('Folder already exists!', 'error')

        return redirect(url_for('index'))

    return render_template('create_folder.html')

@app.route('/edit/<folder_name>', methods=['GET', 'POST'])
def edit_schedule(folder_name):
    csv_path = os.path.join(BASE_DIR, folder_name, 'schedule.csv')

    if request.method == 'POST':
        data = request.form.to_dict(flat=False)
        df = pd.DataFrame(data)

        df.to_csv(csv_path, index=False)
        flash('Schedule updated successfully!', 'success')
        return redirect(url_for('index'))

    df = pd.read_csv(csv_path)
    return render_template('edit_schedule.html', folder_name=folder_name, data=df.to_dict(orient='records'))

# Route to Manage Audio Files
@app.route('/manage_audio/<folder_name>', methods=['GET', 'POST'])
def manage_audio(folder_name):
    folder_path = os.path.join(BASE_DIR, folder_name)
    audio_files = [f for f in os.listdir(folder_path) if f.endswith('.wav')]

    if request.method == 'POST':
        if 'audio_file' in request.files:
            file = request.files['audio_file']
            if file.filename.endswith('.wav'):
                file.save(os.path.join(folder_path, file.filename))
            return redirect(url_for('manage_audio', folder_name=folder_name))

    return render_template('audio_files.html', folder_name=folder_name, audio_files=audio_files)

# Route to Delete Audio File
@app.route('/delete_audio/<folder_name>/<file_name>', methods=['POST'])
def delete_audio_file(folder_name, file_name):
    folder_path = os.path.join(BASE_DIR, folder_name)
    file_path = os.path.join(folder_path, file_name)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('manage_audio', folder_name=folder_name))


if __name__ == '__main__':
    app.run("::", debug=True)

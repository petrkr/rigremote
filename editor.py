from flask import Flask, render_template, request, redirect, url_for, flash
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Directory containing subfolders with schedule.csv files
BASE_DIR = '/mnt/data/sstv'

@app.route('/')
def index():
    subfolders = [f.name for f in os.scandir(BASE_DIR) if f.is_dir()]
    return render_template('index.html', subfolders=subfolders)

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
        # Determine if we are adding or deleting rows
        if 'add_row' in request.form:
            df = pd.read_csv(csv_path)
            new_row = {
                'Start Date': '',
                'End Date': '',
                'Start Time': '',
                'Duration (minutes)': '',
                'Frequency (MHz)': '',
                'Mode': 'FM',  # Default value for Mode
                'Power (W)': '',
                'Pause (sec)': ''
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(csv_path, index=False)
            return redirect(url_for('edit_schedule', folder_name=folder_name))

        elif 'delete_row' in request.form:
            df = pd.read_csv(csv_path)
            index = int(request.form['delete_row'])
            df = df.drop(index)
            df.to_csv(csv_path, index=False)
            return redirect(url_for('edit_schedule', folder_name=folder_name))

        else:
            data = request.form.to_dict(flat=False)
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index=False)
            flash('Schedule updated successfully!', 'success')
            return redirect(url_for('index'))

    df = pd.read_csv(csv_path)
    return render_template('edit_schedule.html', folder_name=folder_name, data=df.to_dict(orient='records'))

if __name__ == '__main__':
    app.run(debug=True)

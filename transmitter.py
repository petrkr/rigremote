import os
import signal
import sys
from glob import glob
import time
from datetime import datetime, timedelta
import threading
import queue

# Configuration
import yaml
import csv

# Rig control
import Hamlib

# Audio playback
import pygame
import pygame._sdl2.audio as sdl2_audio

# File system monitoring
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Global state
running = True
wake_up_event = threading.Event()
reload_queue = queue.Queue()


### File system event handler
class ScheduleFileHandler(FileSystemEventHandler):
    """Monitors schedule files and folders for changes"""
    def __init__(self):
        super().__init__()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('schedule.csv'):
            log_message(f"File system event [MODIFY]: {event.src_path}", "debug")
            reload_queue.put(('modify', event.src_path))
            wake_up_event.set()  # Wake up main loop immediately

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('schedule.csv'):
            log_message(f"File system event [CREATE]: {event.src_path}", "debug")
            reload_queue.put(('create', event.src_path))
            wake_up_event.set()  # Wake up main loop immediately
        elif event.is_directory:
            log_message(f"File system event [CREATE DIR]: {event.src_path}", "debug")
            reload_queue.put(('create_dir', event.src_path))
            wake_up_event.set()  # Wake up main loop immediately

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('schedule.csv'):
            log_message(f"File system event [DELETE]: {event.src_path}", "debug")
            reload_queue.put(('delete', event.src_path))
            wake_up_event.set()  # Wake up main loop immediately


### Audio playback functions
def _get_audio_devices(capture_devices: bool = False):
    init_by_me = not pygame.mixer.get_init()
    if init_by_me:
        pygame.mixer.init()
    devices = tuple(sdl2_audio.get_audio_device_names(capture_devices))
    if init_by_me:
        pygame.mixer.quit()
    return devices


def get_audio_output_device(device_name):
    devices = _get_audio_devices()
    for device in devices:
        if device_name in device:
            return device
    return None


def load_config(config_file):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def log_message(message, level="info"):
    if level == "debug":
        print(f"DEBUG: {message}")
    elif level == "info":
        print(f"INFO: {message}")
    elif level == "warning":
        print(f"WARNING: {message}", file=sys.stderr)
    elif level == "error":
        print(f"ERROR: {message}", file=sys.stderr)


def initialize_rig(rig_address):
    Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
    rig = Hamlib.Rig(Hamlib.RIG_MODEL_NETRIGCTL)
    rig.set_conf("rig_pathname", rig_address)
    rig.open()
    log_message(f"Connected to rig at {rig_address}")
    log_message(f"Rig model: {rig.get_info()}")
    log_message(f"Rig frequency: {rig.get_freq()} Hz")
    log_message(f"Rig mode: {rig.get_mode()}")
    log_message(f"Rig power: {int(rig.get_level_f('RFPOWER') * 100)} W")

    return rig

def check_signal_power(rig : Hamlib.Rig, threshold, max_waiting_time):
    start_time = time.time()
    while running:
        signal_power = rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH)
        log_message(f"Signal power: {signal_power}")
        if signal_power < threshold:
            return True
        if time.time() - start_time > max_waiting_time:
            log_message(f"Maximum waiting time exceeded ({max_waiting_time} seconds). Transmitting anyway.", level="warning")
            return True
        time.sleep(10)
    return False


def transmit(rig : Hamlib.Rig, set_folder, frequency, mode, power, pause, signal_power_threshold, max_waiting_time):
    log_message(f"Starting transmission of {set_folder} on {frequency} MHz, Power: {power} W")

    rig.set_mode(mode)
    rig.set_freq(Hamlib.RIG_VFO_CURR, frequency * 1e6)
    rig.set_level(Hamlib.RIG_LEVEL_RFPOWER, power / 100)

    log_message(f"Checking signal power before transmission")

    if not check_signal_power(rig, signal_power_threshold, max_waiting_time):
        log_message("Signal power threshold not met. Transmission aborted.", level="error")
        return

    files = []
    for f in ("*.wav", "*.mp3"):
        files.extend(sorted(glob(f, root_dir=set_folder)))

    for file in files:
        log_message(f"Transmitting {file}...")
        try:
            pygame.mixer.music.load(os.path.join(set_folder, file))
        except pygame.error as e:
            log_message(f"Error loading audio file '{file}': {e}, skipping", "warning")
            continue

        rig.set_ptt(Hamlib.RIG_VFO_CURR, Hamlib.RIG_PTT_ON)
        time.sleep(1)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if not running:
                pygame.mixer.music.stop()
                break

            time.sleep(1)

        if not running:
            log_message(f"Transmission of {set_folder} interrupted by user.")
            rig.set_ptt(Hamlib.RIG_VFO_CURR, Hamlib.RIG_PTT_OFF)
            break

        log_message(f"Finished transmitting {file}. Waiting {pause} sec for next one")
        rig.set_ptt(Hamlib.RIG_VFO_CURR, Hamlib.RIG_PTT_OFF)

        for _ in range(pause):
            if not running:
                break

            time.sleep(1)

        if not running:
                log_message(f"Transmission of {set_folder} interrupted by user.")
                break

    log_message(f"Finished transmission of {set_folder}")


def handle_shutdown(signum, frame):
    global running
    log_message("Received shutdown signal, stopping service...", level="warning")
    running = False
    wake_up_event.set()  # Wake up main loop immediately to exit


def parse_mode(mode):
    if mode == "USB":
        return Hamlib.RIG_MODE_PKTUSB
    elif mode == "LSB":
        return Hamlib.RIG_MODE_PKTLSB
    elif mode == "FM":
        return Hamlib.RIG_MODE_FM
    elif mode == "FMN":
        return Hamlib.RIG_MODE_FMN
    elif mode == "AM":
        return Hamlib.RIG_MODE_AM
    else:
        raise ValueError(f"Invalid mode: {mode}")


def parse_schedule(file_path):
    schedules = []
    set_folder = os.path.dirname(file_path)
    try:
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            rows = list(reader)

            if not rows:
                log_message(f"Schedule file {file_path} is empty (header only), skipping", "debug")
                return schedules

            for row in rows:
                # Check if row has required columns
                if 'Start Date' not in row or not row['Start Date'].strip():
                    log_message(f"Skipping invalid row in {file_path}: missing or empty Start Date", "debug")
                    continue

                start_date = datetime.strptime(row['Start Date'], "%d.%m.%Y")
                end_date = datetime.strptime(row['End Date'], "%d.%m.%Y")
                start_time = datetime.strptime(row['Start Time'], "%H:%M").time()
                duration_minutes = int(row['Duration (minutes)'])
                frequency = float(row['Frequency (MHz)'].replace(',', '.'))
                mode = row['Mode']
                power = int(row['Power (W)']) if row['Power (W)'].strip() else 5
                pause = int(row['Pause (sec)']) if row['Pause (sec)'].strip() else 60

                # Validate - skip invalid rows silently (user is an idiot)
                if duration_minutes <= 0:
                    log_message(f"Skipping invalid row: duration must be positive (got {duration_minutes})", "debug")
                    continue
                if start_date > end_date:
                    log_message(f"Skipping invalid row: start date after end date", "debug")
                    continue

                start_datetime = datetime.combine(start_date, start_time)
                end_datetime = start_datetime + timedelta(minutes=duration_minutes)

                # Create daily schedules within the date range
                current_date = start_date
                while current_date <= end_date:
                    start_datetime = datetime.combine(current_date, start_time)
                    end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                    if end_datetime < datetime.now():
                        log_message(f"Skipping past schedule: {start_datetime}", "debug")
                        current_date += timedelta(days=1)
                        continue

                    schedules.append({
                        'set_folder': set_folder,
                        'start_datetime': start_datetime,
                        'end_datetime': end_datetime,
                        'duration': duration_minutes,
                        'frequency': frequency,
                        'mode': mode,
                        'power': power,
                        'pause': pause
                    })

                    current_date += timedelta(days=1)


    except Exception as e:
        log_message(f"Error reading schedule file '{file_path}': {e}", "error")
        log_message(f"Skipping schedule file '{file_path}' due to errors", "warning")
        return []  # Return empty list, let other schedules load

    return schedules


def print_schedules(schedules, log_level="info"):
    for row in schedules:
        log_message(f"Set: {row['set_folder']} \
Start: {row['start_datetime']} \
For: {row['duration']} minutes \
Freq: {row['frequency']} MHz \
Mode: {row['mode']} \
Power: {row['power']} W \
Pause: {row['pause']} sec", log_level)


def check_overlaps(schedules):
    sorted_schedules = sorted(schedules, key=lambda x: x['start_datetime'])
    for i in range(len(sorted_schedules)):
        for j in range(i + 1, len(sorted_schedules)):
            if sorted_schedules[j]['start_datetime'] < sorted_schedules[i]['end_datetime']:
                log_message("Overlap detected between:", "warning")
                print_schedules([sorted_schedules[i], sorted_schedules[j]], log_level="warning")
                raise ValueError("Overlapping schedules detected.")


def load_and_check_schedules(transmit_sets_path):
    schedule_files = []
    for set_folder in os.listdir(transmit_sets_path):
        set_path = os.path.join(transmit_sets_path, set_folder)
        if os.path.isdir(set_path):
            schedule_file = os.path.join(set_path, 'schedule.csv')
            if not os.path.exists(schedule_file):
                log_message(f"Warning: Schedule file not found in set {set_folder}. Skipping.", level="warning")
                continue

            schedule_files.append(schedule_file)

    all_schedules = []
    for file_path in schedule_files:
        schedules = parse_schedule(file_path)
        all_schedules.extend(schedules)

    check_overlaps(all_schedules)
    log_message("No overlaps detected across all schedules.")
    return all_schedules


def main():
    config = load_config('config.yaml')
    global_settings = config['global_settings']
    transmit_sets_path = config['transmission_sets_path']
    audio_device = get_audio_output_device(global_settings['audio_device_name'])

    if not audio_device:
        log_message(f"Error: Audio device '{global_settings['audio_device_name']}' not found.", "error")
        log_message(f"Available audio devices: {_get_audio_devices()}", level="info")
        sys.exit(1)

    if not os.path.exists(transmit_sets_path):
        log_message(f"Error: Transmission directory '{transmit_sets_path}' does not exist.", "error")
        sys.exit(1)

    rig = initialize_rig(global_settings['rig_address'])

    log_message("Initializing audio", level="info")

    try:
        pygame.mixer.init(devicename=audio_device)
    except Exception as e:
        log_message(f"Error initializing audio: {e}", level="error")
        sys.exit(1)

    # Setup file watcher for schedule changes
    file_handler = ScheduleFileHandler()
    observer = Observer()
    observer.schedule(file_handler, transmit_sets_path, recursive=True)
    observer.start()
    log_message("File watcher started for schedule monitoring", "info")

    # Initial load of schedules
    schedules = []
    try:
        schedules = load_and_check_schedules(transmit_sets_path)
    except Exception as e:
        log_message(f"Error loading schedules: {e}", level="warning")

    while running:
        wake_up_event.clear()  # Reset event at start of loop
        now = datetime.now()

        # Process all queued file events - do it immediately and continue
        events_processed = 0
        while not reload_queue.empty():
            try:
                event_type, file_path = reload_queue.get_nowait()
                events_processed += 1
                log_message(f"Processing file event: {event_type} for {file_path}", "debug")
            except queue.Empty:
                break

        if events_processed > 0:
            log_message(f"Reloading schedules due to {events_processed} file change events", "info")
            try:
                schedules = load_and_check_schedules(transmit_sets_path)
            except Exception as e:
                log_message(f"Error loading schedules: {e}", level="warning")
            continue  # Immediately check schedules after reload

        log_message("Current schedules:", "info")
        print_schedules(schedules)

        # Track if we transmitted and find next upcoming schedule
        transmitted = False
        next_schedule_time = None

        for row in schedules:
            set_folder = row['set_folder']
            start_datetime = row['start_datetime']
            end_datetime = row['end_datetime']

            # Check if current time is within the transmission window
            if now >= start_datetime and now < end_datetime:
                log_message("Actual schedule:")
                print_schedules([row])
                transmit(
                    rig=rig,
                    set_folder=set_folder,
                    frequency=float(row['frequency']),
                    mode=parse_mode(row['mode']),
                    pause=row['pause'],
                    power=row['power'],
                    signal_power_threshold=global_settings['signal_power_threshold'],
                    max_waiting_time=global_settings['max_waiting_time']
                )
                transmitted = True
            else:
                if now < start_datetime:
                    log_message(f"Schedule not yet started: {start_datetime} (current time: {now})", level="debug")
                    # Track the nearest upcoming schedule
                    if next_schedule_time is None or start_datetime < next_schedule_time:
                        next_schedule_time = start_datetime
                else:
                    log_message(f"Schedule transmission window ended: {end_datetime} (current time: {now})", level="debug")

            if not running:
                log_message("Interrupted by user.")
                break

        # After transmission, immediately check again (pause was already in transmit())
        if transmitted:
            continue

        # Calculate smart sleep timeout
        if next_schedule_time:
            timeout = (next_schedule_time - now).total_seconds()
            timeout = max(1, timeout)  # Minimum 1s to prevent negative/zero timeout
            log_message(f"Sleeping until next schedule at {next_schedule_time} (timeout: {int(timeout)}s)", "info")
        else:
            # No upcoming schedules - wait indefinitely until file change or shutdown
            timeout = None
            log_message(f"No upcoming schedules, waiting for file changes or shutdown", "info")

        # Event-driven wait - can be interrupted by file changes or shutdown signal
        wake_up_event.wait(timeout=timeout)

    # Cleanup
    log_message("Stopping file watcher...", "info")
    observer.stop()
    observer.join()
    pygame.mixer.quit()
    rig.close()
    log_message("Service stopped gracefully.", level="info")

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    main()

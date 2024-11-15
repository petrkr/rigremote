import os
import signal
import sys
from glob import glob
import time
from datetime import datetime, timedelta

# Configuration
import yaml
import csv

# Rig control
import Hamlib

# Audio playback
import pygame
import pygame._sdl2.audio as sdl2_audio

running = True


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


def check_for_overlaps(schedule):
    events = []
    for row in schedule:
        start_time = datetime.strptime(row['Start Time'], "%H:%M").time()
        duration = int(row['Duration (minutes)'])
        end_time = (datetime.combine(datetime.today(), start_time) + timedelta(minutes=duration)).time()
        events.append((start_time, end_time))
    
    # Sort events by start time
    events.sort()
    
    for i in range(len(events) - 1):
        current_end = events[i][1]
        next_start = events[i + 1][0]
        if current_end > next_start:
            return True
    return False


def handle_shutdown(signum, frame):
    global running
    log_message("Received shutdown signal, stopping service...", level="warning")
    running = False


def parse_mode(mode):
    if mode == "USB":
        return Hamlib.RIG_MODE_PKTUSB
    elif mode == "LSB":
        return Hamlib.RIG_MODE_PKTLSB
    elif mode == "FM":
        return Hamlib.RIG_MODE_FM
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
            for row in reader:
                start_date = datetime.strptime(row['Start Date'], "%d.%m.%Y")
                end_date = datetime.strptime(row['End Date'], "%d.%m.%Y")
                start_time = datetime.strptime(row['Start Time'], "%H:%M").time()
                duration_minutes = int(row['Duration (minutes)'])
                frequency = float(row['Frequency (MHz)'].replace(',', '.'))
                mode = row['Mode']
                power = int(row['Power (W)']) or 5
                pause = int(row['Pause (sec)']) or 60

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
        exit(1)

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
        log_message(f"Error: Transmition directory '{transmit_sets_path}' does not exist.", "error")
        sys.exit(1)

    rig = initialize_rig(global_settings['rig_address'])

    log_message("Initializing audio", level="info")

    try:
        pygame.mixer.init(devicename=audio_device)
    except Exception as e:
        log_message(f"Error initializing audio: {e}", level="error")
        sys.exit(1)

    schedules = []
    while running:
        now = datetime.now()
        try:
            schedules = load_and_check_schedules(transmit_sets_path)
        except Exception as e:
            log_message(f"Error loading schedules: {e}", level="warning")

        log_message("Current schedules:", "info")
        print_schedules(schedules)

        for row in schedules:
            set_folder = row['set_folder']
            start_time = row['start_datetime'].time()
            if now.time() >= start_time and now.time() <= (datetime.combine(datetime.today(), start_time) + timedelta(minutes=int(row['duration']))).time():
                log_message(f"Actual schedule:")
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
            else:
                log_message(f"This schedule is not active at the moment. Time: "+ str(row['start_datetime']))

            if not running:
                log_message(f"Interrupted by user.")
                break

        log_message(f"Waiting {global_settings['check_interval']} seconds for next loop...")
        for _ in range(global_settings['check_interval']):
            if not running:
                break

            time.sleep(1)

    pygame.mixer.quit()
    rig.close()
    log_message("Service stopped gracefully.", level="info")

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    main()

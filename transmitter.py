import os
import csv
import signal
import sys
import time
from datetime import datetime, timedelta
import yaml
import Hamlib

running = True

def load_config(config_file):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def log_message(message, level="info"):
    if level == "info":
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
    log_message(f"Rig frequency: {rig.get_freq()}")

    return rig

def check_signal_power(rig : Hamlib.Rig, threshold, max_waiting_time):
    start_time = time.time()
    while running:
        signal_power = rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH  )
        if signal_power < threshold:
            return True
        if time.time() - start_time > max_waiting_time:
            log_message(f"Maximum waiting time exceeded ({max_waiting_time} seconds). Transmitting anyway.", level="warning")
            return True
        time.sleep(10)
    return False

def transmit(rig, set_name, frequency, mode, duration, files, signal_power_threshold, max_waiting_time):
    log_message(f"Checking signal power before transmission of {files} from {set_name} on {frequency} MHz, Mode: {mode}")

    if check_signal_power(rig, signal_power_threshold, max_waiting_time):
        log_message(f"Starting transmission of {files} from {set_name} on {frequency} MHz, Mode: {mode}")

        rig.set_freq(frequency * 1e6)
        rig.set_mode(mode)
        
        for file in files:
            log_message(f"Transmitting {file}...")
            time.sleep(duration * 60 / len(files))
        
        log_message(f"Finished transmission of {files}")
    else:
        log_message(f"Signal power threshold not met. Transmission aborted.", level="error")

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

def main():
    config = load_config('config.yaml')
    global_settings = config['global_settings']
    transmit_sets_path = config['transmission_sets_path']

    if not os.path.exists(transmit_sets_path):
        log_message(f"Error: Transmition directory '{transmit_sets_path}' does not exist.", "error")
        sys.exit(1)

    rig = initialize_rig(global_settings['rig_address'])

    while running:
        now = datetime.now()
        for set_folder in os.listdir(transmit_sets_path):
            set_path = os.path.join(transmit_sets_path, set_folder)
            if os.path.isdir(set_path):
                schedule_file = os.path.join(set_path, 'schedule.csv')
                if not os.path.exists(schedule_file):
                    log_message(f"Warning: Schedule file not found in set {set_folder}. Skipping.", level="warning")
                    continue

                with open(schedule_file, mode='r') as file:
                    reader = csv.DictReader(file)
                    schedule = list(reader)
                    
                    # Check for overlaps
                    if check_for_overlaps(schedule):
                        log_message(f"Error: Overlapping schedules detected in set {set_folder}. Exiting.", level="error")
                        sys.exit(1)
                    
                    for row in schedule:
                        start_time = datetime.strptime(row['Start Time'], "%H:%M").time()
                        if now.time() >= start_time and now.time() <= (datetime.combine(datetime.today(), start_time) + timedelta(minutes=int(row['Duration (minutes)']))).time():
                            files = row['Files'].split(';')
                            transmit(
                                rig=rig,
                                set_name=set_folder,
                                frequency=float(row['Frequency (MHz)']),
                                mode=Hamlib.RIG_MODE_USB if row['Mode'] == "USB" else Hamlib.RIG_MODE_LSB,
                                duration=int(row['Duration (minutes)']),
                                files=files,
                                signal_power_threshold=global_settings['signal_power_threshold'],
                                max_waiting_time=global_settings['max_waiting_time']
                            )
        for _ in range(global_settings['check_interval']):
            if not running:
                break

            time.sleep(1)

    rig.close()
    log_message("Service stopped gracefully.", level="info")

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    main()

import os
import csv
import signal
import sys
from glob import glob
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
        signal_power = rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH)
        if signal_power < threshold:
            return True
        if time.time() - start_time > max_waiting_time:
            log_message(f"Maximum waiting time exceeded ({max_waiting_time} seconds). Transmitting anyway.", level="warning")
            return True
        time.sleep(10)
    return False

def transmit(rig : Hamlib.Rig, set_folder, frequency, mode, power, pause, signal_power_threshold, max_waiting_time):
    log_message(f"Starting transmission of {set_folder} on {frequency} MHz, Power: {power} W")

    rig.set_freq(Hamlib.RIG_VFO_CURR, frequency * 1e6)
    rig.set_mode(mode)
    rig.set_level(Hamlib.RIG_LEVEL_RFPOWER, power / 100)

    log_message(f"Checking signal power before transmission")

    if not check_signal_power(rig, signal_power_threshold, max_waiting_time):
        log_message("Signal power threshold not met. Transmission aborted.", level="error")
        return

    for file in glob("*.wav", root_dir=set_folder):
        if not running:
            log_message(f"Transmission of {set_folder} interrupted by user.")
            break

        log_message(f"Transmitting {file}...")
        time.sleep(5)

        log_message(f"Finished transmitting {file}. Waiting {pause} sec for next one")
        time.sleep(pause)

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
    else:
        raise ValueError(f"Invalid mode: {mode}")


def parse_schedule(file_path):
    schedules = []
    set_folder = os.path.dirname(file_path)
    try:
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                start_date = datetime.strptime(row['Start Date'], "%d.%m.%Y")
                end_date = datetime.strptime(row['End Date'], "%d.%m.%Y")
                start_time = datetime.strptime(row['Start Time'], "%H:%M").time()
                duration_minutes = int(row['Duration (minutes)'])
                frequency = float(row['Frequency (MHz)'])
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
        print(f"Error reading schedule file '{file_path}': {e}")
        exit(1)

    return schedules


def check_overlaps(schedules):
    sorted_schedules = sorted(schedules, key=lambda x: x['start_datetime'])
    for i in range(len(sorted_schedules)):
        for j in range(i + 1, len(sorted_schedules)):
            if sorted_schedules[j]['start_datetime'] < sorted_schedules[i]['end_datetime']:
                print("Overlap detected between:")
                print(f"  Schedule 1: {sorted_schedules[i]}")
                print(f"  Schedule 2: {sorted_schedules[j]}")
                exit(1)


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
    print("No overlaps detected across all schedules.")
    return all_schedules


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
        schedules = load_and_check_schedules(transmit_sets_path)

        print(schedules)

        for row in schedules:
            set_folder = row['set_folder']
            start_time = row['start_datetime'].time()
            if now.time() >= start_time and now.time() <= (datetime.combine(datetime.today(), start_time) + timedelta(minutes=int(row['duration']))).time():
                log_message(f"Transmitting set {set_folder} at {now}...")
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

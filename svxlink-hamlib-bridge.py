
from hamlibrig import HamlibNetRig
from fakerig import FakeRadio

import threading
import time
import os

import select

class SvxPtyRadio:
    def __init__(self, rig, ptt, sql):
        self._rig = rig
        self._ptt_pty = ptt
        self._sql_pty = sql
    

def start_radio_monitor(radio_id, radio, ptt, sql):
    prev_state = {}

    def monitor():
        nonlocal prev_state
        while True:
            mode_str, bandwidth = radio.get_mode()

            state = {
                'id': radio_id,
                'freq': radio.get_freq(),
                'ptt': radio.get_ptt(),
                'signal': radio.get_signal_strength(),
                'mode': mode_str,
                'bandwidth': bandwidth,
                'ctcss': radio.get_ctcss_tone(),
                'dcs': radio.get_dcs_code()
            }
            if state != prev_state:
                print(state)
                prev_state = state

            time.sleep(0.5)
    

    def check_ptt():
        _stop = threading.Event()
        while not _stop.is_set():
            if not os.path.exists(ptt):
                time.sleep(1)
                continue
            try:
                with open(ptt, "rb") as pty:
                    while not _stop.is_set():
                        char = pty.read(1)
                        if char == b'T':
                            radio.set_ptt(True)
                        elif char == b'R':
                            radio.set_ptt(False)
            except Exception as e:
                print(f"[{radio_id}] Error: {e}")
                time.sleep(1)

    threading.Thread(target=monitor, daemon=True).start()
    threading.Thread(target=check_ptt, daemon=True).start()


if __name__ == '__main__':
    #start_radio_monitor("FT991", HamlibNetRig("127.0.0.1"), "/tmp/svxlink_tx1_ptt", "/tmp/svxlink_tx1_sql")
    start_radio_monitor("FT991", FakeRadio(), "/tmp/svxlink_tx1_ptt", "/tmp/svxlink_tx1_sql")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

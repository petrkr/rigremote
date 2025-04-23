
from hamlibrig import HamlibNetRig
from fakerig import FakeRadio

import threading
import time
import os


class SvxPtyRadio:
    def __init__(self, rig, ptt, sql):
        self._rig = rig
        self._ptt_pty = ptt
        self._sql_pty = sql
    

def start_radio_monitor(radio_id, radio, ptt, sql_pty = None):
    prev_state = {}

    def monitor():
        nonlocal prev_state
        while True:
            if not os.path.exists(sql_pty):
                time.sleep(1)
                continue
            try:
                with open(sql_pty, "wb") as sql:
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
                            if state['signal'] > 6:
                                sql.write(b"O")
                                sql.flush()
                            else:
                                sql.write(b"Z")
                                sql.flush()

                            prev_state = state

                        time.sleep(0.5)

            except Exception as e:
                print(f"[{radio_id}] Error: {e}")
                time.sleep(1)
    

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

    if sql_pty:
        threading.Thread(target=monitor, daemon=True).start()

    if ptt:
        threading.Thread(target=check_ptt, daemon=True).start()


if __name__ == '__main__':
    start_radio_monitor("FT991", HamlibNetRig("127.0.0.1"), None, "/tmp/svxlink_tx1_sql")
    start_radio_monitor("FT991", FakeRadio(), "/tmp/svxlink_tx1_ptt", None)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

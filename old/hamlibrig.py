import Hamlib

HAMLIB_MODE_MAP = {
    Hamlib.RIG_MODE_USB: "USB",
    Hamlib.RIG_MODE_LSB: "LSB",
    Hamlib.RIG_MODE_CW: "CW",
    Hamlib.RIG_MODE_CWR: "CWR",
    Hamlib.RIG_MODE_AM: "AM",
    Hamlib.RIG_MODE_FM: "FM",
    Hamlib.RIG_MODE_WFM: "WFM",
    Hamlib.RIG_MODE_RTTY: "RTTY"
}


class HamlibNetRig:
    def __init__(self, host):
        self._rig = self._initialize_rig(host)
        self.ptt = False


    def get_ctcss_tone(self):
        return self._rig.get_ctcss_tone()


    def get_dcs_code(self):
        return self._rig.get_dcs_code()


    def get_freq(self):
        return self._rig.get_freq()


    def get_mode(self):
        mode_code, bandwidth = self._rig.get_mode()
        mode_str = HAMLIB_MODE_MAP.get(mode_code, f"Unknown({mode_code})")
        return (mode_str, bandwidth)


    def get_ptt(self):
        return self._rig.get_ptt(Hamlib.RIG_VFO_CURR)


    def get_signal_strength(self):
        return self._rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH)


    def toggle_ptt(self):
        self.set_ptt(not self.get_ptt())


    def set_ptt(self, value):
        self._rig.set_ptt(Hamlib.RIG_VFO_CURR, Hamlib.RIG_PTT_ON if value else Hamlib.RIG_PTT_OFF)


    def _initialize_rig(self, rig_address):
        Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
        rig = Hamlib.Rig(Hamlib.RIG_MODEL_NETRIGCTL)
        rig.set_conf("rig_pathname", rig_address)
        rig.open()
        print(f"Connected to rig at {rig_address}")
        print(f"Rig model: {rig.get_info()}")
        print(f"Rig frequency: {rig.get_freq()} Hz")
        print(f"Rig mode: {rig.get_mode()}")
        print(f"Rig power: {int(rig.get_level_f('RFPOWER') * 100)} W")

        return rig

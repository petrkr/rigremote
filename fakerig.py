import random

class FakeRadio:
    def __init__(self):
        self.freq = 145500000
        self.ptt = False


    def get_ctcss_tone(self):
        return 887


    def get_dcs_code(self):
        return 25


    def get_freq(self):
        return self.freq


    def get_mode(self):
        return ("FM", 25000)


    def get_ptt(self):
        return self.ptt

    def get_signal_strength(self):
        import random
        return random.randint(0, 9)

    def toggle_ptt(self):
        self.ptt = not self.ptt
        return self.ptt

    def set_ptt(self, value):
        self.ptt = value

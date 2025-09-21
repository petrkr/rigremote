import yaml
from fakerig import FakeRadio
from hamlibrig import HamlibNetRig

def load_radios_from_config(path="radios.yaml"):
    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    radios = {}

    for entry in config.get("radios", []):
        radio_id = entry["id"]
        radio_type = entry["type"]

        if radio_type == "fake":
            radios[radio_id] = FakeRadio()

        elif radio_type == "hamlibnet":
            host = entry.get("host")
            if not host:
                raise ValueError(f"Missing host for radio {radio_id}")
            radios[radio_id] = HamlibNetRig(host)

        else:
            raise ValueError(f"Unknown radio type: {radio_type}")

    return radios

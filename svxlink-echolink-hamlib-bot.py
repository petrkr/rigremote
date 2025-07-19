#!/usr/bin/env python3
import os
import time
from hamlibrig import HamlibNetRig
from fakerig import FakeRadio

fifo_path = "/tmp/svxlink_echolink_chat"
msg_path = "/tmp/svxlink_echolink_ctrl"

def parseEcholinkmsg(msg):
    if ">" not in msg:
        return None, None
    sep = msg.index(">")
    callsign = msg[:sep]
    msg = msg[sep+1:]

    return callsign, msg

def sendEcholinkMsg(call, msg):
    with open(msg_path, "w") as f:
        f.write(f"MSG {call} {msg}\n")
        f.close()


def main():
    # Create fifo
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path)

    # Connect to radio
    rig = HamlibNetRig("10.200.0.176")

    print(f"Waiting for messanges {fifo_path}...")

    try:
        while True:
            with open(fifo_path, "r") as fifo:
                for line in fifo:
                    call, msg = parseEcholinkmsg(line.strip())
                    print(f"{call}: {msg}")

                    if msg == "f":
                        print("Sending frequency")
                        sendEcholinkMsg(call, f"Frequency: {rig.get_freq()}")

    except KeyboardInterrupt:
        print("User interrupted.")
    except Exception as e:
        print(f"Error: {e}")

    # Remove fifo after exit
    os.remove(fifo_path)


if __name__ == "__main__":
    main()

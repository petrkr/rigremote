#!/usr/bin/env python3
import os
import time

fifo_path = "/tmp/svxlink_echolink_chat"

# Vytvoření FIFO pokud neexistuje
if not os.path.exists(fifo_path):
    os.mkfifo(fifo_path)

print(f"Waiting for messanges {fifo_path}...")

try:
    while True:
        with open(fifo_path, "r") as fifo:
            for line in fifo:
                print(f"[ECHOLINK CHAT] {line.strip()}")
except KeyboardInterrupt:
    print("User interrupted.")
except Exception as e:
    print(f"Error: {e}")

os.remove(fifo_path)

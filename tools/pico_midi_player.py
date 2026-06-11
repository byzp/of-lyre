"""Pico USB-MIDI player — reads .mseq binary and sends MIDI via USB.

Copy to CIRCUITPY as code.py (or main.py), place song.mseq alongside.
"""

import time
import struct
import usb_midi

# usb_midi.ports[1] is typically the MIDI OUT port
midi_out = usb_midi.ports[1]

EVENT_SIZE = 5  # <HBBB: 2 + 1 + 1 + 1

with open("song.mseq", "rb") as f:
    while True:
        data = f.read(EVENT_SIZE)
        if len(data) != EVENT_SIZE:
            break

        delta_ms, status, note, vel = struct.unpack("<HBBB", data)

        time.sleep(delta_ms / 1000)

        # Skip dummy "gap-filler" events (status 0x00 inserted for gaps > 65s)
        if status == 0x00:
            continue

        midi_out.write(bytes([status, note, vel]))

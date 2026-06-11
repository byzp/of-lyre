"""Convert MIDI file to binary .mseq format for Pico USB-MIDI playback.

Format: 5 bytes per event: <H BBB  (uint16 delta_ms, uint8 status, uint8 note, uint8 vel)
"""

import struct
import sys
import mido


def convert(midi_path: str, output_path: str = "song.mseq"):
    mid = mido.MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat
    current_tempo = 500000  # microseconds per beat (default 120 BPM)

    with open(output_path, "wb") as f:
        # merge_tracks flattens all tracks into a single time-ordered stream
        for msg in mido.merge_tracks(mid.tracks):
            # Convert delta from ticks to milliseconds
            delta_seconds = mido.tick2second(msg.time, ticks_per_beat, current_tempo)
            delta_ms = int(delta_seconds * 1000)

            # Handle tempo changes
            if msg.type == "set_tempo":
                current_tempo = msg.tempo
                continue

            # Only emit note events
            if msg.type == "note_on":
                if msg.velocity == 0:
                    status, vel = 0x80, 0
                else:
                    status, vel = 0x90, msg.velocity
            elif msg.type == "note_off":
                status, vel = 0x80, 0
            else:
                continue  # skip non-note messages

            # Clamp delta to uint16 range; chain multiple events for longer gaps
            while delta_ms > 65535:
                # Insert a dummy "no-op" event: status 0x00 is undefined → ignored by receiver
                f.write(struct.pack("<HBBB", 65535, 0x00, 0, 0))
                delta_ms -= 65535

            f.write(struct.pack("<HBBB", delta_ms, status, msg.note, vel))

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python midi_to_mseq.py <input.mid> [output.mseq]")
        sys.exit(1)
    out = sys.argv[2] if len(sys.argv) > 2 else "song.mseq"
    convert(sys.argv[1], out)

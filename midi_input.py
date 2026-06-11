"""
MIDI input wrapper — connect to first available MIDI device and output keyboard
events via core.py mapping logic.  Real-time: play a MIDI keyboard → game input.

Usage:
    python midi_input.py                    # auto-connect first MIDI input port
    python midi_input.py --file song.mid    # play a MIDI file through real-time handlers
    python midi_input.py --list             # list available ports and exit
    python midi_input.py --port 1           # connect to specific port index
"""

import os
import sys
import time
import threading
import argparse

import mido
from mido import Message, MidiFile, tick2second

from core import (
    _NOTE_TO_CHAR,
    _char_vk_info,
    press_keys_simultaneous,
    release_keys_simultaneous,
)


# ── state ────────────────────────────────────────────────────────────────────
active_chars: dict = {}  # char -> needs_shift
shift_held: bool = False
sustain_on: bool = False  # CC 64 sustain pedal
sustained: dict = {}  # note -> char (notes held open by pedal)
lock = threading.Lock()


# ── note handlers ────────────────────────────────────────────────────────────


def _get_char(note: int):
    """Return mapped character for MIDI note, or None if unmapped."""
    return _NOTE_TO_CHAR.get(note)


def handle_note_on(note: int, velocity: int):
    global shift_held
    ch = _get_char(note)
    if ch is None:
        return

    vk, needs_shift = _char_vk_info(ch)
    if not vk:
        return

    with lock:
        # If this char is already pressed, release first (re-trigger)
        if ch in active_chars:
            release_keys_simultaneous([ch], release_shift=False)
            del active_chars[ch]

        # If sustain pedal is holding this note, clear sustained copy (live note takes over)
        sustained.pop(note, None)

        # Determine shift state for this key
        press_shift = False
        if needs_shift:
            if not shift_held:
                # If unshifted keys are held, pressing Shift would contaminate them → skip
                if any(not ns for ns in active_chars.values()):
                    return
                press_shift = True
        elif shift_held:
            # Shift is held (by another key): pressing an unshifted key would
            # register as Shift+key → skip to avoid wrong note
            return

        press_keys_simultaneous([ch], press_shift=press_shift)
        if press_shift:
            shift_held = True
        active_chars[ch] = needs_shift


def handle_note_off(note: int):
    global shift_held
    ch = _get_char(note)
    if ch is None:
        return

    with lock:
        if sustain_on:
            # Sustain pedal active: defer release
            if ch in active_chars:
                sustained[note] = ch
            return

        if ch not in active_chars:
            return

        needs_shift = active_chars.pop(ch)
        release_shift = needs_shift and not any(active_chars.values())
        release_keys_simultaneous([ch], release_shift=release_shift)
        if release_shift:
            shift_held = False


def handle_sustain(value: int):
    """CC 64: sustain pedal."""
    global shift_held, sustain_on
    with lock:
        if value >= 64:
            sustain_on = True
        else:
            sustain_on = False
            # Release all sustained chars that aren't still held live
            to_release = [
                ch for note, ch in sustained.items() if ch not in active_chars
            ]
            sustained.clear()
            if to_release:
                any_needs = any(active_chars.values())
                release_keys_simultaneous(
                    to_release, release_shift=shift_held and not any_needs
                )
                if shift_held and not any_needs:
                    shift_held = False


def release_all():
    """Emergency release: all held keys + Shift."""
    global shift_held
    with lock:
        if active_chars:
            release_shift = any(active_chars.values())
            release_keys_simultaneous(
                list(active_chars.keys()), release_shift=release_shift
            )
            active_chars.clear()
            shift_held = False


# ── main ─────────────────────────────────────────────────────────────────────


def _note_name(note: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[note % 12]}{note // 12 - 1}"


def run_midi_file(path: str, show_notes: bool = False):
    """Play a MIDI file through the real-time handlers with proper timing."""
    mid = MidiFile(path)
    current_tempo = 500000
    abs_time = 0.0
    events = []

    # Build time-ordered event list
    for msg in mido.merge_tracks(mid.tracks):
        if msg.time:
            abs_time += tick2second(msg.time, mid.ticks_per_beat, current_tempo)
        if msg.type == "set_tempo":
            current_tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            events.append((abs_time, "on", msg.note, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            events.append((abs_time, "off", msg.note, 0))
        elif msg.type == "control_change" and msg.control == 64:
            events.append((abs_time, "cc64", msg.value, 0))
    events.sort(key=lambda x: x[0])

    print(f"Playing: {path}  ({len(events)} events, {events[-1][0]:.1f}s)")
    print("3 seconds until start...")
    time.sleep(3)

    start_wall = time.perf_counter()
    for t, typ, a, b in events:
        # Wait until event time
        while True:
            elapsed = time.perf_counter() - start_wall
            if elapsed >= t:
                break
            time.sleep(0.001)

        if typ == "on":
            if show_notes:
                ch = _get_char(a)
                mapped = f"-> '{ch}'" if ch else "(unmapped)"
                print(f"  {t:.3f}s ON  {a:3d} ({_note_name(a):4s}) {mapped}")
            handle_note_on(a, b)
        elif typ == "off":
            if show_notes:
                ch = _get_char(a)
                mapped = f"char='{ch}'" if ch else ""
                print(f"  {t:.3f}s OFF {a:3d} {mapped}")
            handle_note_off(a)
        elif typ == "cc64":
            handle_sustain(a)

    # Release any remaining held keys after file ends
    release_all()
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="MIDI input → keyboard output wrapper")
    parser.add_argument("--list", action="store_true", help="list ports and exit")
    parser.add_argument(
        "--port", type=int, default=None, help="port index (default: first)"
    )
    parser.add_argument(
        "--file", type=str, default=None, help="play a MIDI file instead of live input"
    )
    parser.add_argument(
        "--show-notes", action="store_true", help="print MIDI note info on each event"
    )
    args = parser.parse_args()

    def list_ports():
        print("Available MIDI input ports:")
        names = mido.get_input_names()
        if not names:
            print("  (none)")
            return
        for i, name in enumerate(names):
            print(f"  [{i}] {name}")

    if args.list:
        list_ports()
        return

    # Show mapping summary
    mapped_notes = sorted(_NOTE_TO_CHAR.keys())
    print(
        f"Mapping loaded: {len(mapped_notes)} notes ({mapped_notes[0]}–{mapped_notes[-1]})"
    )

    # ── file mode ─────────────────────────────────────────────────────────
    if args.file:
        run_midi_file(args.file, show_notes=args.show_notes)
        return

    # ── live MIDI input mode ───────────────────────────────────────────────
    names = mido.get_input_names()
    if not names:
        print("No MIDI input ports found. Connect a MIDI device and retry.")
        print("Or use --file to play a MIDI file: python midi_input.py --file song.mid")
        return

    port_idx = args.port if args.port is not None else 0
    if port_idx >= len(names):
        print(f"Port index {port_idx} out of range (0–{len(names)-1})")
        list_ports()
        return

    port_name = names[port_idx]
    print(f"Connecting to [{port_idx}] {port_name} ...")
    print("Press Ctrl+C to exit.\n")

    try:
        with mido.open_input(port_name) as inport:
            for msg in inport:
                if msg.type == "note_on" and msg.velocity > 0:
                    if args.show_notes:
                        ch = _get_char(msg.note)
                        mapped = f"-> '{ch}'" if ch else "(unmapped)"
                        print(
                            f"  ON  {msg.note:3d} ({_note_name(msg.note):4s}) vel={msg.velocity:3d} {mapped}"
                        )
                    handle_note_on(msg.note, msg.velocity)

                elif msg.type == "note_off" or (
                    msg.type == "note_on" and msg.velocity == 0
                ):
                    if args.show_notes:
                        ch = _get_char(msg.note)
                        print(
                            f"  OFF {msg.note:3d} ({_note_name(msg.note):4s}) char='{ch}'"
                            if ch
                            else f"  OFF {msg.note:3d}"
                        )
                    handle_note_off(msg.note)

                elif msg.type == "control_change" and msg.control == 64:
                    handle_sustain(msg.value)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        release_all()
        print("All keys released.")


if __name__ == "__main__":
    main()

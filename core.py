"""
mido.MidiFile -> 时间事件列表, MIDI note_on/note_off -> Windows 键盘事件（使用 SendInput，提高同时性与精度）。
stop flag 控制可被 GUI 的停止按钮触发。
"""
import os
import time
import threading
from typing import List, Tuple, Optional
import mido
from mido import MidiFile, tick2second
import ctypes
import ctypes.wintypes

# white key semitone offsets relative to C
_WHITE_OFFSETS = {0, 2, 4, 5, 7, 9, 11}

# mapping characters for the three rows (each row 7 keys)
_ROW1 = list("ASDFGHJ")   # lowest 7 (starting at C3)
_ROW2 = list("QWERTYU")   # middle 7
_ROW3 = list("1234567")   # highest 7

# Build mapping from MIDI note number (48..83 white keys) to characters
def build_note_to_char_map() -> dict:
    mapping = {}
    # white notes from C3 (48) to B5 (83) inclusive
    notes = [n for n in range(48, 84) if (n % 12) in _WHITE_OFFSETS]
    assert len(notes) == 21, "Expect 21 white keys between C3 and B5"
    groups = [notes[0:7], notes[7:14], notes[14:21]]
    rows = [_ROW1, _ROW2, _ROW3]
    for group, row in zip(groups, rows):
        for note, ch in zip(group, row):
            mapping[note] = ch
    return mapping

if os.path.exists("key.txt"):
    mapping = {}
    with open("key.txt", 'r') as f:
        rows = list(f.read().replace("\n" ,""))
    notes = [n for n in range(48, 84) if (n % 12) in _WHITE_OFFSETS]
    for note, ch in zip(notes, rows):
        mapping[note] = ch
    _NOTE_TO_CHAR = mapping
else:
    _NOTE_TO_CHAR = build_note_to_char_map()

# ---- Windows SendInput wrapper (ctypes) for high-precision simultaneous input ----
PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

# constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

_sendinput = ctypes.windll.user32.SendInput
_get_current_process = ctypes.windll.kernel32.GetCurrentProcess
_set_priority_class = ctypes.windll.kernel32.SetPriorityClass
_get_current_thread = ctypes.windll.kernel32.GetCurrentThread
_set_thread_priority = ctypes.windll.kernel32.SetThreadPriority

def _make_key_input(vk: int, is_up: bool=False) -> Input:
    ki = KeyBdInput()
    ki.wVk = vk
    ki.wScan = 0
    ki.dwFlags = KEYEVENTF_KEYUP if is_up else 0
    ki.time = 0
    extra = ctypes.c_ulong(0)
    ki.dwExtraInfo = ctypes.cast(ctypes.pointer(extra), PUL)
    ii = Input_I()
    ii.ki = ki
    inp = Input()
    inp.type = INPUT_KEYBOARD
    inp.ii = ii
    return inp

def send_inputs(inputs: List[Input]) -> int:
    n = len(inputs)
    arr_type = Input * n
    arr = arr_type(*inputs)
    res = _sendinput(n, ctypes.byref(arr), ctypes.sizeof(Input))
    return res

# helper: get virtual-key for a character
def vk_for_char(ch: str) -> int:
    if not ch:
        return 0
    # Uppercase for letters; digits also map to ord('0')..ord('9') which are VK codes
    return ord(ch.upper())

def press_key(ch: str):
    vk = vk_for_char(ch)
    if vk == 0:
        return
    inp = _make_key_input(vk, is_up=False)
    send_inputs([inp])

def release_key(ch: str):
    vk = vk_for_char(ch)
    if vk == 0:
        return
    inp = _make_key_input(vk, is_up=True)
    send_inputs([inp])

def press_keys_simultaneous(chars: List[str]):
    inputs = []
    for ch in chars:
        vk = vk_for_char(ch)
        if vk:
            inputs.append(_make_key_input(vk, is_up=False))
    if inputs:
        send_inputs(inputs)

def release_keys_simultaneous(chars: List[str]):
    inputs = []
    for ch in chars:
        vk = vk_for_char(ch)
        if vk:
            inputs.append(_make_key_input(vk, is_up=True))
    if inputs:
        send_inputs(inputs)

# Convert MidiFile -> list of events with absolute time (seconds)
# Each event: (abs_time_seconds, type_str, note, velocity)
# type_str: 'on' or 'off'

def midi_to_events(
    mid: MidiFile, 
    min_time: Optional[float] = None, 
    max_time: Optional[float] = None
) -> List[Tuple[float, str, int, int]]:
    events = []
    ticks_per_beat = mid.ticks_per_beat
    current_tempo = 500000  # default 120 BPM in microseconds per beat
    # merge all tracks into one stream
    merged = mido.merge_tracks(mid.tracks)
    abs_time = 0.0
    for msg in merged:
        # msg.time is delta in ticks
        if msg.time:
            dt = tick2second(msg.time, ticks_per_beat, current_tempo)
            abs_time += dt
        # tempo changes
        if msg.type == 'set_tempo':
            current_tempo = msg.tempo
            continue
        if min_time is not None and abs_time < min_time:
            continue
        if msg.type == 'note_on':
            if 48 <= msg.note <= 83:
                if msg.velocity == 0:
                    events.append((abs_time, 'off', msg.note, 0))
                else:
                    events.append((abs_time, 'on', msg.note, msg.velocity))
        elif msg.type == 'note_off':
            if 48 <= msg.note <= 83:
                events.append((abs_time, 'off', msg.note, msg.velocity))
        if max_time is not None and abs_time > max_time:
            break
    if min_time is not None:
        events = [e for e in events if e[0] >= min_time]
    if max_time is not None:
        events = [e for e in events if e[0] <= max_time]
    events.sort(key=lambda x: x[0])
    return events


# Play events: send keyboard presses/releases according to event times
def play_events(events: List[Tuple[float, str, int, int]],
                stop_flag: threading.Event,
                progress_callback=None,
                spin_threshold: float = 0.005,
                sleep_chunk: float = 0.01,
                progress_interval: float = 0.05,
                raise_priority: bool = True):
    """
    events: list of (time, 'on'/'off', note, velocity) sorted by time
    stop_flag: threading.Event() - when set, function should stop ASAP (release all keys)
    progress_callback: optional function(current_time_seconds) called regularly to update GUI
    spin_threshold: when remaining time <= spin_threshold (seconds), switch to busy-wait (for precision)
    sleep_chunk: max chunk to wait with Event.wait (seconds)
    progress_interval: how often (seconds) to call progress_callback during waiting
    raise_priority: try to raise process/thread priority for more stable timing (best-effort)
    """
    if not events:
        return

    # Try to raise process & thread priority (best-effort; failures ignored)
    if raise_priority:
        try:
            # HIGH_PRIORITY_CLASS = 0x00000080
            _set_priority_class(_get_current_process(), 0x00000080)
            # THREAD_PRIORITY_HIGHEST = 2
            _set_thread_priority(_get_current_thread(), 2)
        except Exception:
            pass

    # Track which characters are currently physically pressed
    pressed_chars = set()

    # Group events by their timestamp so that actions at the same timestamp are simultaneous
    groups = []
    cur_t = events[0][0]
    cur_group = []
    for e in events:
        t = e[0]
        if abs(t - cur_t) < 1e-9:
            cur_group.append(e)
        else:
            groups.append((cur_t, cur_group))
            cur_t = t
            cur_group = [e]
    groups.append((cur_t, cur_group))

    # base time zero
    base_time_zero = groups[0][0]  # usually 0
    start_wall = time.perf_counter()

    last_progress_time = start_wall

    for (event_time, evlist) in groups:
        if stop_flag.is_set():
            break

        target_wall = start_wall + (event_time - base_time_zero)

        while True:
            if stop_flag.is_set():
                break
            now = time.perf_counter()
            to_wait = target_wall - now
            # progress callback periodically while waiting
            if progress_callback and (now - last_progress_time >= progress_interval):
                try:
                    progress_callback(now - start_wall + base_time_zero)
                except Exception:
                    pass
                last_progress_time = now
            if to_wait <= 0:
                break
            # If remaining time larger than spin threshold, use wait (interruptible)
            if to_wait > spin_threshold:
                # wait up to min(sleep_chunk, to_wait - spin_threshold) so we don't oversleep into spin region
                wait_time = min(sleep_chunk, max(0.0, to_wait - spin_threshold))
                # use stop_flag.wait which is interruptible
                stop_flag.wait(wait_time)
            else:
                # busy-spin for the last few milliseconds for better accuracy
                # simple tight loop
                while True:
                    if stop_flag.is_set():
                        break
                    if time.perf_counter() >= target_wall:
                        break
                break  # exit main wait loop

        if stop_flag.is_set():
            break

        # For this timestamp: first OFF events, then ON events
        offs = [e for e in evlist if e[1] == 'off']
        ons  = [e for e in evlist if e[1] == 'on']

        # Process offs: release keys that correspond
        chars_to_release = []
        for (_, _, note, _) in offs:
            ch = _NOTE_TO_CHAR.get(note)
            if ch is None:
                continue
            if ch in pressed_chars:
                chars_to_release.append(ch)
                pressed_chars.discard(ch)
        if chars_to_release:
            # release simultaneously if multiple
            release_keys_simultaneous(chars_to_release)

        # Process ons: determine chars to press
        chars_to_press = []
        for (_, _, note, _) in ons:
            ch = _NOTE_TO_CHAR.get(note)
            if ch is None:
                continue
            chars_to_press.append(ch)

        # If a requested char is already pressed: release it first (so retrigger)
        must_release_before_press = [ch for ch in chars_to_press if ch in pressed_chars]
        if must_release_before_press:
            release_keys_simultaneous(must_release_before_press)
            for ch in must_release_before_press:
                pressed_chars.discard(ch)

        # Press all requested chars simultaneously (single SendInput call)
        if chars_to_press:
            press_keys_simultaneous(chars_to_press)
            for ch in chars_to_press:
                pressed_chars.add(ch)

    # After events finished or stopped, release any held keys
    if pressed_chars:
        # release all at once
        release_keys_simultaneous(list(pressed_chars))
        pressed_chars.clear()

# Simple helper to get total duration (seconds) of a MidiFile
def midi_total_length(mid: MidiFile) -> float:
    # compute by converting merged track times with tempo updates
    ticks_per_beat = mid.ticks_per_beat
    merged = mido.merge_tracks(mid.tracks)
    current_tempo = 500000
    total = 0.0
    for msg in merged:
        if msg.time:
            total += tick2second(msg.time, ticks_per_beat, current_tempo)
        if msg.type == 'set_tempo':
            current_tempo = msg.tempo
    return total

# Stop function: set the event
def stop(stop_flag: threading.Event):
    stop_flag.set()

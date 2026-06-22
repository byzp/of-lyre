"""
mido.MidiFile -> 时间事件列表, MIDI note_on/note_off -> Windows 键盘事件（使用 SendInput，提高同时性与精度）。
stop flag 控制可被 GUI 的停止按钮触发。
"""

import os
import sys
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
# _ROW0 = list("ZXCVBNM")   # chords 'C', 'Dm', 'Em', 'F', 'G', 'Am', 'G7'
_ROW1 = list("ASDFGHJ")  # lowest 7 (starting at C3)
_ROW2 = list("QWERTYU")  # middle 7
_ROW3 = list("1234567")  # highest 7


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


_HAS_CUSTOM_MAPPING = False


# Resolve key.txt path: look next to the executable (packaged) or script (dev)
def _app_dir() -> str:
    """Directory containing the executable or script."""
    if getattr(sys, "frozen", False):
        # PyInstaller / Nuitka: executable directory
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _find_key_txt() -> Optional[str]:
    """Find key.txt: exe/script dir first, then cwd."""
    for base in (_app_dir(), os.getcwd()):
        path = os.path.join(base, "key.txt")
        if os.path.exists(path):
            return path
    return None


_key_path = _find_key_txt()

# _NOTE_TO_CHAR: note -> character (for regular keys like 'q', '1', '!')
# _NOTE_TO_VK:   note -> (vk_code, needs_shift) for raw-VK keys like {F1}
_NOTE_TO_CHAR: dict = {}
_NOTE_TO_VK: dict = {}
_pressed_key_id: dict = {}  # note -> stable string key for pressed_chars tracking

if _key_path:
    _HAS_CUSTOM_MAPPING = True
    with open(_key_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            base_note_str, keys_str = line.split(":", 1)
            try:
                base_note = int(base_note_str)
            except ValueError:
                continue

            note_idx = 0
            pos = 0
            while pos < len(keys_str):
                ch = keys_str[pos]

                if ch == "{" and (end := keys_str.find("}", pos + 1)) != -1:
                    # {Fn} escape: function key VK code
                    name = keys_str[pos + 1 : end]
                    if name.startswith("F") and name[1:].isdigit():
                        fn = int(name[1:])
                        if 1 <= fn <= 24:
                            n = base_note + note_idx
                            vk = 0x6F + fn  # VK_F1 = 0x70 .. VK_F24 = 0x87
                            _NOTE_TO_VK[n] = (vk, False)
                            _pressed_key_id[n] = name
                    pos = end + 1
                    note_idx += 1
                elif ch != " ":
                    n = base_note + note_idx
                    _NOTE_TO_CHAR[n] = ch
                    _pressed_key_id[n] = ch
                    pos += 1
                    note_idx += 1
                else:
                    pos += 1
                    note_idx += 1
else:
    _NOTE_TO_CHAR = build_note_to_char_map()
    for n in _NOTE_TO_CHAR:
        _pressed_key_id[n] = _NOTE_TO_CHAR[n]


def _note_info(note: int):
    """Return (key_id, vk_code, needs_shift) for a MIDI note, or (None, 0, False)."""
    ch = _NOTE_TO_CHAR.get(note)
    if ch is not None:
        vk, ns = _char_vk_info(ch)
        return _pressed_key_id[note], vk, ns
    entry = _NOTE_TO_VK.get(note)
    if entry is not None:
        return _pressed_key_id[note], entry[0], entry[1]
    return None, 0, False


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

# VkKeyScanEx: map a character to virtual-key code + shift state
_vk_key_scan = ctypes.windll.user32.VkKeyScanExW
_vk_key_scan.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
_vk_key_scan.restype = ctypes.c_short

VK_SHIFT = 0x10


def _make_key_input(vk: int, is_up: bool = False) -> Input:
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


# helper: get virtual-key and shift state for a character using VkKeyScanEx
def _char_vk_info(ch: str) -> Tuple[int, bool]:
    """Return (vk_code, needs_shift). Returns (0, False) if character has no valid mapping."""
    if not ch:
        return 0, False
    result = _vk_key_scan(ch, None)
    vk = result & 0xFF
    if vk == 0xFF:  # no keyboard mapping found
        return 0, False
    needs_shift = bool((result >> 8) & 0x1)
    return vk, needs_shift


def _resolve_key(key_id: str) -> Tuple[int, bool]:
    """Resolve a key identifier (single char or Fn name) to (vk, needs_shift)."""
    if len(key_id) == 1:
        return _char_vk_info(key_id)
    # Look up raw-VK entries by key_id
    for note, (vk, ns) in _NOTE_TO_VK.items():
        if _pressed_key_id.get(note) == key_id:
            return vk, ns
    return 0, False


def press_keys_simultaneous(chars: List[str], press_shift: bool = False):
    inputs = []
    if press_shift:
        inputs.append(_make_key_input(VK_SHIFT, is_up=False))
    for key_id in chars:
        vk, _ = _resolve_key(key_id)
        if vk:
            inputs.append(_make_key_input(vk, is_up=False))
    if inputs:
        send_inputs(inputs)


def release_keys_simultaneous(chars: List[str], release_shift: bool = False):
    inputs = []
    for key_id in chars:
        vk, _ = _resolve_key(key_id)
        if vk:
            inputs.append(_make_key_input(vk, is_up=True))
    if release_shift:
        inputs.append(_make_key_input(VK_SHIFT, is_up=True))
    if inputs:
        send_inputs(inputs)


# Convert MidiFile -> list of events with absolute time (seconds)
# Each event: (abs_time_seconds, type_str, note, velocity)
# type_str: 'on' or 'off'


def midi_to_events(
    mid: MidiFile, min_time: Optional[float] = None, max_time: Optional[float] = None
) -> List[Tuple[float, str, int, int]]:
    events = []
    ticks_per_beat = mid.ticks_per_beat
    current_tempo = 500000  # default 120 BPM in microseconds per beat
    # merge all tracks into one stream
    merged = mido.merge_tracks(mid.tracks)
    abs_time = 0.0
    # Track notes active before min_time so we can insert synthetic note_on at min_time
    held_before = set()
    crossed_min_time = False

    def _is_mapped(note: int) -> bool:
        if _HAS_CUSTOM_MAPPING:
            return note in _NOTE_TO_CHAR or note in _NOTE_TO_VK
        return 48 <= note <= 83

    for msg in merged:
        # msg.time is delta in ticks
        if msg.time:
            dt = tick2second(msg.time, ticks_per_beat, current_tempo)
            abs_time += dt

        # Insert synthetic note_on for notes still held when crossing min_time
        if min_time is not None and not crossed_min_time and abs_time >= min_time:
            crossed_min_time = True
            for note in held_before:
                events.append((min_time, "on", note, 100))
            held_before.clear()

        # tempo changes
        if msg.type == "set_tempo":
            current_tempo = msg.tempo
            continue

        # Before min_time: only track held notes (don't emit events)
        if min_time is not None and abs_time < min_time:
            if msg.type == "note_on":
                if msg.velocity > 0 and _is_mapped(msg.note):
                    held_before.add(msg.note)
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                held_before.discard(msg.note)
            continue

        if msg.type == "note_on":
            if not _is_mapped(msg.note):
                continue
            if msg.velocity == 0:
                events.append((abs_time, "off", msg.note, 0))
            else:
                events.append((abs_time, "on", msg.note, msg.velocity))
        elif msg.type == "note_off":
            if not _is_mapped(msg.note):
                continue
            events.append((abs_time, "off", msg.note, msg.velocity))
        if max_time is not None and abs_time > max_time:
            break
    if min_time is not None:
        # Shift timestamps so playback starts from 0, not from min_time
        events = [
            (t - min_time, typ, note, vel)
            for t, typ, note, vel in events
            if t >= min_time
        ]
    if max_time is not None and min_time is not None:
        events = [e for e in events if e[0] <= max_time - min_time]
    elif max_time is not None:
        events = [e for e in events if e[0] <= max_time]
    events.sort(key=lambda x: x[0])
    return events


# Play events: send keyboard presses/releases according to event times
def play_events(
    events: List[Tuple[float, str, int, int]],
    stop_flag: threading.Event,
    progress_callback=None,
    spin_threshold: float = 0.005,
    sleep_chunk: float = 0.01,
    progress_interval: float = 0.05,
    raise_priority: bool = True,
):
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

    # Track which characters are currently physically pressed (char -> needs_shift)
    pressed_chars: dict = {}
    shift_held = False

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
    # base_time_zero = groups[0][0]  # usually 0
    base_time_zero = 0  # Ensure ensemble synchronization
    start_wall = time.perf_counter()

    last_progress_time = start_wall

    for event_time, evlist in groups:
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
        offs = [e for e in evlist if e[1] == "off"]
        ons = [e for e in evlist if e[1] == "on"]

        # Process offs: release keys that correspond
        chars_to_release = []
        any_released_needs_shift = False
        for _, _, note, _ in offs:
            key_id, vk, ns = _note_info(note)
            if key_id is None:
                continue
            if key_id in pressed_chars:
                chars_to_release.append(key_id)
                if pressed_chars.pop(key_id):
                    any_released_needs_shift = True
        if chars_to_release:
            # release simultaneously if multiple
            release_shift = any_released_needs_shift and not any(pressed_chars.values())
            release_keys_simultaneous(chars_to_release, release_shift=release_shift)
            if release_shift:
                shift_held = False

        # Process ons: determine chars to press, tracking shift needs
        chars_to_press: list = []  # list of (key_id, needs_shift)
        for _, _, note, _ in ons:
            key_id, vk, ns = _note_info(note)
            if key_id is None:
                continue
            chars_to_press.append((key_id, ns))

        # If a requested char is already pressed: release it first (so retrigger)
        must_release_before_press = [
            ch for ch, _ in chars_to_press if ch in pressed_chars
        ]
        if must_release_before_press:
            for ch in must_release_before_press:
                pressed_chars.pop(ch, None)
            release_keys_simultaneous(must_release_before_press, release_shift=False)
            # If no remaining pressed chars need Shift, release it and sync state
            if shift_held and not any(pressed_chars.values()):
                release_keys_simultaneous([], release_shift=True)
                shift_held = False

        # Press chars. When mixed (shifted + unshifted at same timestamp),
        # drop black keys (shifted chars) to avoid Shift contamination.
        if chars_to_press:
            # Separate into shifted / unshifted
            chars_shifted = [ch for ch, ns in chars_to_press if ns]
            if chars_shifted and len(chars_shifted) < len(chars_to_press):
                # Mixed group: drop black keys, keep only white keys
                chars_to_press = [
                    (ch, ns) for ch, ns in chars_to_press if ch not in chars_shifted
                ]
                chars_shifted = []

            press_shift = False
            if chars_shifted:
                if not shift_held:
                    press_shift = True
            elif shift_held:
                release_keys_simultaneous([], release_shift=True)
                shift_held = False
            press_keys_simultaneous(
                [ch for ch, _ in chars_to_press], press_shift=press_shift
            )
            if press_shift:
                shift_held = True
            for ch, ns in chars_to_press:
                pressed_chars[ch] = ns

    # After events finished or stopped, release any held keys
    if pressed_chars:
        # release all at once
        release_shift = any(pressed_chars.values())
        release_keys_simultaneous(
            list(pressed_chars.keys()), release_shift=release_shift
        )
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
        if msg.type == "set_tempo":
            current_tempo = msg.tempo
    return total


# Stop function: set the event
def stop(stop_flag: threading.Event):
    stop_flag.set()

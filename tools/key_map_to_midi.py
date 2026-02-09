# notation_to_midi.py
"""
将自定义文本乐谱转换为 MIDI 文件。
规则（与用户给定一致）：
- 21 个音：ZXCVBNM, ASDFGHJ, QWERTYU -> C3..B5（白键）
- 括号内的多个字母表示同一时值同时发声（和弦）
- / 为小节分隔符（不消耗时值）
- 空格字符 ' ' 表示一个时值的休止
- 每个时值 = 1 拍（quarter note），可通过 BPM/beat_duration 修改
"""

from mido import Message, MidiFile, MidiTrack, MetaMessage
import sys

# ---------------------------
# 配置参数（可按需修改）
BPM = 400  # 速度，单位：BPM
TICKS_PER_BEAT = 480  # MIDI ticks 每拍（分辨率）
BEATS_PER_UNIT = 1  # 每个记号（字母或括号或空格）占多少拍（1 = 四分音符）
OUTPUT_FILE = "output.mid"
# ---------------------------


# 生成键到 MIDI 音高的映射（白键）
def make_mapping():
    # 21 键的顺序字符串
    keys = "ZXCVBNMASDFGHJQWERTYU"
    # white-key semitone offsets from C: C D E F G A B -> 0,2,4,5,7,9,11
    white_offsets = [0, 2, 4, 5, 7, 9, 11]
    mapping = {}
    # starting octave 3 for ZXCVBNM (C3..B3), then octave 4, then octave 5
    base_octaves = [3, 4, 5]
    idx = 0
    for octv in base_octaves:
        for off in white_offsets:
            if idx >= len(keys):
                break
            letter = keys[idx]
            midi_note = (
                (octv + 0) * 12 + 0 + off
            )  # C_octv midi = 12*octv, we add offset
            # Note: C0 would be midi 0 in this calc if octv=0; with octv=3 it's fine.
            # But standard MIDI middle C (C4) = 60, so C3=48 -> 12*3 = 36; add 12 to align?
            # To make C4=60 we set base = 12 (one octave) -> do adjustment below.
            mapping[letter] = midi_note
            idx += 1
    # The above produced C3 as midi 36; but standard MIDI C4 = 60, so C3 must be 48.
    # Our current mapping is offset by -12; fix by adding +12 to all notes.
    for k in mapping:
        mapping[k] += 12
    return mapping


MAPPING = make_mapping()

# 简单检查
# print(MAPPING)  # 若需要调试可打开


# 解析输入的乐谱文本
def parse_notation(text):
    """
    解析规则：
    - 按字符逐个扫描
    - 遇到 '(' 开始收集直到 ')' -> 作为一个事件，内部多字母表示同时发声（和弦）
    - 遇到字母 A-Z -> 单个字母事件（单音）
    - 遇到空格 ' ' -> 产生一个休止事件（advance time）
    - 遇到 '/' -> 小节分隔符，不消耗时间（跳过）
    返回：事件列表，每项 (tick_index, list_of_letters) 其中 tick_index 为第几个 unit（整数从0起）
    """
    events = []  # list of (unit_index, [letters])
    unit_idx = 0
    i = 0
    skip = 0
    while i < len(text):
        ch = text[i]
        if ch == "#":
            i += 1
            skip = 1
            continue
        if skip:
            i += 1
            if ch == "\t" or ch == "\n" or ch == "\r":
                skip = 0
            continue
        if ch == "(":
            # read until closing ')'
            j = i + 1
            letters = []
            while j < len(text) and text[j] != ")":
                if text[j].isalpha():
                    letters.append(text[j].upper())
                j += 1
            # if no closing ) found, treat until end
            events.append((unit_idx, letters))
            unit_idx += 1
            i = j + 1
        elif ch == "/":
            # barline: skip, no time advance
            i += 1
        elif ch == " ":  # or ch == '\t' or ch == '\n' or ch == '\r':
            # whitespace -> one unit rest (advance time)
            # but avoid multiple consecutive whitespace producing many rest units if user didn't intend?
            # 根据用户描述，空格就是休止，故每个空白字符当作一个单位的休止。
            unit_idx += 1
            i += 1
        else:
            # other chars: if letter, it's a single-note event. 其他字符忽略
            if ch.isalpha():
                events.append((unit_idx, [ch.upper()]))
                unit_idx += 1
            # ignore any other char
            i += 1
    return events


# 将解析结果转换为 MIDI 事件（绝对 ticks 上的 on/off）
def build_midi_events(
    parsed_events, ticks_per_beat=TICKS_PER_BEAT, beats_per_unit=BEATS_PER_UNIT
):
    duration_ticks = int(ticks_per_beat * beats_per_unit)
    scheduled = []  # list of (tick, 'on'/'off', midi_note)
    for unit_idx, letters in parsed_events:
        start_tick = unit_idx * duration_ticks
        # letters为空 -> 这是一个“静默单位”（rest），不安排任何事件
        if not letters:
            continue
        for L in letters:
            if L not in MAPPING:
                print(f"Warning: letter '{L}' not in mapping, skipping.")
                continue
            midi_note = MAPPING[L]
            scheduled.append((start_tick, "on", midi_note))
            scheduled.append((start_tick + duration_ticks, "off", midi_note))
    # sort by tick, and ensure off events come after on events at same tick by ordering
    scheduled.sort(key=lambda x: (x[0], 0 if x[1] == "on" else 1))
    return scheduled


# 把 scheduled events 转为 mido track（使用 delta times）
def scheduled_to_midifile(
    scheduled, bpm=BPM, ticks_per_beat=TICKS_PER_BEAT, out_filename=OUTPUT_FILE
):
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    # tempo meta
    microseconds_per_beat = int(60_000_000 / bpm)
    track.append(MetaMessage("set_tempo", tempo=microseconds_per_beat, time=0))
    # optional track name
    track.append(MetaMessage("track_name", name="Converted", time=0))

    last_tick = 0
    for tick, typ, note in scheduled:
        delta = tick - last_tick
        if delta < 0:
            delta = 0
        if typ == "on":
            track.append(Message("note_on", note=note, velocity=100, time=delta))
        else:
            track.append(Message("note_off", note=note, velocity=0, time=delta))
        last_tick = tick
    # end_of_track: ensure final delta 0
    track.append(MetaMessage("end_of_track", time=0))
    mid.save(out_filename)
    print(f"Saved MIDI to {out_filename}")


# 主流程
def convert_text_to_midi(input_text, out_filename=OUTPUT_FILE):
    parsed = parse_notation(input_text)
    scheduled = build_midi_events(parsed)
    scheduled_to_midifile(scheduled, out_filename=out_filename)


# 如果作为脚本运行，读取文件或标准输入
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # 第一个参数可以是一个文本文件路径，或者直接把乐谱文本作为参数（如果含空格需用引号）
        arg = sys.argv[1]
        try:
            with open(arg, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            # 当作直接传入的乐谱文本
            text = arg
    else:
        print("请把乐谱文本粘贴（EOF 结束），或者将文件路径作为第一个参数。")
        print("结束输入后按 Ctrl-D (Linux/Mac) 或 Ctrl-Z (Windows) 回车。")
        text = sys.stdin.read()

    if not text.strip():
        print("未检测到乐谱文本，退出。")
        sys.exit(1)

    convert_text_to_midi(text, out_filename=OUTPUT_FILE)

"""
shrink_silences.py

用途：
  将 MIDI 文件中“所有音轨之间的长静音（以秒计）”替换为给定的最大时长（秒）。
  保持 tempo 事件和消息顺序，只在 tick 层面压缩静音区间。

依赖：
  pip install mido

用法示例：
  python shrink_silences.py input.mid output.mid --max_silence 2.5

注意：
  - 脚本会考虑文件中的 set_tempo（变速），并把 tick <-> 秒 的转换在整个文件的 tempo 轮廓下正确计算。
  - 静音定义：从“所有 note 都已停止”到“任意 note 再次开始”为一个静音区间（即跨轨道聚合）。
"""

import argparse
import mido
from copy import deepcopy
from math import isclose


def collect_events(mid):
    """
    收集所有 track 中的消息并计算每条消息的绝对 tick（原始文件坐标）。
    返回：
      messages_by_track: list，每项是该轨的 [(abs_tick, msg, index_in_track)]
      all_note_msgs: 全部 note on/off 消息（用于检测静音），格式 [(abs_tick, msg)]
      tempo_changes: list of (abs_tick, tempo_microseconds_per_beat)
    """
    ticks_per_beat = mid.ticks_per_beat
    messages_by_track = []
    all_note_msgs = []
    tempo_changes = []

    for ti, track in enumerate(mid.tracks):
        abs_tick = 0
        track_msgs = []
        for idx, msg in enumerate(track):
            abs_tick += msg.time
            # 保存消息以便重建轨道时使用
            track_msgs.append((abs_tick, msg, idx))
            # tempo 事件
            if msg.is_meta and msg.type == "set_tempo":
                tempo_changes.append((abs_tick, msg.tempo))
            # note 事件（note_on velocity>0 当作开始，note_off 或 note_on vel==0 当作结束）
            if not msg.is_meta and (msg.type == "note_on" or msg.type == "note_off"):
                all_note_msgs.append((abs_tick, msg))
        messages_by_track.append(track_msgs)

    # 确保 tempo_changes 有初始值（MIDI 默认 tempo=500000 microsec/beat）
    # 如果第一个 tempo 不在 tick 0，仍然需要默认 tempo
    tempo_changes.sort(key=lambda x: x[0])
    if len(tempo_changes) == 0 or tempo_changes[0][0] != 0:
        # 在 0 tick 插入默认 tempo（不会重复如果已经有 0）
        tempo_changes.insert(0, (0, 500000))
    return messages_by_track, all_note_msgs, tempo_changes


def compute_seconds_for_events(messages_by_track, tempo_changes, ticks_per_beat):
    """
    基于 tempo_changes 把所有 note 事件映射为绝对秒（用于检测静音）。
    为简单与稳健，把 tempo events 和 note events 合并按 tick 排序后线性扫描来计算秒数。

    返回：
      note_events_sec: list of dict { 'tick':int, 'sec':float, 'msg':mido.Message }
      tempo_events: sorted list of (tick, tempo)
    """
    # 构造合并事件列表，包含 tempo 和 note 事件
    merged = []
    # 收集 note events from messages_by_track
    for track_msgs in messages_by_track:
        for abs_tick, msg, idx in track_msgs:
            if not msg.is_meta and (msg.type in ("note_on", "note_off")):
                merged.append(("note", abs_tick, msg))

    for t_tick, tempo in tempo_changes:
        merged.append(("tempo", t_tick, tempo))

    # sort by tick, tempo events before note events at same tick
    merged.sort(key=lambda x: (x[1], 0 if x[0] == "tempo" else 1))

    # sweep to compute seconds
    last_tick = 0
    cur_tempo = 500000  # default microsec per beat
    sec_acc = 0.0
    note_events_sec = []
    for kind, tick, payload in merged:
        delta_ticks = tick - last_tick
        sec_acc += (delta_ticks * (cur_tempo / 1_000_000.0)) / ticks_per_beat
        last_tick = tick
        if kind == "tempo":
            cur_tempo = payload
        else:
            note_events_sec.append({"tick": tick, "sec": sec_acc, "msg": payload})
    return note_events_sec


def find_silence_intervals(note_events_sec, ticks_per_beat):
    """
    基于按时间排序的 note events (全局聚合) 找到所有 silence intervals（在 note 间的时间区间）
    返回 intervals（按原始 tick 单位）列表：每项为 dict
      { 'start_tick':, 'end_tick':, 'start_sec':, 'end_sec':, 'duration_sec':, 'duration_ticks': }
    """
    # 按秒排序
    note_events_sec.sort(key=lambda x: (x["sec"], x["tick"]))
    # 我们需要模拟“有无音”的状态：note_on (vel>0) => 音开始，note_off 或 note_on vel=0 => 音结束。
    active = set()  # set of (channel, note) 当作活动音符计数
    intervals = []
    last_change_tick = None
    last_change_sec = None
    in_silence = False
    silence_start_tick = None
    silence_start_sec = None

    # We need to process the events in chronological order, but note_events_sec includes both on/off.
    # If multiple events share the same time, we process note-off before note-on to avoid zero-length overlaps producing silence.
    # So sort with note_off first.
    def is_on(ev):
        m = ev["msg"]
        return m.type == "note_on" and m.velocity > 0

    def is_off(ev):
        m = ev["msg"]
        return (m.type == "note_off") or (m.type == "note_on" and m.velocity == 0)

    # Build sorted events list with a stable ordering preference: off before on at same time
    events = sorted(note_events_sec, key=lambda e: (e["sec"], 0 if is_off(e) else 1))

    # find first note event time (start of music) and last note event time (end of music)
    if not events:
        return []  # no notes at all -> nothing to do

    # iterate
    for ev in events:
        m = ev["msg"]
        ch_note = (getattr(m, "channel", None), getattr(m, "note", None))
        if is_on(ev):
            # if was in silence, that silence ends here
            if len(active) == 0:
                # silence ended at this event.time
                if silence_start_tick is not None:
                    intervals.append(
                        {
                            "start_tick": silence_start_tick,
                            "end_tick": ev["tick"],
                            "start_sec": silence_start_sec,
                            "end_sec": ev["sec"],
                            "duration_sec": ev["sec"] - silence_start_sec,
                            "duration_ticks": ev["tick"] - silence_start_tick,
                        }
                    )
                    silence_start_tick = None
                    silence_start_sec = None
            active.add(ch_note)
        elif is_off(ev):
            # remove one instance if present
            if ch_note in active:
                active.remove(ch_note)
            # if becomes empty, start a silence
            if len(active) == 0:
                silence_start_tick = ev["tick"]
                silence_start_sec = ev["sec"]

    # We only consider silences that are strictly between notes; trailing silence after last note is ignored by this algorithm.
    # (User said "note 之间", 所以这是合适的。)
    return intervals


def compute_intervals_to_shrink(intervals, max_silence_seconds):
    """
    对找到的 silence intervals，计算需要压缩的比例 r（<=1）以及将减少多少 ticks。
    返回包含每个 interval 的扩展字典，字段包括 r, orig_len_ticks, new_len_ticks, shrink_ticks
    """
    out = []
    for it in intervals:
        orig_sec = it["duration_sec"]
        orig_ticks = it["duration_ticks"]
        if orig_sec <= max_silence_seconds or orig_ticks == 0:
            r = 1.0
            new_ticks = orig_ticks
            shrink = 0
        else:
            r = max_silence_seconds / orig_sec  # 比例缩放
            new_ticks = int(round(orig_ticks * r))
            if new_ticks < 0:
                new_ticks = 0
            shrink = orig_ticks - new_ticks
        d = it.copy()
        d.update(
            {
                "r": r,
                "orig_ticks": orig_ticks,
                "new_ticks": new_ticks,
                "shrink_ticks": shrink,
            }
        )
        out.append(d)
    return out


def map_tick(orig_tick, intervals_sorted):
    """
    将原始 tick 映射为新的 tick，intervals_sorted 基于原始坐标、按 start 升序，
    每项包含 start_tick, end_tick, r, shrink_ticks, orig_ticks, new_ticks。
    使用基于 orig_tick 的逻辑（参见说明），返回整数 new_tick。
    """
    shrink_before = 0
    for it in intervals_sorted:
        s = it["start_tick"]
        e = it["end_tick"]
        r = it["r"]
        orig_len = it["orig_ticks"]
        new_len = it["new_ticks"]
        shrink = it["shrink_ticks"]
        if orig_tick < s:
            return orig_tick - shrink_before
        elif s <= orig_tick < e:
            # 在该静音内部，按比例缩放相对于段起点的偏移
            inside = orig_tick - s
            mapped_inside = int(round(inside * r))
            return s - shrink_before + mapped_inside
        else:
            # 在该静音之后：累积前面所有静音的缩减
            shrink_before += shrink
    return orig_tick - shrink_before


def rebuild_midi(mid, messages_by_track, intervals_to_shrink, output_path):
    """
    根据 intervals_to_shrink 映射所有 messages 的绝对 ticks，再按轨道重建 delta times 并保存文件。
    """
    # 按 start_tick 排序 intervals
    intervals_sorted = sorted(intervals_to_shrink, key=lambda x: x["start_tick"])

    # 计算所有消息的新绝对 tick（按轨道）
    new_mid = mido.MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
    total_shrunk = 0
    for track_msgs in messages_by_track:
        # track_msgs: list of (abs_tick,msg,idx)
        new_track = mido.MidiTrack()
        # 保持原始轨道顺序的同时根据每条消息原始 abs_tick 做映射
        prev_new_abs = 0
        for abs_tick, msg, idx in track_msgs:
            new_abs = map_tick(abs_tick, intervals_sorted)
            if new_abs < 0:
                new_abs = 0
            delta = new_abs - prev_new_abs
            if delta < 0:
                # 安全兜底：出现负值就置为 0（通常不会发生）
                delta = 0
            new_msg = msg.copy(time=delta)
            new_track.append(new_msg)
            prev_new_abs = new_abs
        new_mid.tracks.append(new_track)

    # 统计总共减少的 ticks（可选反馈）
    total_orig = sum(it["orig_ticks"] for it in intervals_sorted)
    total_new = sum(it["new_ticks"] for it in intervals_sorted)
    total_shrunk = total_orig - total_new

    new_mid.save(output_path)
    return total_shrunk, intervals_sorted


def main():
    parser = argparse.ArgumentParser(
        description="Shrink long silences (across all tracks) in a MIDI file."
    )
    parser.add_argument("input_mid", help="输入 MIDI 文件 (.mid)")
    parser.add_argument("output_mid", help="输出 MIDI 文件 (.mid)")
    parser.add_argument(
        "--max_silence",
        "-m",
        type=float,
        required=True,
        help="允许的最大静音长度（秒），超过则压缩到此长度",
    )
    args = parser.parse_args()

    mid = mido.MidiFile(args.input_mid)
    print(
        f"读取 MIDI：{args.input_mid}  ticks_per_beat={mid.ticks_per_beat}, tracks={len(mid.tracks)}"
    )

    messages_by_track, all_note_msgs, tempo_changes = collect_events(mid)
    note_events_sec = compute_seconds_for_events(
        messages_by_track, tempo_changes, mid.ticks_per_beat
    )

    intervals = find_silence_intervals(note_events_sec, mid.ticks_per_beat)
    if not intervals:
        print("未检测到 song 中的跨轨道 note 之间的静音区间（可能无音符），没有修改。")
        return

    intervals_to_shrink = compute_intervals_to_shrink(intervals, args.max_silence)
    # 过滤出需要实际压缩的区间（shrink_ticks > 0）
    to_actually_shrink = [it for it in intervals_to_shrink if it["shrink_ticks"] > 0]
    if not to_actually_shrink:
        print("所有静音区间都不超过给定最大静音长度，未修改。")
        return

    total_shrunk, used_intervals = rebuild_midi(
        mid, messages_by_track, to_actually_shrink, args.output_mid
    )

    print(f"完成。写入：{args.output_mid}")
    print(
        f"共压缩 {len(used_intervals)} 段静音，总共减少 {total_shrunk} ticks（tick数会随文件 tempo/ticks_per_beat 不同而意义不同）。"
    )
    print("已压缩区间（原始 ticks -> 新 ticks, 原始秒 -> 新秒 ≈ max_silence）：")
    for it in used_intervals:
        print(
            f"  ticks {it['start_tick']} -> {it['end_tick']}  : {it['orig_ticks']} -> {it['new_ticks']}, secs {it['duration_sec']:.3f} -> {it['r']*it['duration_sec']:.3f}"
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
batch_midi_transpose.py

功能：
- 遍历输入文件夹内所有 .mid/.midi 文件
- 在给定移调范围内选择一个整体移调，使得落在 C3-B5（含，MIDI 号 48-83）且为白键的 note 数量最大
- 应用该移调，统计低于 C3、C3-B5（逐半音）和高于 B5 的 note 分布并打印
- 根据三个阈值筛选并保存符合条件的 MIDI 到输出文件夹

默认阈值：
- min_within_pct: 在 C3-B5 范围内的 notes 比例至少为 0.60
- max_below_pct: 低于 C3 的 notes 比例最大为 0.20
- max_above_pct: 高于 B5 的 notes 比例最大为 0.20
"""

import os
import argparse
from pathlib import Path
from collections import Counter, OrderedDict
import pretty_midi
import numpy as np
from tqdm import tqdm

WHITE_PITCH_CLASSES = {0, 2, 4, 5, 7, 9, 11}  # C, D, E, F, G, A, B
C3 = 48
B5 = 83
MIN_MIDI = 0
MAX_MIDI = 127


def is_white_key(midi_note):
    return (midi_note % 12) in WHITE_PITCH_CLASSES


def gather_all_note_pitches(pm: pretty_midi.PrettyMIDI, include_drums=False):
    """收集 MIDI 中所有 note 的 pitch（整数 midi note numbers）"""
    pitches = []
    for inst in pm.instruments:
        if inst.is_drum and not include_drums:
            continue
        for n in inst.notes:
            pitches.append(int(round(n.pitch)))
    return pitches


def transpose_counts_for_shift(pitches, shift):
    """计算将 pitches 全部加上 shift 后落在 C3-B5 且为白键的数量"""
    shifted = [p + shift for p in pitches]
    count = 0
    for p in shifted:
        if p < MIN_MIDI or p > MAX_MIDI:
            continue
        if C3 <= p <= B5 and is_white_key(p):
            count += 1
    return count


def apply_transpose_to_pretty_midi(pm: pretty_midi.PrettyMIDI, shift):
    """直接修改 pretty_midi 对象里的 note.pitch，截断到 [0,127]"""
    for inst in pm.instruments:
        for n in inst.notes:
            newp = int(round(n.pitch)) + shift
            if newp < MIN_MIDI:
                newp = MIN_MIDI
            if newp > MAX_MIDI:
                newp = MAX_MIDI
            n.pitch = newp


def compute_stats(pitches):
    """给定 pitch 列表，计算低于C3、C3-B5(按半音)和高于B5 的计数与比例"""
    total = len(pitches)
    if total == 0:
        return {
            "total": 0,
            "below_count": 0,
            "above_count": 0,
            "below_pct": 0.0,
            "above_pct": 0.0,
            "inrange_counts": {},
            "inrange_pcts": {},
        }
    below = [p for p in pitches if p < C3]
    above = [p for p in pitches if p > B5]
    inrange = [p for p in pitches if C3 <= p <= B5]

    inrange_counts = Counter(inrange)
    # ensure all semitones in range appear in ordered dict for stable output
    inrange_ordered_counts = OrderedDict()
    for midi_note in range(C3, B5 + 1):
        inrange_ordered_counts[midi_note] = inrange_counts.get(midi_note, 0)
    inrange_pcts = {k: (v / total) for k, v in inrange_ordered_counts.items()}

    stats = {
        "total": total,
        "below_count": len(below),
        "above_count": len(above),
        "below_pct": len(below) / total,
        "above_pct": len(above) / total,
        "inrange_counts": inrange_ordered_counts,
        "inrange_pcts": inrange_pcts,
    }
    return stats


def choose_best_transposition(pitches, min_shift=-24, max_shift=24):
    """在 [min_shift, max_shift] 范围内选取一个移调，使落在 C3-B5 且为白键的数量最大。
    tie-breaker: 选择 abs(shift) 最小的；再 tie 则选择正的 shift（向上）"""
    best = None  # (count, abs_shift, -sign, shift) 用于比较
    best_shift = 0
    for shift in range(min_shift, max_shift + 1):
        cnt = transpose_counts_for_shift(pitches, shift)
        key = (cnt, -abs(shift), 1 if shift > 0 else (0 if shift == 0 else -1))
        # 我们希望最大 cnt, 然后 prefer 小的 abs(shift) -> 即更接近原调（所以 key includes -abs(shift))
        if best is None or key > best:
            best = key
            best_shift = shift
    return best_shift


def process_file(path_in: Path, path_out_dir: Path, args):
    try:
        pm = pretty_midi.PrettyMIDI(str(path_in))
    except Exception as e:
        print(f"[ERROR] 无法读取 MIDI 文件 {path_in}: {e}")
        return None

    # 收集原始音高（非鼓）
    pitches = gather_all_note_pitches(pm, include_drums=False)
    if len(pitches) == 0:
        print(
            f"[WARN] 文件 {path_in.name} 不包含可统计的 note（或全部为 drum 并被忽略）。跳过统计。"
        )
        return None

    best_shift = choose_best_transposition(pitches, args.min_shift, args.max_shift)

    # 复制一个 pretty_midi 对象或直接在原上操作？我们在内存中复制，保留原 pm 用于不破坏源
    pm_trans = pretty_midi.PrettyMIDI(str(path_in))  # 重新读取以做改动
    apply_transpose_to_pretty_midi(pm_trans, best_shift)

    # 统计移调后的音高
    pitches_after = gather_all_note_pitches(pm_trans, include_drums=False)
    stats = compute_stats(pitches_after)
    stats["chosen_shift"] = best_shift

    # 打印统计结果
    print("=" * 60)
    print(f"File: {path_in.name}")
    print(f"Chosen transpose (semitones): {best_shift}")
    print(f"Total notes counted: {stats['total']}")
    print(f"Below C3 (<{C3}): {stats['below_count']} ({stats['below_pct']:.2%})")
    print(f"In C3-B5 ({C3}-{B5}) per-semitone proportions:")
    # 打印每个半音的比例，按 midi note 显示音名也可以，但这里先用 midi 号和百分比
    for midi_note, cnt in stats["inrange_counts"].items():
        pct = stats["inrange_pcts"][midi_note]
        if cnt > 0:
            print(f"  {midi_note:3d} : count={cnt:4d}, pct={pct:.2%}")
    print(f"Above B5 (>{B5}): {stats['above_count']} ({stats['above_pct']:.2%})")

    # 判断是否满足阈值要求（默认或用户给定）
    meets = True
    if stats["total"] > 0:
        if stats["inrange_counts"] is not None:
            within_pct = (
                sum(stats["inrange_counts"].values()) / stats["total"]
            )  # 这一值等于 1 - below - above
        else:
            within_pct = 0.0
        if within_pct < args.min_within_pct - 1e-12:
            meets = False
        if stats["below_pct"] > args.max_below_pct + 1e-12:
            meets = False
        if stats["above_pct"] > args.max_above_pct + 1e-12:
            meets = False
    else:
        meets = False

    if meets:
        # 保存处理后的 MIDI 到输出文件夹，文件名保持原名并加后缀
        out_name = f"{path_in.stem}_trans{best_shift:+d}{path_in.suffix}"
        out_path = path_out_dir / out_name
        try:
            pm_trans.write(str(out_path))
            print(f"[SAVED] 符合阈值，已保存到: {out_path}")
        except Exception as e:
            print(f"[ERROR] 保存文件失败: {e}")
    else:
        print("[SKIP] 未满足阈值要求，未保存文件。")

    return {"path": path_in, "stats": stats, "saved": meets}


def main():
    parser = argparse.ArgumentParser(
        description="批量读取 MIDI，移调以最大化 C3-B5 白键数量，统计并按阈值保存。"
    )
    parser.add_argument(
        "--input_dir", "-i", required=True, help="输入文件夹（包含 .mid/.midi 文件）"
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        required=True,
        help="输出文件夹（保存符合阈值的处理后 MIDI）",
    )
    parser.add_argument(
        "--min_within_pct",
        type=float,
        default=0.60,
        help="保存阈值：C3-B5 范围内 note 占比最少（0-1），默认 0.60",
    )
    parser.add_argument(
        "--max_below_pct",
        type=float,
        default=0.20,
        help="保存阈值：低于 C3 的 note 占比最大（0-1），默认 0.20",
    )
    parser.add_argument(
        "--max_above_pct",
        type=float,
        default=0.20,
        help="保存阈值：高于 B5 的 note 占比最大（0-1），默认 0.20",
    )
    parser.add_argument(
        "--min_shift", type=int, default=-24, help="移调搜索最小半音 (默认 -24)"
    )
    parser.add_argument(
        "--max_shift", type=int, default=24, help="移调搜索最大半音 (默认 +24)"
    )
    parser.add_argument(
        "--include_drums",
        action="store_true",
        help="是否包含 drum 通道的 note 统计（默认不包含）",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    midi_files = sorted(
        [p for p in input_dir.iterdir() if p.suffix.lower() in (".mid", ".midi")]
    )
    if not midi_files:
        print("指定输入文件夹中没有 .mid 或 .midi 文件。")
        return

    results = []
    for p in tqdm(midi_files, desc="Processing MIDIs"):
        res = process_file(p, output_dir, args)
        if res is not None:
            results.append(res)

    print("\n批处理完成。已处理文件数:", len(results))
    saved_count = sum(1 for r in results if r["saved"])
    print(f"符合阈值并已保存的文件数: {saved_count}/{len(results)}")
    print(
        "默认阈值说明：min_within_pct (C3-B5 占比 最小), max_below_pct (低于 C3 占比 最大), max_above_pct (高于 B5 占比 最大)"
    )
    print(
        "若需调整阈值，请使用命令行参数 --min_within_pct/--max_below_pct/--max_above_pct"
    )


if __name__ == "__main__":
    main()

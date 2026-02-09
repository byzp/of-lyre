#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_midi_transpose_mt.py

功能：
- 批量读取输入文件夹内 .mid/.midi 文件
- 在给定移调范围内选择一个整体移调，使得落在 C3-B5（含，MIDI 号 48-83）且为白键的 note 数量最大
- 应用该移调并统计：低于C3、C3-B5(按半音)和高于B5 的分布
- 按用户指定的三个阈值保存符合条件的 MIDI 到输出文件夹
- 使用多进程并行处理：自动检测 CPU 核心并分配任务

用法示例：
python batch_midi_transpose_mt.py -i /path/to/in -o /path/to/out --workers 8
"""
import os
import argparse
from pathlib import Path
from collections import Counter, OrderedDict
import pretty_midi
import numpy as np
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback

# optional psutil for physical core count (not required)
try:
    import psutil
except Exception:
    psutil = None

WHITE_PITCH_CLASSES = {0, 2, 4, 5, 7, 9, 11}  # C, D, E, F, G, A, B
C3 = 48
B5 = 83
MIN_MIDI = 0
MAX_MIDI = 127


def is_white_key(midi_note):
    return (midi_note % 12) in WHITE_PITCH_CLASSES


def gather_all_note_pitches(pm: pretty_midi.PrettyMIDI, include_drums=False):
    pitches = []
    for inst in pm.instruments:
        if inst.is_drum and not include_drums:
            continue
        for n in inst.notes:
            pitches.append(int(round(n.pitch)))
    return pitches


def transpose_counts_for_shift(pitches, shift):
    shifted = [p + shift for p in pitches]
    count = 0
    for p in shifted:
        if p < MIN_MIDI or p > MAX_MIDI:
            continue
        if C3 <= p <= B5 and is_white_key(p):
            count += 1
    return count


def apply_transpose_to_pretty_midi(pm: pretty_midi.PrettyMIDI, shift):
    for inst in pm.instruments:
        for n in inst.notes:
            newp = int(round(n.pitch)) + shift
            if newp < MIN_MIDI:
                newp = MIN_MIDI
            if newp > MAX_MIDI:
                newp = MAX_MIDI
            n.pitch = newp


def compute_stats(pitches):
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
    best = None
    best_shift = 0
    for shift in range(min_shift, max_shift + 1):
        cnt = transpose_counts_for_shift(pitches, shift)
        # 优先最大 cnt, 然后 prefer abs(shift) 小（更接近原调）, 再 prefer 正 shift
        key = (cnt, -abs(shift), 1 if shift > 0 else (0 if shift == 0 else -1))
        if best is None or key > best:
            best = key
            best_shift = shift
    return best_shift


def worker_process_file(args_tuple):
    """
    Worker executed in separate process.
    args_tuple: (path_str, out_dir_str, settings_dict)
    """
    path_str, out_dir_str, settings = args_tuple
    path = Path(path_str)
    out_dir = Path(out_dir_str)
    try:
        pm = pretty_midi.PrettyMIDI(str(path))
    except Exception as e:
        return {"path": path_str, "error": f"Cannot read MIDI: {e}", "saved": False}

    pitches = gather_all_note_pitches(
        pm, include_drums=settings.get("include_drums", False)
    )
    if len(pitches) == 0:
        return {
            "path": path_str,
            "error": "No notes to analyze (or all drums and drums excluded).",
            "saved": False,
        }

    best_shift = choose_best_transposition(
        pitches, settings.get("min_shift", -24), settings.get("max_shift", 24)
    )

    # 重新读取以便不改变输入对象（并在 worker 里做保存）
    pm_trans = pretty_midi.PrettyMIDI(str(path))
    apply_transpose_to_pretty_midi(pm_trans, best_shift)

    pitches_after = gather_all_note_pitches(
        pm_trans, include_drums=settings.get("include_drums", False)
    )
    stats = compute_stats(pitches_after)
    stats["chosen_shift"] = best_shift

    total = stats["total"]
    within_count = (
        sum(stats["inrange_counts"].values())
        if isinstance(stats["inrange_counts"], dict)
        else 0
    )
    within_pct = within_count / total if total > 0 else 0.0

    meets = True
    if total == 0:
        meets = False
    else:
        if within_pct < settings.get("min_within_pct", 0.6) - 1e-12:
            meets = False
        if stats["below_pct"] > settings.get("max_below_pct", 0.2) + 1e-12:
            meets = False
        if stats["above_pct"] > settings.get("max_above_pct", 0.2) + 1e-12:
            meets = False

    save_all = settings.get("save_all", False)
    saved = False
    out_path = None
    if meets or save_all:
        out_name = f"{path.stem}_trans{best_shift:+d}{path.suffix}"
        out_path = out_dir / out_name
        try:
            pm_trans.write(str(out_path))
            saved = True
        except Exception as e:
            return {"path": path_str, "error": f"Write failed: {e}", "saved": False}

    # 返回尽量紧凑的结果，避免过大的返回体
    return {
        "path": path_str,
        "chosen_shift": best_shift,
        "total": total,
        "below_count": stats["below_count"],
        "below_pct": stats["below_pct"],
        "above_count": stats["above_count"],
        "above_pct": stats["above_pct"],
        "within_count": within_count,
        "within_pct": within_pct,
        "saved": saved,
        "out_path": str(out_path) if out_path else None,
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="批量 MIDI 移调并按阈值保存（支持多进程）"
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
        help="保存阈值：C3-B5 范围内 note 占比至少（0-1），默认 0.60",
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
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="并行 worker 数（默认检测到的 CPU 数）",
    )
    parser.add_argument(
        "--save_all",
        action="store_true",
        help="是否保存所有处理后的 MIDI（不按阈值筛选）",
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

    # detect CPU info
    logical_cores = os.cpu_count() or 1
    physical_cores = None
    if psutil:
        try:
            physical_cores = psutil.cpu_count(logical=False)
        except Exception:
            physical_cores = None

    workers = args.workers if args.workers and args.workers > 0 else logical_cores
    workers = min(workers, len(midi_files)) if len(midi_files) > 0 else workers

    print(
        f"系统检测到逻辑 CPU: {logical_cores}"
        + (f", 物理 CPU: {physical_cores}" if physical_cores else "")
    )
    print(f"使用 worker 数: {workers}")
    approx_per_worker = len(midi_files) // workers
    print(
        f"共 {len(midi_files)} 个文件，约分配每个 worker 处理 ~{approx_per_worker} 个（任务由调度器分配）"
    )

    # prepare settings for workers (simple dict -> 可序列化)
    settings = {
        "min_shift": args.min_shift,
        "max_shift": args.max_shift,
        "min_within_pct": args.min_within_pct,
        "max_below_pct": args.max_below_pct,
        "max_above_pct": args.max_above_pct,
        "include_drums": args.include_drums,
        "save_all": args.save_all,
    }

    tasks = [(str(p), str(output_dir), settings) for p in midi_files]

    results = []
    saved_count = 0
    processed = 0

    # Use ProcessPoolExecutor to parallelize worker_process_file
    with ProcessPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(worker_process_file, t): t[0] for t in tasks}
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Processing MIDIs"
        ):
            processed += 1
            try:
                res = future.result()
            except Exception as e:
                # 捕获 worker 异常
                tb = traceback.format_exc()
                print(f"[ERROR] 处理文件时发生异常: {e}\n{tb}")
                continue
            results.append(res)
            # 主进程统一打印结果
            path = Path(res.get("path"))
            if res.get("error"):
                print(
                    f"[{processed}/{len(midi_files)}] {path.name} 处理失败: {res.get('error')}"
                )
                continue
            saved_str = "SAVED" if res.get("saved") else "SKIPPED"
            if res.get("saved"):
                saved_count += 1
            print(
                f"[{processed}/{len(midi_files)}] {path.name} | shift={res.get('chosen_shift'):+d} | "
                f"total={res.get('total')} | below={res.get('below_count')}({res.get('below_pct'):.2%}) | "
                f"within={res.get('within_count')}({res.get('within_pct'):.2%}) | "
                f"above={res.get('above_count')}({res.get('above_pct'):.2%}) -> {saved_str}"
                + (f" -> {res.get('out_path')}" if res.get("out_path") else "")
            )

    print("\n批处理完成。")
    print(f"已处理文件: {len(results)} / {len(midi_files)}")
    print(f"符合（或已保存）文件数: {saved_count}")


if __name__ == "__main__":
    main()

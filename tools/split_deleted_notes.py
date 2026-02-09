#!/usr/bin/env python3
"""
split_deleted_notes.py

用法:
    python split_deleted_notes.py full.mid reduced.mid output.mid
可选参数:
    --start-tol  起始时间容差（秒），默认 0.05
    --dur-tol    时长容差（秒），默认 0.05
    --verbose    打印处理摘要
说明:
    将 reduced.mid 作为主文件，找出 full.mid 中但不在 reduced.mid 中的 notes，
    并把这些被删除的 notes 按原 instrument（program/is_drum）放到新的 track 中。
"""
import argparse
import pretty_midi
import copy
from collections import defaultdict


def parse_args():
    p = argparse.ArgumentParser(description="Split deleted notes from two MIDI files.")
    p.add_argument("full", help="原始（含更多 note）的 MIDI 文件路径")
    p.add_argument("reduced", help="删除了一些 note 的 MIDI 文件路径（作为主音轨）")
    p.add_argument("out", help="输出 MIDI 文件路径")
    p.add_argument(
        "--start-tol", type=float, default=0.05, help="起始时间容差（秒），默认 0.05"
    )
    p.add_argument(
        "--dur-tol", type=float, default=0.05, help="时长容差（秒），默认 0.05"
    )
    p.add_argument("--verbose", action="store_true", help="打印详细信息")
    return p.parse_args()


def note_matches(n1, n2, start_tol=0.05, dur_tol=0.05):
    """
    n1, n2: pretty_midi.Note
    match if pitch equal and start/duration within tolerance
    """
    if n1.pitch != n2.pitch:
        return False
    if abs(n1.start - n2.start) > start_tol:
        return False
    if abs((n1.end - n1.start) - (n2.end - n2.start)) > dur_tol:
        return False
    return True


def build_reduced_note_index(reduced_pm):
    """
    返回一个方便检索的列表（或字典）。为简单实现，这里收集 reduced 中的所有 note 为一个列表。
    """
    reduced_notes = []
    for inst in reduced_pm.instruments:
        for n in inst.notes:
            reduced_notes.append(n)
    return reduced_notes


def find_deleted_notes(full_pm, reduced_notes, start_tol=0.05, dur_tol=0.05):
    """
    遍历 full_pm 的每个 instrument 的每个 note，
    如果在 reduced_notes 中找不到匹配，则认为是 deleted note。
    返回：dict mapping full_inst_index -> [note, ...]（这些 note 来自 full）
    """
    deleted_by_inst = defaultdict(list)
    # 为提高速度，可把 reduced_notes 按 pitch 分桶
    reduced_by_pitch = defaultdict(list)
    for rn in reduced_notes:
        reduced_by_pitch[rn.pitch].append(rn)

    for i, inst in enumerate(full_pm.instruments):
        for n in inst.notes:
            candidates = reduced_by_pitch.get(n.pitch, [])
            matched = False
            # 线性搜索候选（pitch 相同的）以判断是否存在匹配 note
            for rn in candidates:
                if note_matches(n, rn, start_tol=start_tol, dur_tol=dur_tol):
                    matched = True
                    break
            if not matched:
                deleted_by_inst[i].append(n)
    return deleted_by_inst


def main():
    args = parse_args()
    full_pm = pretty_midi.PrettyMIDI(args.full)
    reduced_pm = pretty_midi.PrettyMIDI(args.reduced)

    reduced_notes = build_reduced_note_index(reduced_pm)
    deleted_by_inst = find_deleted_notes(
        full_pm, reduced_notes, start_tol=args.start_tol, dur_tol=args.dur_tol
    )

    # 深拷贝 reduced_pm 以保留 tempo/其他 meta 信息
    out_pm = copy.deepcopy(reduced_pm)

    total_deleted = 0
    for inst_idx, deleted_notes in deleted_by_inst.items():
        if not deleted_notes:
            continue
        src_inst = full_pm.instruments[inst_idx]
        # 创建新的 instrument 放置被删除的 notes，保留 program/is_drum
        new_name = (
            f"deleted_from_{src_inst.name or ('program_' + str(src_inst.program))}"
        )
        del_inst = pretty_midi.Instrument(
            program=src_inst.program, is_drum=src_inst.is_drum, name=new_name
        )
        for n in deleted_notes:
            # 复制 note（pitch, start, end, velocity）
            new_note = pretty_midi.Note(
                velocity=getattr(n, "velocity", 100),
                pitch=n.pitch,
                start=n.start,
                end=n.end,
            )
            del_inst.notes.append(new_note)
            total_deleted += 1
        out_pm.instruments.append(del_inst)

    out_pm.write(args.out)

    if args.verbose:
        print(f"读取 full: {args.full}")
        print(f"读取 reduced: {args.reduced}")
        print(f"写入输出: {args.out}")
        print(f"容差: start_tol={args.start_tol}s, dur_tol={args.dur_tol}s")
        print(
            f"共检测到 {sum(len(inst.notes) for inst in full_pm.instruments)} notes（full）"
        )
        print(f"reduced 中 notes 数量: {len(reduced_notes)}")
        print(f"被判定为 deleted 的 notes 总计: {total_deleted}")
        print(
            "为每个有 deleted note 的原始 instrument 新建了一个 track（名称以 deleted_from_ 开头）"
        )


if __name__ == "__main__":
    main()

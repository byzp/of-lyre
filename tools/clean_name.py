#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rename_clean.py
批量重命名文件：
 - 去掉前导的数字和短横，例如 "00566-"
 - 去掉所有以 "_trans" 开头的片段，能匹配：
     _trans, _trans+0, _trans- , _trans-12, _trans+3 等变体
 - 保留扩展名（支持多重后缀，如 .tar.gz）
 - 支持递归、dry-run、按 glob 模式筛选（例如只处理 *.mid）

用法示例：
  # 预览（dry-run）当前目录所有文件
  python3 rename_clean.py --dry-run

  # 递归处理，只处理 .mid 文件并实际改名（需确认）
  python3 rename_clean.py -r -p "*.mid"

  # 指定目录并自动确认
  python3 rename_clean.py -d /path/to/files --yes
"""

import argparse
import re
from pathlib import Path
import fnmatch
import sys

# 清理文件名主体（不含扩展名）
def clean_name(filename: str) -> str:
    p = Path(filename)
    stem = p.stem
    suffix = ''.join(p.suffixes)  # 支持 .tar.gz 等

    # 1) 去掉前导的数字加短横，例如 "00566-"
    stem = re.sub(r'^\d+-', '', stem)

    # 2) 去掉所有以 _trans 开头的片段，模式能匹配：
    #    _trans
    #    _trans+0
    #    _trans-      (只有减号也匹配)
    #    _trans-12
    #    _trans+3
    # 说明：使用全局替换以删除所有出现
    stem = re.sub(r'_trans[+\-]?\d*', '', stem)

    # 3) 将连续多个下划线压缩为一个（可选）
    stem = re.sub(r'__+', '_', stem)

    # 4) 去掉首尾下划线/空格
    stem = stem.strip('_ ').strip()

    # 如果去掉后为空名，退回原始 stem（避免生成无名文件）
    if stem == '':
        stem = p.stem

    return stem + suffix

def iter_files(base: Path, recursive: bool, pattern: str):
    if recursive:
        for p in base.rglob('*'):
            if p.is_file():
                if pattern is None or fnmatch.fnmatch(p.name, pattern):
                    yield p
    else:
        for p in base.iterdir():
            if p.is_file():
                if pattern is None or fnmatch.fnmatch(p.name, pattern):
                    yield p

def main():
    ap = argparse.ArgumentParser(description="批量移除文件名中的前导数字- 和 _trans 变体")
    ap.add_argument('-d', '--dir', default='.', help='目标目录（默认当前目录）')
    ap.add_argument('-r', '--recursive', action='store_true', help='递归子目录')
    ap.add_argument('--dry-run', action='store_true', help='仅显示将要执行的更名，不实际修改')
    ap.add_argument('--yes', action='store_true', help='直接执行，无需交互（慎用）')
    ap.add_argument('-p', '--pattern', default=None,
                    help='按文件名 glob 模式筛选（例如 "*.mid" 或 "*.wav"），默认处理所有文件')
    args = ap.parse_args()

    base = Path(args.dir)
    if not base.exists() or not base.is_dir():
        print(f"目录不存在或不是文件夹：{base}", file=sys.stderr)
        sys.exit(1)

    files = list(iter_files(base, args.recursive, args.pattern))
    ops = []
    for p in files:
        new_name = clean_name(p.name)
        if new_name != p.name:
            target = p.with_name(new_name)
            ops.append((p, target))

    if not ops:
        print("没有发现需要重命名的文件。")
        return

    print(f"发现 {len(ops)} 个待重命名文件（目录：{base}，模式：{args.pattern or '*'}，{'递归' if args.recursive else '不递归'}）：")
    for src, dst in ops:
        print(f"  {src}  ->  {dst}")

    if args.dry_run:
        print("\n已执行 dry-run（未做实际更名）。")
        return

    if not args.yes:
        ans = input("\n确认执行这些重命名操作？输入 y 确认： ").strip().lower()
        if ans != 'y':
            print("已取消。")
            return

    # 执行重命名，若目标已存在则按规则处理：在目标存在时附加索引避免覆盖
    for src, dst in ops:
        final_dst = dst
        if final_dst.exists():
            # 给出一个不会覆盖的备用名字，例如 name (1).ext
            base_name = Path(final_dst.stem)
            suffixes = ''.join(final_dst.suffixes)
            i = 1
            while True:
                candidate = final_dst.with_name(f"{base_name}-{i}{suffixes}")
                if not candidate.exists():
                    final_dst = candidate
                    break
                i += 1
        try:
            src.rename(final_dst)
            print(f"已重命名：{src} -> {final_dst}")
        except Exception as e:
            print(f"重命名失败：{src} -> {final_dst}，错误：{e}")

if __name__ == '__main__':
    main()

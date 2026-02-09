"""
自动化脚本, 循环演奏在线曲库的mid, 无ui
"""

import requests
import io
import time
import threading
from collections import deque
from typing import List, Dict, Set, Any
import argparse
import sys
import mido

from core import midi_to_events, play_events, midi_total_length, stop as core_stop


def fetch_all_latest_songs(
    base_url: str, page_size: int = 50, timeout: int = 5
) -> List[Dict[str, Any]]:
    # Fetch all pages from /latest_songs; return list in API order (newest->old assumed)
    songs: List[Dict[str, Any]] = []
    page = 1
    while True:
        try:
            r = requests.get(
                f"{base_url.rstrip('/')}/latest_songs",
                params={"page": page, "page_size": page_size},
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            page_list = data.get("midis", [])
            songs.extend(page_list)
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            print(
                f"[ERROR] fetch latest_songs page {page} failed: {e}", file=sys.stderr
            )
            break
    return songs


def download_midi_bytes(base_url: str, hash_: str, timeout: int = 10) -> bytes:
    # Download midi bytes
    r = requests.get(
        f"{base_url.rstrip('/')}/download", params={"hash": hash_}, timeout=timeout
    )
    r.raise_for_status()
    return r.content


def build_initial_queue(base_url: str) -> (deque, Set[str]):
    # Build initial deque and known hash set. Leftmost (popleft) is newest (songs[0])
    songs = fetch_all_latest_songs(base_url)
    uniq = deque()
    seen: Set[str] = set()
    for s in songs:
        h = s.get("hash") or s.get("id") or s.get("name")
        if not h or h in seen:
            continue
        seen.add(h)
        uniq.append(s)
    return uniq, seen


def insert_new_at_top(
    queue: deque, new_songs: List[Dict[str, Any]], known_hashes: Set[str]
):
    # Insert unseen songs at queue top (left). new_songs assumed newest->old; preserve that order.
    filtered = []
    for s in new_songs:
        h = s.get("hash") or s.get("id") or s.get("name")
        if not h:
            continue
        if h in known_hashes:
            continue
        filtered.append(s)
    for s in reversed(filtered):
        queue.appendleft(s)
        h = s.get("hash") or s.get("id") or s.get("name")
        known_hashes.add(h)


def auto_play_from_api(base_url: str):
    # keep queue, download and play
    queue, known_hashes = build_initial_queue(base_url)
    empty_count = 0

    while True:
        if not queue:
            empty_count += 1
            if empty_count >= 2:
                # Reset state and reload all midis to replay
                known_hashes = set()
                queue, known_hashes = build_initial_queue(base_url)
                empty_count = 0
                if not queue:
                    time.sleep(2)
                    continue
            else:
                # Try to fetch once and insert new items
                songs = fetch_all_latest_songs(base_url)
                if songs:
                    for s in reversed(songs):
                        h = s.get("hash") or s.get("id") or s.get("name")
                        if h and h not in known_hashes:
                            queue.appendleft(s)
                            known_hashes.add(h)
                if not queue:
                    time.sleep(1)
                    continue
        else:
            empty_count = 0

        song = queue.popleft()
        hash_ = song.get("hash") or song.get("id") or song.get("name")
        name = song.get("name", "<unknown>")
        print(f"[INFO] play: {name} ({hash_})")

        try:
            midi_bytes = download_midi_bytes(base_url, hash_)
        except Exception as e:
            print(f"[ERROR] download failed: {name} ({hash_}) -> {e}", file=sys.stderr)
            continue

        try:
            midi_file = mido.MidiFile(file=io.BytesIO(midi_bytes))
        except Exception as e:
            print(f"[ERROR] parse failed: {name} ({hash_}) -> {e}", file=sys.stderr)
            continue

        try:
            events = midi_to_events(
                midi_file, min_time=0, max_time=midi_total_length(midi_file)
            )
            stop_flag = threading.Event()
            play_events(events, stop_flag, None)
        except Exception as e:
            print(f"[ERROR] playback error: {name} ({hash_}) -> {e}", file=sys.stderr)

        # After each play, check for new songs and insert at top
        try:
            latest = fetch_all_latest_songs(base_url)
            insert_new_at_top(queue, latest, known_hashes)
        except Exception as e:
            print(f"[ERROR] refresh latest failed: {e}", file=sys.stderr)

        time.sleep(0.05)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-download and play MIDI from API")
    parser.add_argument("--base-url", type=str, default="http://139.196.113.128:1200")
    args = parser.parse_args()

    try:
        auto_play_from_api(args.base_url)
    except KeyboardInterrupt:
        print("\n[INFO] interrupted, exiting.")

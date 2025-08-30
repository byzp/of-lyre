"""
合奏主控程序, 分割音轨下发到被控机, 依赖在线曲库
输入hash添加歌曲, 输入s停止当前演奏
"""
import argparse
import io
import sys
import threading
import time
from collections import deque
from typing import List, Dict, Set, Any

import mido
from mido import MidiFile, tick2second
import requests

def midi_total_length(mid: MidiFile) -> float:
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

stop = False

def download_midi_bytes(base_url: str, hash_: str, timeout: int = 10) -> bytes:
    r = requests.get(f"{base_url.rstrip('/')}/download", params={"hash": hash_}, timeout=timeout)
    r.raise_for_status()
    return r.content

def console_listener(queue: deque, known_hashes: Set[str]):
    global stop
    while True:
        h = input("Enter song hash (or 's' to stop): ").strip()
        if not h:
            continue
        if h == "s":
            stop = True
            continue
        """
        if h in known_hashes:
            print(f"[INFO] hash {h} already known, ignored")
            continue
        """
        print(f"[INFO] manual add {h} to next")
        queue.appendleft({"hash": h, "name": f"manual:{h}"})
        known_hashes.add(h)



def assign_tracks(num_agents: int, num_tracks: List[int]) -> List[List[int]]:
    if num_agents <= 0 or not num_tracks:
        return []
    
    assignments: List[List[int]] = [[] for _ in range(num_agents)]
    total_tracks = len(num_tracks)
    if total_tracks <= 0:
        return assignments
    
    # tracks is less than agents
    if total_tracks < num_agents:
        for i in range(total_tracks):
            assignments[i] = [num_tracks[i]]
        return assignments
    
    # tracks is greater than agents
    for i in range(num_agents - 1):
        assignments[i] = [num_tracks[i]]
    
    # Allocate the remaining tracks to the last agent
    assignments[-1] = num_tracks[num_agents - 1:]
    
    return assignments


def auto_play_from_api(base_url: str, agents: List[str]):
    global stop
    queue = deque()
    known_hashes = set()

    t = threading.Thread(target=console_listener, args=(queue, known_hashes), daemon=True)
    t.start()

    while True:
        if not queue:
            time.sleep(1)
            continue
        song = queue.popleft()
        hash_ = song.get("hash") or song.get("id") or song.get("name")
        name = song.get("name", "<unknown>")
        print(f"[INFO] play: {name} ({hash_})")

        try:
            midi_bytes = download_midi_bytes(base_url, hash_)
            midi_file = mido.MidiFile(file=io.BytesIO(midi_bytes))
        except Exception as e:
            print(f"[ERROR] download/parse failed: {name} ({hash_}) -> {e}", file=sys.stderr)
            continue

        # Filter tracks to include only those with 'note' events
        filtered_tracks=[]
        for track_number, track in enumerate(midi_file.tracks):
            if any(msg.type == 'note_on' or msg.type == 'note_off' for msg in track):
                filtered_tracks.append(track_number)
        
        num_agents = len(agents)
        assignments = assign_tracks(num_agents, filtered_tracks)

        try:
            duration = midi_total_length(midi_file)
        except Exception:
            duration = 0.0

        start_at = time.time() + 3.0

        # Notify all agents to start playback
        for agent_url, tracks in zip(agents, assignments):
            payload = {
                "hash": hash_,
                "tracks": tracks,
                "start_at": start_at,
                "base_url": base_url,
            }
            print(str(tracks))
            try:
                r = requests.post(agent_url.rstrip('/') + '/play', json=payload, timeout=5)
                r.raise_for_status()
            except Exception as e:
                print(f"[WARN] notify agent {agent_url} failed: {e}", file=sys.stderr)

        # Check if stop is triggered during the wait time
        now = time.time()
        to_wait = max(0.0, start_at - now) + duration + 0.5
        print(f"[INFO] waiting {to_wait:.1f}s for playback to finish")

        wait_time = 0.0
        while wait_time < to_wait:
            if stop:
                print("[INFO] stopping early...")
                for agent_url in agents:
                    try:
                        r = requests.post(agent_url.rstrip('/') + '/cnt', json={"cnt": "s"}, timeout=5)
                        r.raise_for_status()
                    except Exception as e:
                        print(f"[WARN] stop failed: {e}", file=sys.stderr)
                stop = False
                break
            time.sleep(0.1)  # Check periodically for stop signal
            wait_time += 0.1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', type=str, default='http://139.196.113.128:1200')
    parser.add_argument('--agents', type=str, nargs='+', required=True, help='agent base URLs, e.g. http://10.0.0.2:5000')
    args = parser.parse_args()

    try:
        auto_play_from_api(args.base_url, args.agents)
    except KeyboardInterrupt:
        print('\n[INFO] interrupted, exiting.')

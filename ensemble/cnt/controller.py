"""
合奏主控程序, 分割音轨下发到被控机, 依赖在线曲库
输入hash添加歌曲, 输入s停止当前演奏, 输入p继续
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
from live_parse import start_sniffer, stop_sniffer

play = True
#auto = True
auto = False


def fetch_all_latest_songs(base_url: str, page_size: int = 50, timeout: int = 5) -> List[Dict[str, Any]]:
    songs: List[Dict[str, Any]] = []
    page = 1
    while True:
        try:
            r = requests.get(f"{base_url.rstrip('/')}/latest_songs", params={"page": page, "page_size": page_size}, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            page_list = data.get("midis", [])
            songs.extend(page_list)
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            print(f"[ERROR] fetch latest_songs page {page} failed: {e}", file=sys.stderr)
            break
    return songs

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

def download_midi_bytes(base_url: str, hash_: str, timeout: int = 10) -> bytes:
    r = requests.get(f"{base_url.rstrip('/')}/download", params={"hash": hash_}, timeout=timeout)
    r.raise_for_status()
    return r.content

def console_listener(queue: deque, known_hashes: Set[str], base_url: str):
    global play
    while True:
        time.sleep(0.1)
        cmd = input("> ").strip()
        if not cmd:
            continue
        if cmd == "s" or cmd == "start":
            play = False
            continue
        if cmd == "p" or cmd == "play":
            play = True
            continue
        if cmd == "a" or cmd == "auto":
            global auto
            if auto == True:
                auto = False
            else:
                auto = True
            print(auto)
            continue
        if cmd[0] == "#":
            if not queue:
                songs = fetch_all_latest_songs(base_url)
                if songs:
                    for s in reversed(songs):
                        h = s.get("hash") or s.get("id") or s.get("name")
                        queue.appendleft(s)
            hash_ = cmd[1:]
            while True:
                song = queue.popleft()
                t_hash = song.get("hash")
                if hash_ == t_hash or len(queue) == 0:
                    break
            continue
        """
        if h in known_hashes:
            print(f"[INFO] hash {h} already known, ignored")
            continue
        """
        print(f"[INFO] manual add {cmd} to next")
        queue.appendleft({"hash": cmd, "name": f"manual:{cmd}"})
        known_hashes.add(cmd)



def assign_tracks(num_agents: int, num_tracks: List[int]) -> List[List[int]]:
    if num_agents <= 0 or not num_tracks:
        return []
    
    assignments: List[List[int]] = [[] for _ in range(num_agents)]
    
    total_tracks = len(num_tracks)
    if total_tracks <= 0:
        return assignments
    
    if total_tracks == 1:
        assignments[-1] = num_tracks
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
    global play,auto
    queue = deque()
    known_hashes = set()

    t = threading.Thread(target=console_listener, args=(queue, known_hashes,base_url), daemon=True)
    t.start()
    stop_evt = threading.Event()
    
    threading.Thread(target=start_sniffer, args=("enp4s0", "14.103.255.172", 11003), kwargs={"out_queue": queue, "stop_event": stop_evt}).start()
    while True:
        while True:
            if play == False:
                time.sleep(0.1)
                continue
            break
        if not queue:
            if auto == False:
                time.sleep(0.1)
                continue
            songs = fetch_all_latest_songs(base_url)
            if songs:
                for s in reversed(songs):
                    h = s.get("hash") or s.get("id") or s.get("name")
                    queue.appendleft(s)
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
            if not play:
                print("[INFO] stopping early...")
                for agent_url in agents:
                    try:
                        t = threading.Thread(target=_send_stop, args=(agent_url,), daemon=True)
                        t.start()
                    except Exception as e:
                        print(f"[WARN] stop failed: {e}", file=sys.stderr)
                break
            time.sleep(0.1)  # Check periodically for stop signal
            wait_time += 0.1
            ti = time.localtime(time.time())
            if ti.tm_hour==4:
                if ti.tm_min==59:
                    threading.Thread(target=_send_stop, args=(agent_url,), daemon=True).start()
                    time.sleep(120)
                    break
                    for agent_url in agents:
                        try:
                            r = requests.post(agent_url.rstrip('/') + '/esc', json={}, timeout=5)
                            r.raise_for_status()
                        except Exception as e:
                            print(f"[WARN] notify agent {agent_url} failed: {e}", file=sys.stderr)

def _send_stop(agent_url):
    try:
        r = requests.post(agent_url.rstrip('/') + '/cnt', json={"cnt": "s"}, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"[WARN] stop failed: {e}", file=sys.stderr)
        

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', type=str, default='http://139.196.113.128:1200')
    parser.add_argument('--agents', type=str, nargs='+', required=True, help='agent base URLs, e.g. http://10.0.0.2:5000')
    args = parser.parse_args()

    try:
        auto_play_from_api(args.base_url, args.agents)
    except KeyboardInterrupt:
        print('\n[INFO] interrupted, exiting.')

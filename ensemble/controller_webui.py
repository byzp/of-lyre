import argparse
import io
import json
import threading
import time
from collections import deque
from typing import List, Dict, Any

import gradio as gr
import mido
from mido import MidiFile, tick2second
import requests

# application state
play_flag = False
queue = deque()
known_hashes = set()
playlist: List[Dict[str, Any]] = []
agents_list: List[str] = []
base_url_global = ""

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
            print(f"[ERROR] fetch latest_songs page {page} failed: {e}")
            break
    return songs


def download_midi_bytes(base_url: str, hash_: str, timeout: int = 10) -> bytes:
    r = requests.get(f"{base_url.rstrip('/')}/download", params={"hash": hash_}, timeout=timeout)
    r.raise_for_status()
    return r.content


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


# filter tracks which contain note_on/note_off
def midi_tracks_with_notes(mid: MidiFile) -> List[int]:
    filtered = []
    for idx, track in enumerate(mid.tracks):
        if any((hasattr(msg, 'type') and (msg.type == 'note_on' or msg.type == 'note_off')) for msg in track):
            filtered.append(idx)
    return filtered


# assign tracks to agents (keeps the same simple policy as original)
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
    if total_tracks < num_agents:
        for i in range(total_tracks):
            assignments[i] = [num_tracks[i]]
        return assignments
    for i in range(num_agents - 1):
        assignments[i] = [num_tracks[i]]
    assignments[-1] = num_tracks[num_agents - 1:]
    return assignments


def playback_worker():
    global play_flag, queue, known_hashes, agents_list, base_url_global
    while True:
        # wait until play_flag is True and queue is not empty
        if not play_flag or not queue:
            time.sleep(0.1)
            continue

        song = queue.popleft()
        #queue_box.update(value=get_queue_view())
        hash_ = song.get('hash') or song.get('id') or song.get('name')
        name = song.get('name', '<unknown>')
        print(f"[INFO] play: {name} ({hash_})")

        try:
            midi_bytes = download_midi_bytes(base_url_global, hash_)
            midi_file = mido.MidiFile(file=io.BytesIO(midi_bytes))
        except Exception as e:
            print(f"[ERROR] download/parse failed: {name} ({hash_}) -> {e}")
            # ensure hash is removed from known_hashes so it can be retried/added later
            known_hashes.discard(hash_)
            continue

        filtered_tracks = midi_tracks_with_notes(midi_file)
        num_agents = len(agents_list)
        assignments = assign_tracks(num_agents, filtered_tracks)

        try:
            duration = midi_total_length(midi_file)
        except Exception:
            duration = 0.0

        start_at = time.time() + 3.0

        # Notify agents
        for agent_url, tracks in zip(agents_list, assignments):
            payload = {
                'hash': hash_,
                'tracks': tracks,
                'start_at': start_at,
                'base_url': base_url_global,
            }
            print(f"[DEBUG] notify {agent_url} -> {tracks}")
            try:
                r = requests.post(agent_url.rstrip('/') + '/play', json=payload, timeout=5)
                r.raise_for_status()
            except Exception as e:
                print(f"[WARN] notify agent {agent_url} failed: {e}")

        # Wait for playback to finish or until stopped
        now = time.time()
        to_wait = max(0.0, start_at - now) + duration + 0.5
        print(f"[INFO] waiting {to_wait:.1f}s for playback to finish")
        waited = 0.0
        while waited < to_wait:
            if not play_flag:
                print('[INFO] stopping early...')
                for agent_url in agents_list:
                    try:
                        threading.Thread(target=_send_stop, args=(agent_url,), daemon=True).start()
                    except Exception as e:
                        print(f"[WARN] stop failed: {e}")
                break
            time.sleep(0.1)
            waited += 0.1

        # After playback (or early stop), allow the same hash to be added again
        known_hashes.discard(hash_)


def _send_stop(agent_url: str):
    try:
        r = requests.post(agent_url.rstrip('/') + '/cnt', json={'cnt': 's'}, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"[WARN] stop failed: {e}")


def start_play():
    global play_flag
    play_flag = True
    return gr.update(value=True)


def stop_play():
    global play_flag
    play_flag = False
    # also notify all agents immediately
    for a in agents_list:
        try:
            threading.Thread(target=_send_stop, args=(a,), daemon=True).start()
        except Exception as e:
            print(f"[WARN] stop failed: {e}")
    return gr.update(value=False)


def add_manual_hash(hash_text: str):
    global queue, known_hashes
    if not hash_text:
        return get_queue_view()
    if hash_text in known_hashes:
        # already in queue or recently added; return current queue view
        return get_queue_view()
    queue.append({'hash': hash_text, 'name': f'manual:{hash_text}'})
    known_hashes.add(hash_text)
    return get_queue_view()


def add_selected(index: int):
    global playlist, queue, known_hashes
    try:
        song = playlist[int(index)]
    except Exception:
        return get_queue_view()
    h = song.get('hash') or song.get('id') or song.get('name')
    if h in known_hashes:
        return get_queue_view()
    queue.append({'hash': h, 'name': song.get('name', h)})
    known_hashes.add(h)
    return get_queue_view()


def refresh_playlist():
    global playlist, base_url_global
    try:
        playlist = fetch_all_latest_songs(base_url_global)
    except Exception as e:
        print(f"[WARN] refresh failed: {e}")
        playlist = []
    table = [[i, p.get('name', '<unknown>'), p.get('hash') or p.get('id') or ''] for i, p in enumerate(playlist)]
    return table


def search_playlist(query: str):
    global playlist
    if not query:
        return [[i, p.get('name', '<unknown>'), p.get('hash') or p.get('id') or ''] for i, p in enumerate(playlist)]
    q = query.lower()
    results = []
    for i, p in enumerate(playlist):
        name = (p.get('name') or '').lower()
        h = (p.get('hash') or p.get('id') or '').lower()
        if q in name or q in h:
            results.append([i, p.get('name', '<unknown>'), p.get('hash') or p.get('id') or ''])
    return results


def get_queue_view():
    global queue
    names=""
    for i in queue:
        names+= ">"+i.get('name')+"\n"
    return names
    # return a short, human-friendly representation
    #return json.dumps([{'name': s.get('name'), 'hash': s.get('hash') or s.get('id') or s.get('name')} for s in list(queue)], ensure_ascii=False, indent=2)


def clear_queue():
    global queue, known_hashes
    # remove queued items' hashes from known_hashes, then clear the queue
    items = list(queue)
    queue.clear()
    for s in items:
        h = s.get('hash') or s.get('id') or s.get('name')
        if h:
            known_hashes.discard(h)
    return get_queue_view()


def select_song_index(event: gr.SelectData) -> Any:
    """
    从表格选择事件中提取行索引
    """
    try:
        if event is None:
            return gr.update()
        
        # 直接返回行索引
        row = event.index[0] if isinstance(event.index, (list, tuple)) else event.index
        
        if isinstance(row, int) and row >= 0:
            return gr.update(value=row)
        
        return gr.update()
        
    except Exception as e:
        print(f"[WARN] select_song_index failed: {e}")
        return gr.update()


def build_and_launch(base_url: str, agents: List[str], port: int = 7860):
    global base_url_global, agents_list, playlist
    base_url_global = base_url
    agents_list = agents

    # initial fetch at startup
    try:
        playlist = fetch_all_latest_songs(base_url_global)
    except Exception as e:
        print(f"[WARN] initial fetch failed: {e}")
        playlist = []

    # start worker thread
    t = threading.Thread(target=playback_worker, daemon=True)
    t.start()

    with gr.Blocks() as demo:
        #gr.Markdown("# 合奏主控 (web)")
        
        with gr.Row():
            with gr.Column(scale=2):
                songs_table = gr.Dataframe(
                    value=[[i, p.get('name', '<unknown>'), p.get('hash') or p.get('id') or ''] for i, p in enumerate(playlist)],
                    headers=["index", "name", "hash"],
                    interactive=False,
                    col_count=(3),
                )
                with gr.Row():
                    add_index = gr.Number(label="序号（点击表格自动填充）", value=0, precision=0)
                    

                    add_button = gr.Button("添加到队列")
                with gr.Row():
                    search_input = gr.Textbox(label="搜索 (name or hash)")
                    search_button = gr.Button("搜索")
                refresh_button = gr.Button("刷新列表")
                #manual_input = gr.Textbox(label="Manual hash to add")
                #manual_add = gr.Button("Add manual hash")

            with gr.Column(scale=1):
                play_btn = gr.Button("开始")
                stop_btn = gr.Button("暂停")
                gr.Markdown("### Queue")
                #global queue_box
                queue_box = gr.Textbox(value=get_queue_view(), lines=12, interactive=False)
                with gr.Row():
                    refresh_queue_btn = gr.Button("刷新队列")
                    clear_queue_btn = gr.Button("清空队列")  # NEW button
                status = gr.Checkbox(value=False, label="Playing (state)")

        # callbacks
        add_button.click(fn=add_selected, inputs=[add_index], outputs=[queue_box])
        #manual_add.click(fn=add_manual_hash, inputs=[manual_input], outputs=[queue_box])
        refresh_button.click(fn=refresh_playlist, inputs=[], outputs=[songs_table])
        search_button.click(fn=search_playlist, inputs=[search_input], outputs=[songs_table])
        play_btn.click(fn=start_play, outputs=[status])
        stop_btn.click(fn=stop_play, outputs=[status])
        refresh_queue_btn.click(fn=get_queue_view, inputs=[], outputs=[queue_box])
        clear_queue_btn.click(fn=clear_queue, inputs=[], outputs=[queue_box])  # NEW binding

        songs_table.select(fn=select_song_index, outputs=[add_index])
        
        # initial loaders
        demo.load(fn=lambda: [[i, p.get('name', '<unknown>'), p.get('hash') or p.get('id') or ''] for i, p in enumerate(playlist)], outputs=[songs_table])
        demo.load(fn=get_queue_view, outputs=[queue_box])

    demo.launch(server_name='0.0.0.0', server_port=port)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', type=str, default='http://139.196.113.128:1200')
    parser.add_argument('--agents', type=str, nargs='+', required=True, help='agent base URLs, e.g. http://10.0.0.2:5000')
    parser.add_argument('--port', type=int, default=7860)
    args = parser.parse_args()

    build_and_launch(args.base_url, args.agents, port=args.port)
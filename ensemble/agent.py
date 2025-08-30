"""
受控程序：接受/播放请求的简单HTTP服务器。
请求：一个midi、要播放的音轨索引列表、要下载的base_url和start_at时间戳。
代理下载MIDI，将请求的曲目提取到新的MidiFile中，转换为事件并在start_at播放。
"""

from flask import Flask, request, jsonify
import threading
import time
import io
import sys
import argparse

import requests
import mido

from core import midi_to_events, play_events, midi_total_length, stop as core_stop

app = Flask(__name__)
stop_flag = threading.Event()

@app.route('/play', methods=['POST'])
def play():
    data = request.get_json(force=True)
    hash_ = data.get('hash')
    tracks = data.get('tracks', [])  # list of indices
    start_at = float(data.get('start_at', time.time()))
    base_url = data.get('base_url')

    if not hash_ or base_url is None:
        return jsonify({'error': 'missing hash or base_url'}), 400

    # download midi (no cache)
    try:
        r = requests.get(f"{base_url.rstrip('/')}/download", params={'hash': hash_}, timeout=10)
        r.raise_for_status()
        midi_bytes = r.content
        midi = mido.MidiFile(file=io.BytesIO(midi_bytes))
    except Exception as e:
        return jsonify({'error': f'download failed: {e}'}), 500

    # Filter tracks: remove tracks that are not selected AND contain note events
    try:
        if not tracks:
            # nothing to play
            return jsonify({'status': 'no tracks assigned'}), 200

        # Sanitize and clamp track indices
        selected_indices = []
        for idx in tracks:
            if 0 <= idx < len(midi.tracks):
                selected_indices.append(idx)
        if not selected_indices:
            return jsonify({'status': 'no valid tracks'}), 200

        # Create a list of tracks to keep: selected tracks and tracks with global meta events (like tempo)
        tracks_to_keep = []
        global_events_track = None

        # First, identify all global meta events (tempo, time signature, etc.) from all tracks
        global_events = []
        for i, track in enumerate(midi.tracks):
            for msg in track:
                if msg.is_meta and msg.type in ['set_tempo', 'time_signature', 'key_signature']:
                    global_events.append(msg)

        # Create a new track for global events if any are found
        if global_events:
            global_events_track = mido.MidiTrack()
            for msg in global_events:
                global_events_track.append(msg)
            tracks_to_keep.append(global_events_track)

        # Add the selected tracks
        for idx in selected_indices:
            tracks_to_keep.append(midi.tracks[idx])

        # Replace the original tracks with the filtered list
        midi.tracks.clear()
        for track in tracks_to_keep:
            midi.tracks.append(track)

        # Prepare events
        total_len = midi_total_length(midi)
        events = midi_to_events(midi, min_time=0, max_time=total_len)
    except Exception as e:
        return jsonify({'error': f'prepare failed: {e}'}), 500

    # schedule playback at start_at
    def _play_later():
        global stop_flag
        now = time.time()
        delay = start_at - now
        if delay > 0:
            time.sleep(delay)
        try:
            play_events(events, stop_flag, None)
        except Exception as e:
            print(f"[ERROR] playback error: {e}", file=sys.stderr)

    thread = threading.Thread(target=_play_later, daemon=True)
    thread.start()

    return jsonify({'status': 'scheduled', 'start_at': start_at}), 200

@app.route('/cnt', methods=['POST'])
def cnt():
    global stop_flag
    data = request.get_json(force=True)
    cnt = data.get('cnt')
    if cnt=="s":
        core_stop(stop_flag)
        time.sleep(3)
        stop_flag.clear()
    return jsonify({'stop': ''}), 200

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    # Flask requires running via app.run
    app.run(host=args.host, port=args.port)

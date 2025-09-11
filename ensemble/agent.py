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
    tracks = data.get('tracks', [])  # list of indices (could be strings or ints)
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

    # Filter tracks: remove notes from tracks that are not selected, operate in-place on midi
    try:
        if not tracks:
            # nothing to play
            return jsonify({'status': 'no tracks assigned'}), 200

        # Sanitize and clamp track indices (allow strings that represent ints)
        selected_indices = []
        for idx in tracks:
            try:
                ii = int(idx)
            except Exception:
                continue
            if 0 <= ii < len(midi.tracks):
                selected_indices.append(ii)
        if not selected_indices:
            return jsonify({'status': 'no valid tracks'}), 200

        # For each track in the original midi, if it's NOT selected then remove note messages
        # while preserving meta messages (tempo, time_signature, key_signature, end_of_track, etc.)
        for i, track in enumerate(midi.tracks):
            # If track is selected, leave it as-is.
            if i in selected_indices:
                continue

            # Build filtered message list with correct delta-time handling.
            new_msgs = []
            time_acc = 0.0
            for msg in track:
                # accumulate time
                time_acc += getattr(msg, 'time', 0.0)

                # Decide whether to keep this message.
                # Keep if it's meta or not a note_on/note_off.
                # (note_on with velocity==0 still has type 'note_on' and will be removed here)
                if msg.is_meta or msg.type not in ('note_on', 'note_off'):
                    # Mutate the message's time to the accumulated delta and append.
                    msg.time = time_acc
                    new_msgs.append(msg)
                    time_acc = 0.0
                else:
                    # This is a note event in an unselected track -> drop it (do not append),
                    # but keep its delta-time accumulated into the next kept message.
                    # (so just continue, time_acc remains)
                    continue

            # If there is leftover accumulated time (e.g., trailing note events removed),
            # attach it to the last message if exists, otherwise create an end_of_track meta with that time.
            if time_acc:
                if new_msgs:
                    # add leftover delta to last message's time
                    new_msgs[-1].time = getattr(new_msgs[-1], 'time', 0.0) + time_acc
                else:
                    # no messages kept in this track — ensure there's an end_of_track meta
                    new_msgs.append(mido.MetaMessage('end_of_track', time=time_acc))
                    time_acc = 0.0

            # Ensure track ends with an end_of_track meta (many MIDIs already have it, but be safe)
            if not (new_msgs and getattr(new_msgs[-1], 'is_meta', False) and getattr(new_msgs[-1], 'type', '') == 'end_of_track'):
                # append end_of_track with time 0
                new_msgs.append(mido.MetaMessage('end_of_track', time=0))

            # Replace messages in-place on the original track (do not create a new MidiTrack)
            track.clear()
            for m in new_msgs:
                track.append(m)

        # After in-place filtering, prepare events from the same midi object
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

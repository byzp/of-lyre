import io
import os
import re
import math
import threading
from collections import defaultdict
from typing import List, Dict, Tuple

import numpy as np
import soundfile as sf
import librosa
import mido
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse,Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydub import AudioSegment
from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
import re
import requests
import io
import numpy as np
from pydub import AudioSegment

NOTE_NAME_RE = re.compile(r'([A-Ga-g])(#|b)?(\d+)')
NOTE_TO_SEMITONE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

# 全局 samples 缓存： samples_dir -> { midi_num: (y: np.ndarray, sr: int) }
SAMPLES_CACHE: Dict[str, Dict[int, Tuple[np.ndarray, int]]] = {}
SAMPLES_CACHE_LOCK = threading.Lock()


def note_name_to_midi(note_name: str) -> int:
    """把类似 C4, G#3, Bb2 转成 MIDI 数字（0-127）"""
    m = NOTE_NAME_RE.search(note_name)
    if not m:
        raise ValueError(f"invalid note name: {note_name}")
    letter, acc, octave = m.groups()
    letter = letter.upper()
    sem = NOTE_TO_SEMITONE[letter]
    if acc == '#':
        sem += 1
    elif acc == 'b':
        sem -= 1
    octave = int(octave)
    return (octave + 1) * 12 + sem

def is_white_key(midi_note: int) -> bool:
    return (midi_note % 12) in {0, 2, 4, 5, 7, 9, 11}

def list_sample_files(samples_dir: str) -> List[str]:
    try:
        return [f for f in os.listdir(samples_dir) if os.path.isfile(os.path.join(samples_dir, f))]
    except Exception as e:
        raise RuntimeError(f"cannot list samples_dir: {e}")

def load_and_prepare_sample(path: str, out_sr: int) -> Tuple[np.ndarray, int]:
    """
    读取并返回单通道（mono）float32 numpy 数组，采样率为 out_sr。
    使用 librosa.load 做重采样与单通道化。
    """
    y, sr = librosa.load(path, sr=out_sr, mono=True)
    # 转为 float32（librosa 返回通常是 float32，但确保类型）
    y = y.astype(np.float32)
    return y, out_sr

def preload_samples_dir(samples_dir: str, out_sr: int = 22050) -> Dict[int, Tuple[np.ndarray, int]]:
    """
    将 samples_dir 中的样本一次性读入内存并缓存，返回 midi->(y,sr) 的映射。
    线程安全：并发请求时只会加载一次。
    """
    abs_dir = os.path.abspath(samples_dir)
    with SAMPLES_CACHE_LOCK:
        if abs_dir in SAMPLES_CACHE:
            return SAMPLES_CACHE[abs_dir]

        files = list_sample_files(abs_dir)
        m = {}
        for fn in files:
            name = os.path.splitext(fn)[0]
            s = NOTE_NAME_RE.search(name)
            if not s:
                continue
            token = s.group(0)
            try:
                midi = note_name_to_midi(token)
            except Exception:
                continue
            path = os.path.join(abs_dir, fn)
            try:
                y, sr = load_and_prepare_sample(path, out_sr)
            except Exception:
                # 忽略无法读取的文件
                continue
            m[midi] = (y, sr)
        if not m:
            raise RuntimeError("no valid sample files found in samples_dir")
        SAMPLES_CACHE[abs_dir] = m
        return m


def parse_midi_file(midi_bytes: bytes) -> list:
    """
    返回按时间排序的事件：(abs_time_seconds, note, velocity, event_type)
    event_type: "on" 或 "off" (note_on velocity==0 也当 off)
    """
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    ticks_per_beat = mid.ticks_per_beat
    tempo = 500000  # default microseconds per beat
    merged = mido.merge_tracks(mid.tracks)
    abs_time = 0.0
    events = []
    for msg in merged:
        if msg.time:
            abs_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
            continue
        if msg.type == "note_on":
            event_type = "off" if msg.velocity == 0 else "on"
            events.append((abs_time, msg.note, msg.velocity, event_type))
        elif msg.type == "note_off":
            events.append((abs_time, msg.note, 0, "off"))
    return sorted(events, key=lambda x: x[0])

def events_to_notes(note_events: list) -> list:
    """
    把 note on/off 事件配对成 notes 列表：(start_time, duration, pitch, velocity)
    如果 note 没有 off 则默认持续 0.5s。
    """
    notes = []
    active = defaultdict(list)  # pitch -> list of (start_time, vel)
    for abs_time, pitch, velocity, event_type in note_events:
        if event_type == "on" and velocity > 0:
            active[pitch].append((abs_time, velocity))
        elif event_type == "off" or (event_type == "on" and velocity == 0):
            if active[pitch]:
                start_time, vel = active[pitch].pop(0)
                duration = abs_time - start_time
                if duration > 0.001:
                    notes.append((start_time, duration, pitch, vel))
    # still active -> give short default duration
    for pitch, evs in active.items():
        for start_time, vel in evs:
            notes.append((start_time, 0.5, pitch, vel))
    return sorted(notes, key=lambda x: x[0])


def find_best_transpose(notes: list, sample_midis: List[int], search_range=range(-24, 25)):
    """
    寻找一个整体转调，使得尽可能多的音符落在 samples 可用范围内且为白键。
    返回 (best_transpose, count)
    """
    sample_min = min(sample_midis)
    sample_max = max(sample_midis)
    best_t = 0
    best_cnt = -1
    for t in search_range:
        cnt = 0
        for _, _, pitch, _ in notes:
            p = pitch + t
            if sample_min <= p <= sample_max and is_white_key(p):
                cnt += 1
        if cnt > best_cnt:
            best_cnt = cnt
            best_t = t
    return best_t, best_cnt

def pitch_shift_audio(y: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """对单通道信号做半音变化（librosa）"""
    if abs(semitones) < 1e-9:
        return y
    try:
        return librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones)
    except TypeError:
        # 兼容历史参数名
        return librosa.effects.pitch_shift(y, sr, semitones)

def trim_silence(audio: np.ndarray, threshold: float = 0.01, chunk_size: int = 1024) -> np.ndarray:
    """简单的前后静音裁剪（基于绝对值阈值）"""
    if audio.ndim == 1:
        abs_audio = np.abs(audio)
    else:
        abs_audio = np.max(np.abs(audio), axis=1)
    start = 0
    end = len(audio)
    for i in range(0, len(abs_audio), chunk_size):
        if np.max(abs_audio[i:i+chunk_size]) >= threshold:
            start = i
            break
    for i in range(len(abs_audio), 0, -chunk_size):
        if np.max(abs_audio[max(0, i-chunk_size):i]) >= threshold:
            end = i
            break
    return audio[start:end]

def synthesize(notes, samples_mem: Dict[int, Tuple[np.ndarray,int]],
               black_policy='up', auto_octave=False, out_sr=22050,
               manual_offset=0, duration_scale=1.0, clean=False, auto_transpose=True):
    """
    用已经预加载到内存的 samples (samples_mem) 做采样合成。
    samples_mem: midi_num -> (y, sr) （y 已经为 out_sr, mono）
    返回 (mix, out_sr)
    """
    sample_midis = sorted(samples_mem.keys())
    if not sample_midis:
        raise RuntimeError("samples empty")
    sample_min = min(sample_midis)
    sample_max = max(sample_midis)

    # 找整体转调（只要 notes 非空）
    best_t = 0
    if notes and auto_transpose:
        best_t, _ = find_best_transpose(notes, sample_midis)
    total_transpose = best_t + manual_offset if auto_transpose else manual_offset

    # 生成事件列表： (start_s, dur_s, sample_midi, semitone_shift, velocity)
    events = []
    for start, dur, pitch, velocity in notes:
        scaled_start = start * duration_scale
        scaled_dur = max(0.01, dur * duration_scale)
        p = pitch + total_transpose
        if not is_white_key(p):
            if black_policy == 'ignore':
                continue
            elif black_policy == 'up':
                p += 1
            elif black_policy == 'down':
                p -= 1
        if auto_octave:
            while p < sample_min:
                p += 12
            while p > sample_max:
                p -= 12
        if p < sample_min or p > sample_max:
            continue
        # 找最接近的可用 sample（优先精确匹配）
        if p in samples_mem:
            sample_midi = p
            semitone_shift = 0
        else:
            found = None
            for delta in range(1, 25):
                for sign in (1, -1):
                    cand = p + sign * delta
                    if cand in samples_mem and is_white_key(cand):
                        found = cand
                        break
                if found is not None:
                    break
            if found is None:
                continue
            sample_midi = found
            semitone_shift = p - sample_midi
        events.append((scaled_start, scaled_dur, sample_midi, semitone_shift, velocity))

    if not events:
        raise RuntimeError("no events to synthesize")

    last_time = max(e[0] + e[1] for e in events)
    out_len = int(math.ceil((last_time + 2.0) * out_sr))
    mix = np.zeros(out_len, dtype=np.float32)

    fade_in_ms = 8
    fade_out_ms = 20
    max_extra_release_ms = 1000

    # 合成每个事件
    for start_s, dur, sample_midi, shift, vel in events:
        y, sr = samples_mem[sample_midi]  # y 已经为 out_sr, mono
        if sr != out_sr:
            # 理论上 preload 时已做重采样，但保底
            y = librosa.resample(y, sr, out_sr)
        y_shifted = pitch_shift_audio(y, out_sr, shift) if abs(shift) > 0 else y
        needed_len = int(dur * out_sr)
        fade_in = int((fade_in_ms / 1000.0) * out_sr)
        fade_out = int((fade_out_ms / 1000.0) * out_sr)
        max_extra_release = int((max_extra_release_ms / 1000.0) * out_sr)

        # 如果 sample 长度比目标 duration 长，保留一部分尾音作为 release
        if len(y_shifted) > needed_len:
            tail_keep = min(max_extra_release, len(y_shifted) - needed_len)
            y_use = y_shifted[:needed_len + tail_keep].astype(np.float32)
        else:
            y_use = y_shifted.astype(np.float32)

        # 包络：简易线性淡入淡出
        env = np.ones(len(y_use), dtype=np.float32)
        fade_in = min(fade_in, len(y_use)//2)
        fade_out = min(fade_out, len(y_use)//2)
        if fade_in > 0:
            env[:fade_in] = np.linspace(0.0, 1.0, fade_in)
        if fade_out > 0:
            env[-fade_out:] = np.minimum(env[-fade_out:], np.linspace(1.0, 0.0, fade_out))
        y_use *= env

        # 按 velocity 缩放
        amp = vel / 127.0
        y_use *= amp

        start_idx = int(round(start_s * out_sr))
        end_idx = start_idx + len(y_use)
        if end_idx > len(mix):
            mix = np.pad(mix, (0, end_idx - len(mix)), mode='constant')
        mix[start_idx:end_idx] += y_use

    # 简单归一化（避免裁剪）
    peak = np.max(np.abs(mix))
    if peak > 1e-9:
        mix = mix / max(peak, 1.0)

    if clean:
        mix = trim_silence(mix, threshold=0.01)

    return mix, out_sr

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/wav")
async def wav(request: Request,
              hash: str = Query(...),
              samples_dir: str = Query('./lyre/dict/8/'),
              black_key_policy: str = Query('up', regex='^(up|down|ignore)$'),
              auto_octave: bool = Query(False),
              offset: int = Query(0),
              duration_scale: float = Query(1.0),
              sr: int = Query(22050),
              clean: bool = Query(False)):
    if not re.fullmatch(r'[0-9a-fA-F]{32}', hash):
        raise HTTPException(status_code=400, detail="invalid hash")
    if duration_scale <= 0:
        raise HTTPException(status_code=400, detail="duration_scale must be > 0")
    if sr <= 0:
        raise HTTPException(status_code=400, detail="sr must be > 0")

    url = f'http://127.0.0.1:1200/download?hash={hash}'
    try:
        r = requests.get(url, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"fetch error: {e}")
    if r.status_code != 200 or not r.content:
        raise HTTPException(status_code=404, detail="midi not found")
    midi_bytes = r.content

    try:
        note_events = parse_midi_file(midi_bytes)
        notes = events_to_notes(note_events)
        if not notes:
            raise HTTPException(status_code=400, detail="no notes in midi")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"midi parse error: {e}")

    try:
        samples_mem = preload_samples_dir(samples_dir, out_sr=sr)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"samples load error: {e}")

    try:
        mix, out_sr = synthesize(
            notes,
            samples_mem,
            black_policy=black_key_policy,
            auto_octave=auto_octave,
            out_sr=sr,
            manual_offset=offset,
            duration_scale=duration_scale,
            clean=clean,
            auto_transpose=True
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"synthesis error: {e}")

    try:
        mix = np.clip(mix, -1.0, 1.0)
        mix_int16 = (mix * 32767.0).astype(np.int16)
        audio_seg = AudioSegment(
            data=mix_int16.tobytes(),
            sample_width=2,
            frame_rate=out_sr,
            channels=1
        )
        buf = io.BytesIO()
        audio_seg.export(buf, format="mp3", bitrate="128")
        mp3_bytes = buf.getvalue()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"aac export error: {e}")

    total = len(mp3_bytes)
    range_header: Optional[str] = request.headers.get("range")
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "audio/mpeg",
    }

    if not range_header:
        headers["Content-Length"] = str(total)
        return Response(content=mp3_bytes, media_type="audio/mpeg", headers=headers)

    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        headers["Content-Range"] = f"bytes */{total}"
        return Response(status_code=416, headers=headers)

    start_str, end_str = m.groups()
    try:
        if start_str == "" and end_str:
            suffix_len = int(end_str)
            if suffix_len <= 0:
                headers["Content-Range"] = f"bytes */{total}"
                return Response(status_code=416, headers=headers)
            start = max(total - suffix_len, 0)
            end = total - 1
        else:
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else total - 1
    except ValueError:
        headers["Content-Range"] = f"bytes */{total}"
        return Response(status_code=416, headers=headers)

    if start >= total or start < 0 or end < start:
        headers["Content-Range"] = f"bytes */{total}"
        return Response(status_code=416, headers=headers)

    end = min(end, total - 1)
    chunk_length = end - start + 1

    def iter_range(data: bytes, s: int, e: int, chunk_size: int = 8192):
        idx = s
        while idx <= e:
            yield data[idx:min(idx + chunk_size, e + 1)]
            idx += chunk_size

    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    headers["Content-Length"] = str(chunk_length)
    return StreamingResponse(iter_range(mp3_bytes, start, end), status_code=206, media_type="audio/mpeg", headers=headers)


if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=1220, reload=False)

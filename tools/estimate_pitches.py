import librosa
import librosa.display
import numpy as np


# 读取音频文件
def load_audio(path):
    y, sr = librosa.load(path)
    return y, sr


# 检测音符起始点
def detect_onsets(y, sr):
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    return onset_frames, onset_times


# 提取每个音符的音高
def estimate_pitches(y, sr, onset_frames):
    pitches = []
    for i in range(len(onset_frames)):
        start = onset_frames[i]
        end = onset_frames[i + 1] if i + 1 < len(onset_frames) else len(y)
        y_segment = y[start * 512 : end * 512]  # 每帧 hop_length 默认是 512
        if len(y_segment) == 0:
            continue
        # 用 YIN 算法估算基频
        f0 = librosa.yin(
            y_segment, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7")
        )
        pitch_hz = np.median(f0)
        pitch_note = librosa.hz_to_note(pitch_hz)
        pitches.append((pitch_hz, pitch_note))
    return pitches


if __name__ == "__main__":
    path = "p.wav"  # 你的音频文件路径
    y, sr = load_audio(path)
    onset_frames, onset_times = detect_onsets(y, sr)
    pitches = estimate_pitches(y, sr, onset_frames)

    for i, (hz, note) in enumerate(pitches):
        print(f"Note {i+1}: {note} ({hz:.2f} Hz)")

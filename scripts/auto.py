"""
自动化脚本, 循环演奏文件夹内的mid, 无ui
"""
import mido
import threading
import os

from core import midi_to_events, play_events, midi_total_length, stop as core_stop

def auto_play(pth: str):
    files = os.listdir(pth)
    for fi in files:
        print(pth, fi)
        mid = mido.MidiFile(os.path.join(pth,fi))
        events = midi_to_events(mid, min_time=0, max_time=midi_total_length(mid))
        stop_flag = threading.Event()
        play_events(events, stop_flag, None)

if __name__ == "__main__":
    pth = "./mid"
    while True:
        auto_play(pth)

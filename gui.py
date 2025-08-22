"""
PyQt5 界面。通过 core 中的函数把裁剪后的事件传入 core.play_events。
"""

import sys
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QFileDialog, QSlider
)
from PyQt5.QtCore import Qt, QTimer
import mido
from core import midi_to_events, play_events, midi_total_length, stop as core_stop
import core
import online

# allows "online" load files into "gui"
w = None

class MidiKeyboardGUI(QWidget):
    def __init__(self):
        global pub_mid
        super().__init__()
        self.setWindowTitle("over field midi player (Windows)")
        #self.setWindowFlags(Qt.Window)
        self.resize(640, 260)

        self.midi = None
        self.total_ms = 0  # total length in milliseconds
        self.play_thread = None
        self.stop_flag = threading.Event()

        # Widgets
        self.load_btn = QPushButton("load MIDI file")
        self.start_btn = QPushButton("start")
        self.stop_btn = QPushButton("stop")
        self.info_label = QLabel("no MIDI file")
        self.api_btn = QPushButton("online midi")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        # slider for selecting clip end time (ms)
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setValue(0)
        # slider for selecting clip start time (ms)
        self.start_slider = QSlider(Qt.Horizontal)
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(0)
        self.start_slider.setValue(0)

        self.time_label = QLabel("start: 0.000 s    end: 0.000 s")

        # Layout
        top_row = QHBoxLayout()
        top_row.addWidget(self.load_btn)
        top_row.addWidget(self.start_btn)
        top_row.addWidget(self.stop_btn)
        top_row.addWidget(self.api_btn)

        mid_row = QHBoxLayout()
        mid_row.addWidget(self.info_label)

        # sliders layout (start and end stacked)
        slider_row = QVBoxLayout()
        slider_row.addWidget(QLabel("start"))
        slider_row.addWidget(self.start_slider)
        slider_row.addWidget(QLabel("end"))
        slider_row.addWidget(self.time_slider)
        slider_row.addWidget(self.time_label)

        main = QVBoxLayout()
        main.addLayout(top_row)
        main.addLayout(mid_row)
        main.addLayout(slider_row)
        main.addWidget(self.progress_bar)

        self.setLayout(main)

        # Connections
        self.load_btn.clicked.connect(self.select_file)
        self.start_btn.clicked.connect(self.start_playback)
        self.stop_btn.clicked.connect(self.stop_playback)
        self.api_btn.clicked.connect(self.open_midi_browser)
        self.time_slider.valueChanged.connect(self.update_time_label)
        self.start_slider.valueChanged.connect(self.update_time_label)

        # ensure sliders keep valid ordering
        self.start_slider.sliderReleased.connect(self._ensure_slider_order)
        self.time_slider.sliderReleased.connect(self._ensure_slider_order)

        # Timer for GUI progress smoothing (in case we want periodic updates)
        self.gui_timer = QTimer()
        self.gui_timer.setInterval(100)
        self.gui_timer.timeout.connect(self._gui_timer_tick)
        self.gui_timer.start()

        # internal progress time (seconds) updated by callback from play_events
        self._current_play_time = 0.0
    
    def open_midi_browser(self):
        # API base url 
        api_base = "http://139.196.113.128:1200/"
        self.online_dlg = online.midiBrowser(api_base, w)
        a=self.online_dlg.show()

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select MIDI file", "", "MIDI Files (*.mid *.midi)")
        if not path:
            return
        self.load_midi(path)
    
    def load_midi(self,path):
        try:
            mid = mido.MidiFile(path)
        except Exception as e:
            self.info_label.setText(f"cannot load MIDI: {e}")
            return
        self.midi = mid
        total = midi_total_length(mid)
        self.total_ms = int(total * 1000)
        self.info_label.setText(f"loaded: {path}  time: {total:.3f} s")
        # configure sliders (ms)
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(max(1, self.total_ms))
        self.start_slider.setValue(0)

        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(max(1, self.total_ms))
        self.time_slider.setValue(self.time_slider.maximum())

        self.update_time_label()
        # set progress bar to zero
        self.progress_bar.setValue(0)

    def update_time_label(self, _=None):
        start_ms = self.start_slider.value()
        end_ms = self.time_slider.value()
        # keep them in order visually (we also enforce on release)
        if end_ms < start_ms:
            end_ms, start_ms = start_ms, end_ms
        s_start = start_ms / 1000.0
        s_end = end_ms / 1000.0
        self.time_label.setText(f"start {s_start:.3f} s    end {s_end:.3f} s")

    def _ensure_slider_order(self):
        # make sure start <= end; if not, snap the end to start
        s = self.start_slider.value()
        e = self.time_slider.value()
        if s > e:
            # move the end to equal start so the clip is valid
            self.time_slider.setValue(s)

    def start_playback(self):
        if self.midi is None:
            self.info_label.setText("please load MIDI file first")
            return
        # if a previous thread is running, stop it first
        if self.play_thread and self.play_thread.is_alive():
            self.info_label.setText("A task is already running, please stop it first")
            return
        # prepare events clipped by slider time
        start_ms = self.start_slider.value()
        clip_ms = self.time_slider.value()
        if clip_ms <= start_ms:
            self.info_label.setText("the end time must be greater than the start time")
            return
        start_s = start_ms / 1000.0
        clip_s = clip_ms / 1000.0

        # Try to use midi_to_events with min_time if supported by core
        events = None
        try:
            events = midi_to_events(self.midi, min_time=start_s, max_time=clip_s)
        except TypeError:
            # fallback: get events up to end, then filter/shift locally (best-effort)
            try:
                raw_events = midi_to_events(self.midi, max_time=clip_s)
            except Exception as e:
                self.info_label.setText(f"failed: {e}")
                return

            # best-effort generic filter + shift for typical event formats
            def _filter_and_shift(ev_list, start_t):
                if not ev_list:
                    return []
                # tuple-like (time, ...)
                try:
                    first = ev_list[0]
                    if isinstance(first, (list, tuple)) and isinstance(first[0], (int, float)):
                        filtered = [(t - start_t, *rest) for (t, *rest) in ev_list if t >= start_t]
                        return filtered
                    # dict with 'time'
                    if isinstance(first, dict) and 'time' in first:
                        new = []
                        for e in ev_list:
                            if e['time'] >= start_t:
                                ne = e.copy()
                                ne['time'] = ne['time'] - start_t
                                new.append(ne)
                        return new
                    # objects with .time attribute
                    if hasattr(first, 'time'):
                        new = []
                        for e in ev_list:
                            if getattr(e, 'time', 0) >= start_t:
                                # clone might not be necessary, but try to avoid mutating original
                                try:
                                    ne = e
                                    ne.time = ne.time - start_t
                                    new.append(ne)
                                except Exception:
                                    # as fallback, append original
                                    new.append(e)
                        return new
                except Exception:
                    pass
                # unknown format: return as-is
                return ev_list

            events = _filter_and_shift(raw_events, start_s)

        # if still no events
        if not events:
            self.info_label.setText("There are no events after cropping (or the time is too short)")
            return

        # Remove trailing silence: best-effort trimming of trailing non-note interval
        def _is_note_event(item):
            # heuristics: examine common formats
            try:
                if isinstance(item, (list, tuple)) and isinstance(item[0], (int, float)):
                    msg = item[1] if len(item) > 1 else None
                    if hasattr(msg, 'type'):
                        return msg.type in ('note_on', 'note_off')
                    # dict-like message
                    if isinstance(msg, dict) and msg.get('type') in ('note_on', 'note_off'):
                        return True
                if isinstance(item, dict) and 'msg' in item:
                    msg = item['msg']
                    if hasattr(msg, 'type'):
                        return msg.type in ('note_on', 'note_off')
                    if isinstance(msg, dict) and msg.get('type') in ('note_on', 'note_off'):
                        return True
                if hasattr(item, 'msg') and hasattr(item.msg, 'type'):
                    return item.msg.type in ('note_on', 'note_off')
                if hasattr(item, 'type') and item.type in ('note_on', 'note_off'):
                    return True
            except Exception:
                pass
            return False

        try:
            # find last index that contains a note event
            last_note_index = -1
            for i, ev in enumerate(events):
                if _is_note_event(ev):
                    last_note_index = i
            if last_note_index >= 0:
                events = events[: last_note_index + 1]
        except Exception:
            # if trimming fails, ignore and keep events
            pass

        # reset stop flag
        self.stop_flag = threading.Event()
        # progress callback updates internal variable used by GUI timer
        def progress_cb(current_time):
            # current_time is approximate playback seconds since start (may be slightly coarse)
            self._current_play_time = current_time

        # thread target
        def target():
            self.info_label.setText("running")
            time.sleep(3)
            try:
                play_events(events, self.stop_flag, progress_callback=progress_cb)
                if not self.stop_flag.is_set():
                    self.info_label.setText("finish")
                else:
                    self.info_label.setText("stop")
            except Exception as e:
                self.info_label.setText(f"error: {e}")

        self.play_thread = threading.Thread(target=target, daemon=True)
        self.play_thread.start()

    def stop_playback(self):
        if self.play_thread and self.play_thread.is_alive():
            core_stop(self.stop_flag)  # set stop flag to request stop
            # The play thread will release held keys before returning
            self.info_label.setText("stop")
        else:
            self.info_label.setText("no task")

    def _gui_timer_tick(self):
        # update progress bar if total known
        if self.midi is None or self.total_ms == 0:
            return
        # compute clip duration
        start_ms = self.start_slider.value()
        end_ms = self.time_slider.value()
        clip_ms = max(1, end_ms - start_ms)
        percent = min(1.0, (self._current_play_time * 1000.0) / clip_ms)
        self.progress_bar.setValue(int(percent * 1000))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MidiKeyboardGUI()
    w.show()
    sys.exit(app.exec_())

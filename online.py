"""
midi下载界面。通过 gui 唤起
"""
import threading
import tempfile
import os
import requests
from urllib.parse import urljoin

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QWidget, QFileDialog, QMessageBox, QInputDialog, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtGui import QDesktopServices

class midiBrowser(QDialog):
    songs_loaded = pyqtSignal(dict)          # emits the JSON from /latest_songs
    operation_result = pyqtSignal(bool, str) # (success, message)

    def __init__(self, api_base_url="http://127.0.0.1:8000/", gui_object=None):
        super().__init__()
        self.setWindowTitle("Online MIDI Browser")
        #self.setWindowFlags(Qt.Window)
        self.resize(700, 500)
        self.api_base = api_base_url.rstrip("/") + "/"
        self.page = 1
        self.page_size = 20
        self.gui_obj=gui_object

        # Top: search + refresh
        top_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name and press Enter")
        self.search_edit.returnPressed.connect(self.on_search)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_latest)
        self.refresh_btn.setAutoDefault(False)
        top_layout.addWidget(self.search_edit)
        top_layout.addWidget(self.refresh_btn)

        # Scrollable area for items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout()
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_container.setLayout(self.list_layout)
        self.scroll.setWidget(self.list_container)

        # Pagination controls
        pager_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.next_btn = QPushButton("Next")
        self.page_label = QLabel("Page 1")
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        pager_layout.addWidget(self.prev_btn)
        pager_layout.addWidget(self.page_label)
        pager_layout.addWidget(self.next_btn)
        pager_layout.addStretch()

        # Bottom: upload button
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.on_upload)
        bottom_layout.addWidget(self.upload_btn)

        # Main layout
        main = QVBoxLayout()
        main.addLayout(top_layout)
        main.addWidget(self.scroll)
        main.addLayout(pager_layout)
        main.addLayout(bottom_layout)
        self.setLayout(main)

        # Signals
        self.songs_loaded.connect(self._on_songs_loaded)
        self.operation_result.connect(self._on_operation_result)

        # Load first page
        self.load_latest()

    # network workers
    def load_latest(self):
        self.page_label.setText(f"Loading page {self.page}...")
        threading.Thread(target=self._worker_load_latest, daemon=True).start()

    def _worker_load_latest(self):
        try:
            url = urljoin(self.api_base, "latest_songs")
            resp = requests.get(url, params={"page": self.page, "page_size": self.page_size}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            data = {"error": str(e)}
        self.songs_loaded.emit(data)

    def _worker_search(self, name):
        try:
            url = urljoin(self.api_base, "search")
            resp = requests.get(url, params={"name": name}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            data = {"error": str(e)}
        self.songs_loaded.emit(data)

    def _worker_download(self, hash_val, save_path, open_after=False):
        try:
            url = urljoin(self.api_base, "download")
            with requests.get(url, params={"hash": hash_val}, stream=True, timeout=5) as r:
                r.raise_for_status()
                # total = r.headers.get("Content-Length")
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            msg = f"Downloaded to {save_path}"
            success = True
            if open_after:
                QDesktopServices.openUrl(QUrl.fromLocalFile(save_path))
            return True
        except Exception as e:
            success = False
            msg = f"Download failed: {e}"
            self.operation_result.emit(success, msg)
            return False

    def _worker_delete(self, hash_val, password):
        try:
            url = urljoin(self.api_base, "delete")
            resp = requests.post(url, data={"hash": hash_val, "delete_password": password}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            succeed = data.get("succeed", False)
            message = data.get("message", str(data))
        except Exception as e:
            succeed = False
            message = f"Delete failed: {e}"
        self.operation_result.emit(succeed, message)

    def _worker_upload(self, file_path, upload_by, delete_password):
        try:
            url = urljoin(self.api_base, "upload")
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "audio/midi")}
                data = {"upload_by": upload_by, "delete_password": delete_password}
                resp = requests.post(url, files=files, data=data, timeout=60)
                resp.raise_for_status()
                j = resp.json()
                succeed = j.get("succeed", False)
                message = j.get("message", str(j))
        except Exception as e:
            succeed = False
            message = f"Upload failed: {e}"
        self.operation_result.emit(succeed, message)

    # UI callbacks
    def on_search(self):
        name = self.search_edit.text().strip()
        if not name:
            self.page = 1
            self.load_latest()
            return
        self.page_label.setText("Searching...")
        threading.Thread(target=self._worker_search, args=(name,), daemon=True).start()

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.load_latest()

    def next_page(self):
        self.page += 1
        self.load_latest()

    def on_upload(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MIDI file to upload", "", "MIDI files (*.mid *.midi);;All files (*)")
        if not file_path:
            return
        try:
            size = os.path.getsize(file_path)
        except Exception:
            QMessageBox.warning(self, "Error", "Cannot access file.")
            return
        MAX_FILE_SIZE = 1048576  # 1MB
        if size > MAX_FILE_SIZE:
            QMessageBox.warning(self, "Too large", "File exceeds 1MB maximum.")
            return
        # ask for upload_by and delete_password
        upload_by, ok1 = QInputDialog.getText(self, "Upload by", "Uploaded by (your name):")
        if not ok1:
            return
        delete_password, ok2 = QInputDialog.getText(self, "Delete password", "Delete password (will be required to delete):", echo=QLineEdit.Password)
        if not ok2:
            return
        threading.Thread(target=self._worker_upload, args=(file_path, upload_by, delete_password), daemon=True).start()

    # signal handlers
    def _on_songs_loaded(self, data):
        # clear list
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # error handling
        if not isinstance(data, dict):
            self.list_layout.addWidget(QLabel("Invalid response."))
            return
        if "error" in data:
            self.list_layout.addWidget(QLabel(f"Error: {data['error']}"))
            self.page_label.setText("Error")
            return

        # Two possible response shapes:
        # 1) latest_songs: contains "midis", "total_pages", "count"
        # 2) search: contains "results"
        items = []
        if "midis" in data:
            items = data.get("midis", [])
            total_pages = data.get("total_pages", None)
            count = data.get("count", None)
            if total_pages:
                self.page_label.setText(f"Page {self.page} / {total_pages}")
            else:
                self.page_label.setText(f"Page {self.page}")
        elif "results" in data:
            items = data.get("results", [])
            self.page_label.setText(f"Search results ({len(items)})")
        else:
            # fallback
            items = data.get("results", []) if "results" in data else []
            self.page_label.setText("No results")

        if not items:
            self.list_layout.addWidget(QLabel("No songs found."))
            return

        for entry in items:
            # expected fields: name, hash, maybe uploader, duration, etc.
            name = entry.get("name") or entry.get("title") or entry.get("filename") or "<unnamed>"
            hash_val = entry.get("hash") or entry.get("id") or entry.get("file_hash") or ""
            meta_text = f"{name}\n(up: {upload_by})" #"{name}  (hash: {hash_val})"
            row = QWidget()
            row_layout = QHBoxLayout()
            lbl = QLabel(meta_text)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row_layout.addWidget(lbl)

            load_btn = QPushButton("Load")
            dl_btn = QPushButton("Download")
            del_btn = QPushButton("Delete")

            # wire up callbacks with lambdas capturing hash_val and name
            load_btn.clicked.connect(lambda checked, h=hash_val, n=name: self.load_item(h, n))
            dl_btn.clicked.connect(lambda checked, h=hash_val, n=name: self.download_item(h, n))
            del_btn.clicked.connect(lambda checked, h=hash_val, n=name: self.delete_item(h, n))

            row_layout.addWidget(load_btn)
            row_layout.addWidget(dl_btn)
            row_layout.addWidget(del_btn)
            row.setLayout(row_layout)
            self.list_layout.addWidget(row)

    def _on_operation_result(self, success, message):
        #title = "Success" if success else "Error"
        if not success:
            title = "Error"
            QMessageBox.information(self, title, message)

    # ---------------- item actions ----------------
    def download_item(self, hash_val, name):
        # ask user for save file path
        suggested = f"{name}.mid" if name else f"{hash_val}.mid"
        save_path  , _ = QFileDialog.getSaveFileName(self, "Save MIDI file", suggested, "MIDI files (*.mid *.midi);;All files (*)")
        if not save_path:
            return
        threading.Thread(target=self._worker_download, args=(hash_val, save_path, False), daemon=True).start()

    def load_item(self, hash_val, name):
        # download to tmp and load
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mid")
        os.close(tmp_fd)
        # start worker to download and load
        # if not success -> _worker_download() -> _on_operation_result()
        if self._worker_download(hash_val, tmp_path):
            self.gui_obj.load_midi(tmp_path)
        

    def delete_item(self, hash_val, name):
        # ask password
        pwd, ok = QInputDialog.getText(self, "Delete confirmation", f"Enter delete password for:\n{name}", echo=QLineEdit.Password)
        if not ok:
            return
        threading.Thread(target=self._worker_delete, args=(hash_val, pwd), daemon=True).start()

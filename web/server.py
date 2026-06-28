import asyncio
import hashlib
import json
import logging
import logging.config
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from typing import Optional

import mido
import music21
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rapidfuzz import fuzz, process

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(message)s",
        },
    },
    "handlers": {
        # 控制台输出
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        # 文件输出
        "file": {
            "class": "logging.FileHandler",
            "filename": "uvicorn_app.log",
            "formatter": "default",
            "encoding": "utf-8",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"],
    },
}

logging.config.dictConfig(logging_config)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-cache"
    return response


db_file_path = "songs.json"
comments_db_file_path = "comments.json"
db_lock = asyncio.Lock()
comments_lock = asyncio.Lock()
db_thread_lock = threading.Lock()
bg_executor = ThreadPoolExecutor(max_workers=1)

_processing_lock = threading.Lock()
_processing = {}


def _claim_cache(cache_key, cache_path):
    while True:
        if os.path.exists(cache_path):
            return False
        with _processing_lock:
            if os.path.exists(cache_path):
                return False
            ev = _processing.get(cache_key)
            if ev is None:
                _processing[cache_key] = threading.Event()
                return True
        ev.wait()


def _release_cache(cache_key):
    with _processing_lock:
        ev = _processing.pop(cache_key, None)
    if ev:
        ev.set()


MAX_FILE_SIZE = 10485760
MIDI_EXTENSIONS = {".mid", ".midi"}
XML_EXTENSIONS = {".xml", ".musicxml", ".mxl"}
CACHE_DIR = "cache"
ADMIN_PASSWORD = "abc"
os.makedirs(CACHE_DIR, exist_ok=True)


def load_database():
    if os.path.exists(db_file_path):
        with open(db_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


async def save_database():
    async with db_lock:
        with open(db_file_path, "w", encoding="utf-8") as f:
            json.dump(songs_db, f, indent=4, ensure_ascii=False)


def _save_database_sync():
    with db_thread_lock:
        with open(db_file_path, "w", encoding="utf-8") as f:
            json.dump(songs_db, f, indent=4, ensure_ascii=False)


def load_comments_database():
    if os.path.exists(comments_db_file_path):
        with open(comments_db_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


async def save_comments_database():
    async with comments_lock:
        with open(comments_db_file_path, "w", encoding="utf-8") as f:
            json.dump(comments_db, f, indent=4, ensure_ascii=False)


songs_db = load_database()
comments_db = load_comments_database()


def detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in XML_EXTENSIONS:
        return "musicxml"
    return "midi"


class MusicInfo(BaseModel):
    name: str
    upload_by: str
    duration: int
    file_size: int
    hash: str


class UploadResponse(BaseModel):
    succeed: bool
    message: str


app.mount("/static", StaticFiles(directory="static"), name="static")


def fuzzy_search(name: str, songs_db: dict, threshold: float = 70):
    results = []
    for song in songs_db.values():
        score = fuzz.token_set_ratio(name.lower(), song["name"].lower()[:-4])
        if score >= threshold:
            results.append(
                {
                    **{k: v for k, v in song.items() if k != "delete_password"},
                    "confidence": score / 100,
                }
            )
    return sorted(results, key=lambda x: x["confidence"], reverse=True)


def _convert_xml_to_midi(xml_path: str, file_hash: str) -> Optional[str]:
    midi_path = os.path.join(CACHE_DIR, file_hash + ".mid")
    if os.path.exists(midi_path):
        return midi_path
    score = music21.converter.parse(xml_path)
    score.write("midi", fp=midi_path)
    return midi_path


def _convert_midi_to_xml(midi_path: str, file_hash: str) -> Optional[str]:
    xml_path = os.path.join(CACHE_DIR, file_hash + ".mxl")
    if os.path.exists(xml_path):
        return xml_path
    score = music21.converter.parse(midi_path)
    if file_hash in songs_db:
        song_name = os.path.splitext(songs_db[file_hash]["name"])[0]
        score.metadata.title = song_name
    score.write("musicxml", fp=xml_path)
    return xml_path


def _calc_xml_duration_bg(file_hash: str, score):
    midi_path = os.path.join(CACHE_DIR, file_hash + ".mid")
    try:
        score.write("midi", fp=midi_path)
        midi_file = mido.MidiFile(midi_path)
        duration_ms = int(midi_file.length * 1000)
        midi_size = os.path.getsize(midi_path)
        if file_hash in songs_db:
            songs_db[file_hash]["duration"] = duration_ms
            songs_db[file_hash]["midi_size"] = midi_size
            _save_database_sync()
            print(
                f"[BG] XML duration: {songs_db[file_hash]['name']} {duration_ms}ms ({midi_size}B)"
            )
    except Exception as e:
        print(f"[WARN] XML duration calc failed: {e}")
        if os.path.exists(midi_path):
            os.remove(midi_path)


@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/delete")
async def delete_music(
    hash: str = Form(...),
    delete_password: Optional[str] = Form(None),
    admin_password: Optional[str] = Form(None),
    route_admin: Optional[str] = Query(None),
):
    if hash not in songs_db:
        return {"succeed": False, "message": "Music not found."}
    music = songs_db[hash]
    is_admin = (admin_password and admin_password == ADMIN_PASSWORD) or (
        route_admin and route_admin == ADMIN_PASSWORD
    )
    if not is_admin and (delete_password or "") != music["delete_password"]:
        return {"succeed": False, "message": "Invalid delete password."}
    file_path = os.path.join("uploads", music["name"])
    if os.path.exists(file_path):
        os.remove(file_path)
    del songs_db[hash]
    await save_database()
    return {"succeed": True, "message": "File deleted."}


@app.get("/latest_songs")
def get_latest_songs(
    page: int = Query(1, gt=0),
    page_size: int = Query(20, gt=0),
    file_type: Optional[str] = Query(None),
):
    filtered = [
        s
        for s in songs_db.values()
        if not file_type or s.get("file_type", "midi") == file_type
    ]
    total_songs = len(filtered)
    start = (page - 1) * page_size
    if start >= total_songs:
        return {"total_pages": 0, "count": total_songs, "midis": []}
    songs_list = [
        {k: v for k, v in song.items() if k != "delete_password"}
        for song in filtered[start : start + page_size]
    ]
    return {
        "total_pages": (total_songs + page_size - 1) // page_size,
        "count": total_songs,
        "midis": songs_list,
    }


@app.get("/search")
def search_songs(name: str):
    if name == "*":
        while True:
            key = random.choice(list(songs_db.keys()))
            if (
                songs_db[key]["duration"] > 1000 * 60 * 15
                or songs_db[key]["file_size"] > 1024 * 128
            ):
                continue
            results = [
                {k: v for k, v in songs_db[key].items() if k != "delete_password"}
            ]
            return {"message": "Random song", "results": results}
    results = fuzzy_search(name, songs_db)
    uploader_matches = []
    for song in songs_db.values():
        if song.get("upload_by", "") == name:
            uploader_matches.append(
                {
                    **{k: v for k, v in song.items() if k != "delete_password"},
                    "match_type": "uploader",
                }
            )
    if uploader_matches:
        seen_hashes = {r["hash"] for r in results}
        for r in uploader_matches:
            if r["hash"] not in seen_hashes:
                results.append(r)
    if not results:
        return JSONResponse(
            content={"message": "No songs found", "results": []}, status_code=200
        )
    msg = f"Found {len(results)} songs"
    if uploader_matches:
        msg += f" (including {len(uploader_matches)} by '{name}')"
    return {"message": msg, "results": results}


@app.post("/add_comment")
async def add_comment(
    name: str = Form(...), content: str = Form(...), device_id: str = Form(...)
):
    if len(name.strip()) > 20:
        return {"succeed": False, "message": "Name must be 20 characters or fewer."}
    if len(content.strip()) > 100:
        return {"succeed": False, "message": "Comment must be 100 characters or fewer."}
    comment_id = hashlib.md5(
        f"{name}-{content}-{datetime.now().isoformat()}-{device_id}".encode()
    ).hexdigest()
    comment = {
        "id": comment_id,
        "name": name,
        "content": content,
        "device_id": device_id,
        "created_at": datetime.now().isoformat(),
    }
    comments_db[comment_id] = comment
    await save_comments_database()
    return {"succeed": True, "message": "Comment added.", "comment": comment}


@app.get("/comments")
def get_comments():
    comments_list = sorted(
        list(comments_db.values()), key=lambda x: x["created_at"], reverse=True
    )
    return {"succeed": True, "message": "Comments loaded.", "comments": comments_list}


@app.post("/delete_comment")
async def delete_comment(
    comment_id: str = Form(...),
    device_id: str = Form(...),
    admin_password: Optional[str] = Form(None),
    route_admin: Optional[str] = Query(None),
):
    if comment_id not in comments_db:
        return {"succeed": False, "message": "Comment not found."}
    comment = comments_db[comment_id]
    is_admin = False
    if admin_password and admin_password == ADMIN_PASSWORD:
        is_admin = True
    elif route_admin and route_admin == ADMIN_PASSWORD:
        is_admin = True
    if not is_admin and comment["device_id"] != device_id:
        return {"succeed": False, "message": "You can only delete your own comments."}
    if is_admin:
        print(f"[ADMIN] delete comment: {comment_id}, {comment['name']}")
    del comments_db[comment_id]
    await save_comments_database()
    return {"succeed": True, "message": "Comment deleted."}


@app.get("/download")
def download_file(hash: str, semitones: int = Query(0), bpm: int = Query(0, ge=0)):
    if hash not in songs_db:
        raise HTTPException(status_code=404, detail="Music not found.")
    song = songs_db[hash]
    file_path = os.path.join("uploads", song["name"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server.")
    if semitones != 0 or bpm > 0:
        cache_key = f"{hash}_t{semitones}_b{bpm}.mid"
        midi_path = os.path.join(CACHE_DIR, cache_key)
        if _claim_cache(cache_key, midi_path):
            try:
                if song.get("file_type") == "midi":
                    mid = mido.MidiFile(file_path)
                    if semitones != 0:
                        for track in mid.tracks:
                            for msg in track:
                                if msg.type in ("note_on", "note_off") and hasattr(
                                    msg, "note"
                                ):
                                    msg.note = max(0, min(127, msg.note + semitones))
                    if bpm > 0:
                        new_tempo = mido.bpm2tempo(bpm)
                        found = False
                        for track in mid.tracks:
                            for msg in track:
                                if msg.type == "set_tempo":
                                    msg.tempo = new_tempo
                                    found = True
                        if not found:
                            mid.tracks[0].insert(
                                0, mido.MetaMessage("set_tempo", tempo=new_tempo)
                            )
                    mid.save(midi_path)
                else:
                    score = music21.converter.parse(file_path)
                    if semitones != 0:
                        score.transpose(semitones, inPlace=True)
                    if bpm > 0:
                        flat_score = score.flatten()
                        marks = list(
                            flat_score.getElementsByClass(music21.tempo.MetronomeMark)
                        )
                        for el in marks:
                            el.number = bpm
                        if not marks:
                            score.insert(0, music21.tempo.MetronomeMark(number=bpm))
                    score.write("midi", fp=midi_path)
            finally:
                _release_cache(cache_key)
        midi_name = os.path.splitext(song["name"])[0] + ".mid"
        filename = midi_name.encode("utf-8").decode("latin1")
        return FileResponse(
            midi_path,
            media_type="audio/midi",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if song.get("file_type") == "musicxml":
        converted_path = _convert_xml_to_midi(file_path, hash)
        if converted_path:
            midi_name = os.path.splitext(song["name"])[0] + ".mid"
            filename = midi_name.encode("utf-8").decode("latin1")
            return FileResponse(
                converted_path,
                media_type="audio/midi",
                filename=filename,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
    filename = song["name"].encode("utf-8").decode("latin1")
    return FileResponse(
        file_path,
        media_type="audio/midi",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/download_xml")
def download_xml_file(
    hash: str,
    raw: Optional[str] = Query(None),
    semitones: int = Query(0),
    bpm: int = Query(0, ge=0),
):
    if hash not in songs_db:
        raise HTTPException(status_code=404, detail="Music not found.")
    song = songs_db[hash]
    file_path = os.path.join("uploads", song["name"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server.")
    if semitones != 0 or bpm > 0:
        cache_key = f"{hash}_t{semitones}_b{bpm}.mxl"
        mxl_path = os.path.join(CACHE_DIR, cache_key)
        if _claim_cache(cache_key, mxl_path):
            try:
                if song.get("file_type") == "midi":
                    mid = mido.MidiFile(file_path)
                    if semitones != 0:
                        for track in mid.tracks:
                            for msg in track:
                                if msg.type in ("note_on", "note_off") and hasattr(
                                    msg, "note"
                                ):
                                    msg.note = max(0, min(127, msg.note + semitones))
                    if bpm > 0:
                        new_tempo = mido.bpm2tempo(bpm)
                        found = False
                        for track in mid.tracks:
                            for msg in track:
                                if msg.type == "set_tempo":
                                    msg.tempo = new_tempo
                                    found = True
                        if not found:
                            mid.tracks[0].insert(
                                0, mido.MetaMessage("set_tempo", tempo=new_tempo)
                            )
                    temp_midi = os.path.join(CACHE_DIR, f"__tmp_{hash}_t{semitones}_b{bpm}.mid")
                    try:
                        mid.save(temp_midi)
                        score = music21.converter.parse(temp_midi)
                        if hash in songs_db:
                            score.metadata.title = os.path.splitext(
                                songs_db[hash]["name"]
                            )[0]
                        score.write("musicxml", fp=mxl_path)
                    finally:
                        if os.path.exists(temp_midi):
                            os.remove(temp_midi)
                else:
                    score = music21.converter.parse(file_path)
                    if semitones != 0:
                        score.transpose(semitones, inPlace=True)
                    if bpm > 0:
                        flat_score = score.flatten()
                        marks = list(
                            flat_score.getElementsByClass(music21.tempo.MetronomeMark)
                        )
                        for el in marks:
                            el.number = bpm
                        if not marks:
                            score.insert(0, music21.tempo.MetronomeMark(number=bpm))
                    if hash in songs_db:
                        score.metadata.title = os.path.splitext(songs_db[hash]["name"])[
                            0
                        ]
                    score.write("musicxml", fp=mxl_path)
            finally:
                _release_cache(cache_key)
        xml_name = os.path.splitext(song["name"])[0] + ".mxl"
        filename = xml_name.encode("utf-8").decode("latin1")
        return FileResponse(
            mxl_path,
            media_type="application/vnd.recordare.musicxml+xml",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if raw and raw.lower() == "true":
        filename = song["name"].encode("utf-8").decode("latin1")
        media_type = (
            "application/vnd.recordare.musicxml+xml"
            if song.get("file_type") == "musicxml"
            else "audio/midi"
        )
        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if song.get("file_type") == "musicxml":
        filename = song["name"].encode("utf-8").decode("latin1")
        return FileResponse(
            file_path,
            media_type="application/vnd.recordare.musicxml+xml",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    converted_path = _convert_midi_to_xml(file_path, hash)
    if converted_path:
        xml_name = os.path.splitext(song["name"])[0] + ".mxl"
        filename = xml_name.encode("utf-8").decode("latin1")
        return FileResponse(
            converted_path,
            media_type="application/vnd.recordare.musicxml+xml",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    filename = song["name"].encode("utf-8").decode("latin1")
    return FileResponse(
        file_path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    upload_by: str = Form(""),
    delete_password: str = Form(""),
):
    global songs_db
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return JSONResponse(
            content={"succeed": False, "message": "File size exceeds 10MB limit."}
        )
    file_hash = hashlib.md5(file_data).hexdigest()
    if file_hash in songs_db:
        return JSONResponse(
            content={
                "succeed": False,
                "message": f"Duplicate: {songs_db[file_hash]['name']}",
            }
        )
    file_name = (
        file.filename.replace("primary:", "")
        if file.filename.startswith("primary:")
        else file.filename
    )
    file_type = detect_file_type(file_name)
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(os.path.join("uploads", file_name)):
        file_name = f"{base_name}({counter}){ext}"
        counter += 1
    file_path = os.path.join("uploads", file_name)
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(file_data)

    if file_type == "musicxml":
        try:
            score = music21.converter.parse(file_path)
        except Exception:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Failed to parse music file.")
        duration_ms = 0
        bg_executor.submit(_calc_xml_duration_bg, file_hash, score)
    else:
        midi_file = mido.MidiFile(file=BytesIO(file_data))
        duration_ms = int(midi_file.length * 1000)
    songs_db = {
        file_hash: {
            "name": file_name,
            "upload_by": upload_by,
            "duration": duration_ms,
            "file_size": len(file_data),
            "hash": file_hash,
            "delete_password": delete_password,
            "upload_time": datetime.now().isoformat(),
            "file_type": file_type,
        },
        **songs_db,
    }
    await save_database()
    return {"succeed": True, "message": f"'{file_name}' uploaded."}


if __name__ == "__main__":
    uvicorn.run(
        app=app, host="0.0.0.0", port=1200, log_level="info", log_config=logging_config
    )

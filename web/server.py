import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import hashlib
import os
import json
from io import BytesIO
from datetime import timedelta
import mido
import asyncio
import logging
import logging.config
from rapidfuzz import fuzz, process
import random


# 自定义日志配置
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

# 索引文件路径
db_file_path = "songs.json"
db_lock = asyncio.Lock()

# 初始化索引
def load_database():
    if os.path.exists(db_file_path):
        with open(db_file_path, "r") as f:
            return json.load(f)
    return {}

async def save_database():
    async with db_lock:
        with open(db_file_path, "w") as f:
            json.dump(songs_db, f, indent=4, ensure_ascii=False)

songs_db = load_database()

class MusicInfo(BaseModel):
    name: str
    upload_by: str
    duration: int  # milliseconds
    file_size: int  # bytes
    hash: str

@app.get("/", response_class=HTMLResponse)
def index():
    with open("mid.html", "r", encoding="utf-8") as f:
        return f.read()
        
 
@app.post("/delete")
async def delete_music(
    hash: str = Form(...),
    delete_password: str = Form(...)
):
    """
    删除音乐文件
    """
    if hash not in songs_db:
        #raise HTTPException(status_code=404, detail="Music not found.")
        return {"succeed": False, "message": "Music not found."}

    music = songs_db[hash]
    if music["delete_password"] != delete_password:
        #raise HTTPException(status_code=400, detail="Invalid delete password.")
        return {"succeed": False, "message": "Invalid delete password."}

    # 删除音乐
    file_path = os.path.join("uploads", music["name"])
    if os.path.exists(file_path):
        os.remove(file_path)

    del songs_db[hash]
    await save_database()
    return {"succeed": True, "message": "Music deleted successfully."}

@app.get("/latest_songs")
def get_latest_songs(page: int = Query(1, gt=0), page_size: int = Query(20, gt=0)):
    """
    获取最新歌曲列表，支持分页。
    """
    total_songs = len(songs_db)
    start = (page - 1) * page_size
    end = start + page_size

    if start >= total_songs:
        return JSONResponse(content={
            "total_pages": (total_songs + page_size - 1) // page_size,
            "count": total_songs,
            "midis": []
        }, status_code=200)

    # 将数据库转为列表后进行切片并隐藏密码字段
    songs_list = [
        {k: v for k, v in song.items() if k != "delete_password"}
        for song in list(songs_db.values())[start:end]
    ]
    return {
        "total_pages": (total_songs + page_size - 1) // page_size,
        "count": total_songs,
        "midis": songs_list
    }
def fuzzy_search(name: str, songs_db: dict, threshold: float = 70):
    """
    模糊匹配搜索（使用 rapidfuzz）
    :param threshold: 最低置信度阈值 (0-100)
    """
    results = []
    for song in songs_db.values():
        # partial_ratio: 部分匹配更友好
        # token_sort_ratio: 忽略词序
        score = fuzz.token_set_ratio(name.lower(), song["name"].lower()[:-4])
        
        if score >= threshold:
            results.append({
                **{k: v for k, v in song.items() if k != "delete_password"},
                "confidence": score / 100  # 转为 0-1 范围
            })
    
    return sorted(results, key=lambda x: x["confidence"], reverse=True)

@app.get("/search")
def search_songs(name: str):
    """
    根据歌曲名称搜索歌曲。
    """
    if name=="*":
        key=random.choice(list(songs_db.keys()))
        results = [{k: v for k, v in songs_db[key].items() if k != "delete_password"}]
        return {
            "message": f"random 1 song",
            "results": results
        }
    results = fuzzy_search(name,songs_db)
    if not results:
        return JSONResponse(content={"message": "No songs found", "results": []}, status_code=200)

    return {
        "message": f"Found {len(results)} songs",
        "results": results
    }

@app.get("/download")
def download_file(hash: str):
    """
    根据哈希值下载文件
    """
    if hash not in songs_db:
        raise HTTPException(status_code=404, detail="Music not found.")

    file_path = os.path.join("uploads", songs_db[hash]["name"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server.")

    filename = songs_db[hash]["name"].encode("utf-8").decode("latin1")
    return FileResponse(file_path, media_type="audio/midi", filename=filename, headers={"Content-Disposition": f"attachment; filename={filename}"})

# 最大文件大小限制 (1MB)
MAX_FILE_SIZE = 1048576

class UploadResponse(BaseModel):
    succeed: bool
    message: str

@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    upload_by: str = Form(...),
    delete_password: str = Form(...),
):
    """
    处理文件上传请求。
    """
    global songs_db
    # 检查文件类型
    """
    if file.content_type != "audio/midi":
        #raise HTTPException(status_code=400, detail="Invalid file type. Only MIDI files are allowed.")
        return JSONResponse(content={"succeed": False, "message": "File size exceeds the maximum limit of 1MB."})
    """
    # 检查文件大小
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return JSONResponse(content={"succeed": False, "message": "File size exceeds the maximum limit of 1MB."})#, status_code=400)

    # 计算文件哈希
    file_hash = hashlib.md5(file_data).hexdigest()

    # 检查哈希是否已存在
    if file_hash in songs_db:
        #raise HTTPException(status_code=400, detail="A file with the same hash already exists.")
        return JSONResponse(content={"succeed": False, "message": "A file with the same hash already exists."})#, status_code=400)

    # 计算 MIDI 时长
    try:
        midi_file = mido.MidiFile(file=BytesIO(file_data))
        midi_duration = midi_file.length
        duration_ms = int(midi_duration * 1000)  # 转为毫秒
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process MIDI file: {str(e)}")

    # 模拟文件存储
    file_name = file.filename
    
    if file_name[:8] == "primary:":
        file_name= file_name.replace("primary:", "")
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(os.path.join("uploads", file_name)):
        file_name = f"{base_name}({counter}){ext}"
        counter += 1

    file_path = os.path.join("uploads", file_name)
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(file_data)

    # 保存到模拟数据库
    songs_db = {
        file_hash : {
            "name": file_name,
            "upload_by": upload_by,
            "duration": duration_ms,
            "file_size": len(file_data),
            "hash": file_hash,
            "delete_password": delete_password
        },
        **songs_db
    }
    await save_database()

    duration_str = str(timedelta(milliseconds=duration_ms))
    return {
        "succeed": True,
        "message": f"File '{file_name}' uploaded successfully. Duration: {duration_str}.",
    }

if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=1200, log_level="debug", log_config=logging_config)

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import hashlib
import os
import json
from io import BytesIO
from datetime import timedelta, datetime
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
comments_db_file_path = "comments.json"
db_lock = asyncio.Lock()
comments_lock = asyncio.Lock()

# 初始化索引
def load_database():
    if os.path.exists(db_file_path):
        with open(db_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def save_database():
    async with db_lock:
        with open(db_file_path, "w", encoding="utf-8") as f:
            json.dump(songs_db, f, indent=4, ensure_ascii=False)

# 初始化留言数据库
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
        return {"succeed": False, "message": "未找到音乐文件。"}

    music = songs_db[hash]
    if music["delete_password"] != delete_password:
        #raise HTTPException(status_code=400, detail="Invalid delete password.")
        return {"succeed": False, "message": "删除密码无效。"}

    # 删除音乐
    file_path = os.path.join("uploads", music["name"])
    if os.path.exists(file_path):
        os.remove(file_path)

    del songs_db[hash]
    await save_database()
    return {"succeed": True, "message": "音乐文件删除成功。"}

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
            "message": f"随机1首歌曲",
            "results": results
        }
    results = fuzzy_search(name,songs_db)
    if not results:
        return JSONResponse(content={"message": "未找到歌曲", "results": []}, status_code=200)

    return {
        "message": f"找到 {len(results)} 首歌曲",
        "results": results
    }

# 留言功能相关API
@app.post("/add_comment")
async def add_comment(
    name: str = Form(...),
    content: str = Form(...),
    device_id: str = Form(...)
):
    """
    添加留言
    """
    # 验证长度限制
    if len(name.strip()) > 20:
        return {"succeed": False, "message": "昵称长度不能超过20个字符"}
    
    if len(content.strip()) > 100:
        return {"succeed": False, "message": "留言内容不能超过100个字符"}
    
    # 生成唯一ID
    comment_id = hashlib.md5(f"{name}-{content}-{datetime.now().isoformat()}-{device_id}".encode()).hexdigest()
    
    # 创建留言对象
    comment = {
        "id": comment_id,
        "name": name,
        "content": content,
        "device_id": device_id,
        "created_at": datetime.now().isoformat()
    }
    
    # 保存到数据库
    comments_db[comment_id] = comment
    await save_comments_database()
    
    return {
        "succeed": True,
        "message": "留言添加成功",
        "comment": comment
    }

@app.get("/comments")
def get_comments():
    """
    获取所有留言
    """
    # 转换为列表并按创建时间倒序排序
    comments_list = sorted(
        list(comments_db.values()),
        key=lambda x: x["created_at"],
        reverse=True
    )
    
    return {
        "succeed": True,
        "message": "获取留言成功",
        "comments": comments_list
    }

# 管理员密码配置
ADMIN_PASSWORD = "admin"  # 生产环境建议使用环境变量或配置文件

@app.post("/delete_comment")
async def delete_comment(
    comment_id: str = Form(...),
    device_id: str = Form(...),
    admin_password: Optional[str] = Form(None),
    route_admin: Optional[str] = Query(None)
):
    """
    删除留言（支持设备验证和管理员密码验证）
    """
    if comment_id not in comments_db:
        return {"succeed": False, "message": "未找到留言"}
    
    comment = comments_db[comment_id]
    
    # 检查是否为管理员（通过Form参数或路由参数验证密码）
    is_admin = False
    admin_source = None
    
    if admin_password and admin_password == ADMIN_PASSWORD:
        is_admin = True
        admin_source = "form"
    elif route_admin and route_admin == ADMIN_PASSWORD:
        is_admin = True
        admin_source = "route"
    elif admin_password or route_admin:
        # 记录密码错误的尝试
        print(f"[SECURITY] 管理员密码验证失败: {admin_password or route_admin}")
    
    # 如果不是管理员，验证是否为自己设备的留言
    if not is_admin and comment["device_id"] != device_id:
        return {"succeed": False, "message": "只能删除自己设备的留言"}
    
    # 记录管理员操作
    if is_admin:
        print(f"[ADMIN] 管理员删除留言: comment_id={comment_id}, name={comment['name']}, source={admin_source}")
    
    # 删除留言
    del comments_db[comment_id]
    await save_comments_database()
    
    return {
        "succeed": True,
        "message": "留言删除成功"
    }

@app.get("/download")
def download_file(hash: str):
    """
    根据哈希值下载文件
    """
    if hash not in songs_db:
        raise HTTPException(status_code=404, detail="未找到音乐文件。")

    file_path = os.path.join("uploads", songs_db[hash]["name"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="服务器上未找到文件。")

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
        return JSONResponse(content={"succeed": False, "message": "文件类型无效，仅允许上传MIDI文件。"})
    """
    # 检查文件大小
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return JSONResponse(content={"succeed": False, "message": "文件大小超过了1MB的最大限制。"})#, status_code=400)

    # 计算文件哈希
    file_hash = hashlib.md5(file_data).hexdigest()

    # 检查哈希是否已存在
    if file_hash in songs_db:
        #raise HTTPException(status_code=400, detail="A file with the same hash already exists.")
        return JSONResponse(content={"succeed": False, "message": "已存在相同哈希值的文件。"})#, status_code=400)

    # 计算 MIDI 时长
    try:
        midi_file = mido.MidiFile(file=BytesIO(file_data))
        midi_duration = midi_file.length
        duration_ms = int(midi_duration * 1000)  # 转为毫秒
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"处理MIDI文件失败: {str(e)}")

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
            "delete_password": delete_password,
            "upload_time": datetime.now().isoformat()
        },
        **songs_db
    }
    await save_database()

    duration_str = str(timedelta(milliseconds=duration_ms))
    return {
        "succeed": True,
        "message": f"文件 '{file_name}' 上传成功。时长：{duration_str}。",
    }

if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=1200, log_level="debug", log_config=logging_config)

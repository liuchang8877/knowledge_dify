# manage_service.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import sqlite3
import uuid
import aiohttp
import io

app = FastAPI()

# Dify API 配置
DIFY_API_URL = "http://localhost:3000/v1"
DIFY_API_KEY = "your-dify-api-key"

# SQLite 数据库初始化
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        knowledge_id TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# 用户模型
class User(BaseModel):
    username: str
    password: str

# 创建知识库并返回 knowledge_id
async def create_knowledge_base(username: str) -> str:
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "name": f"Knowledge_{username}",
            "description": f"Knowledge base for user {username}"
        }
        async with session.post(f"{DIFY_API_URL}/datasets", json=payload, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail=await resp.text())
            result = await resp.json()
            return result["id"]  # 返回 dataset_id 作为 knowledge_id

# 用户注册并绑定知识库
@app.post("/register")
async def register(user: User):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    user_id = str(uuid.uuid4())

    # 动态创建知识库
    try:
        knowledge_id = await create_knowledge_base(user.username)
    except HTTPException as e:
        conn.close()
        raise e

    # 存储用户信息和 knowledge_id
    try:
        c.execute("INSERT INTO users (user_id, username, password, knowledge_id) VALUES (?, ?, ?, ?)",
                  (user_id, user.username, user.password, knowledge_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()
    
    return {"user_id": user_id, "username": user.username, "knowledge_id": knowledge_id}

# 用户登录
@app.post("/login")
async def login(user: User):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT user_id, knowledge_id FROM users WHERE username = ? AND password = ?",
              (user.username, user.password))
    result = c.fetchone()
    conn.close()
    if result:
        return {"user_id": result[0], "knowledge_id": result[1]}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# 文件上传到知识库（直接调用 Dify API）
@app.post("/upload")
async def upload_file(user_id: str, file: UploadFile = File(...)):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT knowledge_id FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    knowledge_id = result[0]

    # 直接上传文件到 Dify
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}
        form_data = aiohttp.FormData()
        form_data.add_field("dataset_id", knowledge_id)
        form_data.add_field("file", await file.read(), filename=file.filename, content_type=file.content_type)

        async with session.post(f"{DIFY_API_URL}/documents", headers=headers, data=form_data) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail=await resp.text())
            return await resp.json()

# 查询知识库
@app.post("/query")
async def query_knowledge(user_id: str, query: str):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT knowledge_id FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    knowledge_id = result[0]

    # 调用 Dify Workflow API
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "workflow_id": "your-workflow-id-here",
            "inputs": {"query": query, "knowledge_id": knowledge_id},
            "user": "test-user"
        }
        async with session.post(f"{DIFY_API_URL}/workflows/run", json=payload, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail=await resp.text())
            return await resp.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
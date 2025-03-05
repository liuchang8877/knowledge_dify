from fastapi import FastAPI, Depends, HTTPException, status, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Optional, Dict, Any
import sqlite3
import uuid
import os
import requests
from pydantic import BaseModel

# 创建FastAPI应用
app = FastAPI(title="Knowledge Management API")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 使用环境变量或默认值
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 8000))
DB_PATH = os.environ.get('DB_PATH', 'users.db')

# Dify API 配置
DIFY_API_URL = os.environ.get('DIFY_API_URL', "http://api:5001/v1")
DIFY_API_KEY = os.environ.get('DIFY_API_KEY', "dataset-KBWgoCcrXkGwvQSpxmmnhodn")

# 数据模型
class User(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    knowledge_id: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# SQLite 数据库初始化
def init_db():
    print(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        knowledge_id TEXT
    )''')
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

# 确保数据库连接函数使用正确的行工厂
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 创建知识库并返回 knowledge_id
def create_knowledge_base(username):
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "name": f"Knowledge_{username}",
        "description": f"Knowledge base for user {username}"
    }
    try:
        response = requests.post(f"{DIFY_API_URL}/datasets", json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Error creating knowledge base: {response.text}")
            return None
        result = response.json()
        return result["id"]  # 返回 dataset_id 作为 knowledge_id
    except Exception as e:
        print(f"Exception creating knowledge base: {str(e)}")
        return None

# 启动时初始化数据库
@app.on_event("startup")
async def startup_event():
    init_db()

# API路由
@app.get("/")
async def root():
    return {"message": "Knowledge Management API"}

@app.get("/test")
async def test():
    return {"status": "Service is running!"}

@app.post("/register")
async def register(user: User):
    # 生成UUID作为用户ID
    user_id = str(uuid.uuid4())
    
    # 尝试创建知识库
    knowledge_id = create_knowledge_base(user.username)
    if not knowledge_id:
        knowledge_id = "placeholder-knowledge-id"  # 如果创建失败，使用占位符
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (user_id, username, password, knowledge_id) VALUES (?, ?, ?, ?)',
                    (user_id, user.username, user.password, knowledge_id))
        conn.commit()
        return {"message": "User registered successfully", "user_id": user_id}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

@app.post("/login")
async def login(user: User):
    conn = get_db_connection()
    db_user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (user.username, user.password)).fetchone()
    conn.close()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建一个简单的token（在生产环境中应使用更安全的方法）
    token = f"{uuid.uuid4()}"
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": db_user["user_id"],
            "username": db_user["username"],
            "knowledge_id": db_user["knowledge_id"]
        }
    }

@app.get("/users")
async def get_users():
    conn = get_db_connection()
    users = conn.execute('SELECT user_id, username, knowledge_id FROM users').fetchall()
    conn.close()
    
    return [dict(user) for user in users]

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    conn = get_db_connection()
    user = conn.execute('SELECT user_id, username, knowledge_id FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return dict(user)

@app.post("/upload/{knowledge_id}")
async def upload_file(knowledge_id: str, file: bytes = Form(...), filename: str = Form(...)):
    # 保存文件到临时位置
    temp_path = f"/tmp/{filename}"
    with open(temp_path, "wb") as f:
        f.write(file)
    
    # 上传文件到Dify
    try:
        with open(temp_path, 'rb') as f:
            files = {'file': (filename, f)}
            headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}
            response = requests.post(
                f"{DIFY_API_URL}/documents",
                headers=headers,
                data={'dataset_id': knowledge_id},
                files=files
            )
        
        # 删除临时文件
        os.remove(temp_path)
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Error uploading file: {response.text}")
        
        return {"message": "File uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exception uploading file: {str(e)}")

@app.post("/query/{knowledge_id}")
async def query(knowledge_id: str, query_text: str = Form(...), user_id: str = Form(...), username: str = Form(...)):
    # 调用Dify API进行查询
    try:
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "inputs": {"query": query_text},
            "query": query_text,
            "response_mode": "streaming",
            "conversation_id": user_id,
            "user": username
        }
        response = requests.post(f"{DIFY_API_URL}/chat-messages", json=payload, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Error querying: {response.text}")
        
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exception querying: {str(e)}")

@app.get("/debug")
async def debug():
    """调试路由，显示环境信息"""
    # 获取当前工作目录
    cwd = os.getcwd()
    
    # 获取环境变量
    env_vars = dict(os.environ)
    
    # 构建调试信息
    debug_info = {
        "current_working_directory": cwd,
        "environment_variables": env_vars,
        "database_path": DB_PATH,
        "dify_api_url": DIFY_API_URL
    }
    
    return debug_info

if __name__ == "__main__":
    import uvicorn
    print(f"Starting FastAPI server on {HOST}:{PORT}")
    uvicorn.run("api_service:app", host=HOST, port=PORT, reload=True) 
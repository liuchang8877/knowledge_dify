from fastapi import FastAPI, Depends, HTTPException, status, Form, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any, List
import sqlite3
import uuid
import os
import requests
from pydantic import BaseModel
import pathlib

# 创建FastAPI应用
app = FastAPI(title="Knowledge Management API")

# 创建templates目录
templates_dir = pathlib.Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)

# 创建static目录
static_dir = pathlib.Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

# 设置模板
templates = Jinja2Templates(directory=str(templates_dir))

# 添加静态文件支持
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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

# 会话存储
active_sessions = {}

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
        print(f"Creating knowledge base for {username}")
        print(f"DIFY_API_URL: {DIFY_API_URL}")
        print(f"DIFY_API_KEY: {DIFY_API_KEY}")
        print(f"Payload: {payload}")
        
        response = requests.post(f"{DIFY_API_URL}/datasets", json=payload, headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code != 200:
            print(f"Error creating knowledge base: {response.text}")
            return None
        
        result = response.json()
        if "id" not in result:
            print(f"No id in response: {result}")
            return None
            
        print(f"Successfully created knowledge base with ID: {result['id']}")
        return result["id"]  # 返回 dataset_id 作为 knowledge_id
    except Exception as e:
        print(f"Exception creating knowledge base: {str(e)}")
        return None

# 启动时初始化数据库
@app.on_event("startup")
async def startup_event():
    init_db()
    
    # 创建模板文件
    create_template_files()

# 创建模板文件
def create_template_files():
    # 登录页面模板
    login_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>管理员登录</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .login-container {
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                width: 300px;
            }
            h1 {
                text-align: center;
                color: #333;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input[type="text"], input[type="password"] {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
            }
            button {
                width: 100%;
                padding: 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            .error-message {
                color: red;
                text-align: center;
                margin-bottom: 15px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>管理员登录</h1>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
            <form action="/admin/login" method="post">
                <div class="form-group">
                    <label for="username">用户名:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">密码:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">登录</button>
            </form>
        </div>
    </body>
    </html>
    """
    
    # 用户列表页面模板
    users_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>用户管理</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }
            .container {
                width: 80%;
                margin: 0 auto;
                padding: 20px;
            }
            header {
                background-color: #333;
                color: white;
                padding: 10px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            h1 {
                margin: 0;
            }
            .logout-btn {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background-color: white;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            th, td {
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #4CAF50;
                color: white;
            }
            tr:hover {
                background-color: #f5f5f5;
            }
            .add-user-btn {
                display: inline-block;
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                margin: 20px 0;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
            }
            .add-user-form {
                background-color: white;
                padding: 20px;
                margin-top: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input[type="text"], input[type="password"] {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
            }
            .submit-btn {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
            }
            .success-message {
                background-color: #dff0d8;
                color: #3c763d;
                padding: 10px;
                margin-bottom: 20px;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <header>
            <h1>用户管理系统</h1>
            <a href="/admin/logout" class="logout-btn">退出登录</a>
        </header>
        <div class="container">
            {% if message %}
            <div class="success-message">{{ message }}</div>
            {% endif %}
            
            <button id="toggleFormBtn" class="add-user-btn">添加新用户</button>
            
            <div id="addUserForm" class="add-user-form" style="display: none;">
                <h2>添加新用户</h2>
                <form action="/admin/users/add" method="post">
                    <div class="form-group">
                        <label for="new-username">用户名:</label>
                        <input type="text" id="new-username" name="username" required>
                    </div>
                    <div class="form-group">
                        <label for="new-password">密码:</label>
                        <input type="password" id="new-password" name="password" required>
                    </div>
                    <button type="submit" class="submit-btn">添加用户</button>
                </form>
            </div>
            
            <h2>用户列表</h2>
            <table>
                <thead>
                    <tr>
                        <th>用户ID</th>
                        <th>用户名</th>
                        <th>知识库ID</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in users %}
                    <tr>
                        <td>{{ user.user_id }}</td>
                        <td>{{ user.username }}</td>
                        <td>{{ user.knowledge_id }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <script>
            document.getElementById('toggleFormBtn').addEventListener('click', function() {
                var form = document.getElementById('addUserForm');
                if (form.style.display === 'none') {
                    form.style.display = 'block';
                    this.textContent = '取消添加';
                } else {
                    form.style.display = 'none';
                    this.textContent = '添加新用户';
                }
            });
        </script>
    </body>
    </html>
    """
    
    # 写入模板文件
    with open(templates_dir / "login.html", "w") as f:
        f.write(login_template)
    
    with open(templates_dir / "users.html", "w") as f:
        f.write(users_template)

# 验证会话
def verify_session(session_id: str):
    return session_id in active_sessions

# API路由
@app.get("/")
async def root():
    return RedirectResponse(url="/admin/login")

@app.get("/test")
async def test():
    return {"status": "Service is running!"}

# 管理界面路由
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/admin/login")
async def admin_login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (username, password)).fetchone()
    conn.close()
    
    if not user:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "用户名或密码不正确"}
        )
    
    # 创建会话
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "user_id": user["user_id"],
        "username": user["username"]
    }
    
    response = RedirectResponse(url="/admin/users", status_code=303)
    response.set_cookie(key="session_id", value=session_id)
    return response

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, session_id: str = Cookie(None), message: str = None):
    if not verify_session(session_id):
        return RedirectResponse(url="/admin/login")
    
    conn = get_db_connection()
    users = conn.execute('SELECT user_id, username, knowledge_id FROM users').fetchall()
    conn.close()
    
    return templates.TemplateResponse(
        "users.html", 
        {"request": request, "users": users, "message": message}
    )

@app.post("/admin/users/add")
async def admin_add_user(request: Request, username: str = Form(...), password: str = Form(...), session_id: str = Cookie(None)):
    if not verify_session(session_id):
        return RedirectResponse(url="/admin/login")
    
    # 生成UUID作为用户ID
    user_id = str(uuid.uuid4())
    
    # 尝试创建知识库
    knowledge_id = create_knowledge_base(username)
    if not knowledge_id:
        knowledge_id = "placeholder-knowledge-id"  # 如果创建失败，使用占位符
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (user_id, username, password, knowledge_id) VALUES (?, ?, ?, ?)',
                    (user_id, username, password, knowledge_id))
        conn.commit()
        message = "用户添加成功"
    except sqlite3.IntegrityError:
        message = "用户名已存在"
    finally:
        conn.close()
    
    return RedirectResponse(url=f"/admin/users?message={message}", status_code=303)

@app.get("/admin/logout")
async def admin_logout(response: Response, session_id: str = Cookie(None)):
    if session_id in active_sessions:
        del active_sessions[session_id]
    
    response = RedirectResponse(url="/admin/login")
    response.delete_cookie(key="session_id")
    return response

# API路由
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

@app.get("/test-create-kb/{username}")
async def test_create_kb(username: str):
    """测试创建知识库功能"""
    knowledge_id = create_knowledge_base(username)
    return {
        "username": username,
        "knowledge_id": knowledge_id,
        "dify_api_url": DIFY_API_URL,
        "dify_api_key": DIFY_API_KEY[:5] + "..." if DIFY_API_KEY else None
    }

if __name__ == "__main__":
    import uvicorn
    print(f"Starting FastAPI server on {HOST}:{PORT}")
    uvicorn.run("api_service:app", host=HOST, port=PORT, reload=True) 
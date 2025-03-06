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
    # 登录页面模板 - 使用现代简洁风格
    login_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>管理员登录</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Inter', sans-serif;
            }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full space-y-8">
            <div class="text-center">
                <h1 class="text-4xl font-bold text-gray-900 tracking-tight">知识库管理</h1>
                <p class="mt-3 text-lg text-gray-500">登录以管理用户和知识库</p>
            </div>
            
            <div class="bg-white shadow rounded-xl overflow-hidden p-8 space-y-6">
                {% if error %}
                <div class="bg-red-50 border-l-4 border-red-500 p-4 rounded" role="alert">
                    <p class="text-sm text-red-700">{{ error }}</p>
                </div>
                {% endif %}
                
                <form action="/admin/login" method="post" class="space-y-6">
                    <div>
                        <label for="username" class="block text-sm font-medium text-gray-700">用户名</label>
                        <div class="mt-1">
                            <input type="text" id="username" name="username" required
                                class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                        </div>
                    </div>
                    <div>
                        <label for="password" class="block text-sm font-medium text-gray-700">密码</label>
                        <div class="mt-1">
                            <input type="password" id="password" name="password" required
                                class="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                        </div>
                    </div>
                    <div>
                        <button type="submit" 
                            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition duration-150">
                            登录
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 用户列表页面模板 - 使用更简单的方式显示数据
    users_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>用户管理</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Inter', sans-serif;
            }
            .tab-active {
                background-color: #1a1a1a;
                color: white;
            }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen">
        <header class="bg-white shadow-sm">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16">
                    <div class="flex items-center">
                        <h1 class="text-2xl font-bold text-gray-900">知识库管理系统</h1>
                    </div>
                    <div class="flex items-center">
                        <a href="/admin/logout" 
                           class="ml-4 px-4 py-2 text-sm font-medium text-red-600 hover:text-red-800 transition duration-150">
                            退出登录
                        </a>
                    </div>
                </div>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div class="mb-8">
                <h2 class="text-3xl font-bold text-gray-900 mb-6">用户管理</h2>
                <p class="text-lg text-gray-500 mb-8">管理系统用户和他们的知识库</p>
                
                {% if message %}
                <div class="bg-green-50 border-l-4 border-green-500 p-4 rounded mb-6" role="alert">
                    <p class="text-sm text-green-700">{{ message }}</p>
                </div>
                {% endif %}
                
                <!-- 标签导航 -->
                <div class="flex space-x-2 mb-8">
                    <a href="/admin/users" 
                       class="tab-active px-6 py-2 rounded-full text-sm font-medium transition duration-150">
                        用户列表
                    </a>
                    <button onclick="document.getElementById('addUserForm').style.display = 'block';" 
                            class="px-6 py-2 rounded-full text-sm font-medium transition duration-150">
                        添加用户
                    </button>
                </div>
            </div>
            
            <!-- 添加用户表单 -->
            <div id="addUserForm" style="display: none;" 
                 class="bg-white shadow rounded-xl overflow-hidden p-6 mb-8">
                <h3 class="text-lg font-medium text-gray-900 mb-4">添加新用户</h3>
                <form action="/admin/users/add" method="post" class="space-y-4">
                    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                            <label for="new-username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                            <input type="text" id="new-username" name="username" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                        </div>
                        <div>
                            <label for="new-password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                            <input type="password" id="new-password" name="password" required
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                        </div>
                    </div>
                    <div class="flex justify-end">
                        <button type="button" onclick="document.getElementById('addUserForm').style.display = 'none';"
                                class="mr-3 px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-500 transition duration-150">
                            取消
                        </button>
                        <button type="submit" 
                                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition duration-150">
                            添加用户
                        </button>
                    </div>
                </form>
            </div>
            
            <!-- 用户列表 -->
            <div class="bg-white shadow rounded-xl overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    序号
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    用户ID
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    用户名
                                </th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    知识库ID
                                </th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            {% for user in users %}
                            <tr class="hover:bg-gray-50">
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {{ loop.index }}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {{ user.user_id }}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                    {{ user.username }}
                                </td>
                                <td class="px-6 py-4 text-sm text-gray-500">
                                    <div class="max-w-xs truncate" title="{{ user.knowledge_id }}">
                                        {{ user.knowledge_id }}
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                            
                            {% if users|length == 0 %}
                            <tr>
                                <td colspan="4" class="px-6 py-10 text-center text-sm text-gray-500">
                                    没有用户数据
                                </td>
                            </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 如果没有用户，显示添加用户按钮 -->
            {% if users|length == 0 %}
            <div class="text-center mt-6">
                <button onclick="document.getElementById('addUserForm').style.display = 'block';" 
                        class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                    添加第一个用户
                </button>
            </div>
            {% endif %}
        </main>

        <script>
            // 简单的表单显示/隐藏逻辑
            function toggleForm() {
                var form = document.getElementById('addUserForm');
                form.style.display = form.style.display === 'none' ? 'block' : 'none';
            }
            
            // 如果URL中有message参数，自动显示表单
            if (window.location.search.includes('message=')) {
                var urlParams = new URLSearchParams(window.location.search);
                var message = urlParams.get('message');
                if (message && message.includes('用户添加成功')) {
                    document.getElementById('addUserForm').style.display = 'none';
                }
            }
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
    print(f"Admin login attempt for user: {username}")
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (username, password)).fetchone()
    conn.close()
    
    if not user:
        print(f"Admin login failed for user: {username} - Invalid credentials")
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "用户名或密码不正确"}
        )
    
    # 创建会话
    session_id = str(uuid.uuid4())
    knowledge_id = user["knowledge_id"]
    print(f"Admin user {username} logged in successfully with knowledge_id: {knowledge_id}")
    
    active_sessions[session_id] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "knowledge_id": knowledge_id
    }
    
    response = RedirectResponse(url="/admin/users", status_code=303)
    response.set_cookie(key="session_id", value=session_id)
    return response

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, session_id: str = Cookie(None), message: str = None):
    if not verify_session(session_id):
        return RedirectResponse(url="/admin/login")
    
    conn = get_db_connection()
    users_rows = conn.execute('SELECT user_id, username, knowledge_id FROM users').fetchall()
    conn.close()
    
    # 将SQLite Row对象转换为字典列表，确保可以被JSON序列化
    users = [dict(user) for user in users_rows]
    
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
    print(f"Login attempt for user: {user.username}")
    conn = get_db_connection()
    db_user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (user.username, user.password)).fetchone()
    conn.close()
    
    if not db_user:
        print(f"Login failed for user: {user.username} - Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建一个简单的token（在生产环境中应使用更安全的方法）
    token = f"{uuid.uuid4()}"
    
    # 确保knowledge_id存在
    knowledge_id = db_user["knowledge_id"]
    print(f"User {user.username} logged in successfully with knowledge_id: {knowledge_id}")
    
    # 明确返回知识库ID
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": db_user["user_id"],
            "username": db_user["username"],
            "knowledge_id": knowledge_id
        },
        "knowledge_id": knowledge_id  # 额外单独返回知识库ID，使其更明显
    }

@app.post("/test-login")
async def test_login(user: User):
    """测试登录并返回知识库ID的专用端点"""
    print(f"Test login attempt for user: {user.username}")
    conn = get_db_connection()
    db_user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (user.username, user.password)).fetchone()
    conn.close()
    
    if not db_user:
        print(f"Test login failed for user: {user.username} - Invalid credentials")
        return JSONResponse({
            "status": "error",
            "message": "用户名或密码不正确"
        }, status_code=401)
    
    # 确保knowledge_id存在
    knowledge_id = db_user["knowledge_id"]
    print(f"Test login: User {user.username} logged in successfully with knowledge_id: {knowledge_id}")
    
    # 测试知识库是否有效
    try:
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}
        response = requests.get(f"{DIFY_API_URL}/datasets/{knowledge_id}", headers=headers)
        
        kb_status = "valid" if response.status_code == 200 else "invalid"
        kb_info = response.json() if response.status_code == 200 else None
        
        return {
            "status": "success",
            "message": f"登录成功，知识库ID: {knowledge_id}",
            "user_id": db_user["user_id"],
            "username": db_user["username"],
            "knowledge_id": knowledge_id,
            "knowledge_status": kb_status,
            "knowledge_info": kb_info
        }
    except Exception as e:
        return {
            "status": "success",
            "message": f"登录成功，但知识库测试失败: {str(e)}",
            "user_id": db_user["user_id"],
            "username": db_user["username"],
            "knowledge_id": knowledge_id,
            "knowledge_status": "error"
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

@app.get("/admin/test-kb/{knowledge_id}")
async def admin_test_kb(request: Request, knowledge_id: str, session_id: str = Cookie(None)):
    """测试知识库是否有效"""
    if not verify_session(session_id):
        return RedirectResponse(url="/admin/login")
    
    try:
        # 尝试获取知识库信息
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}
        response = requests.get(f"{DIFY_API_URL}/datasets/{knowledge_id}", headers=headers)
        
        if response.status_code == 200:
            kb_info = response.json()
            return JSONResponse({
                "status": "success",
                "message": "知识库有效",
                "knowledge_id": knowledge_id,
                "knowledge_info": kb_info
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": f"知识库无效或不存在: {response.text}",
                "knowledge_id": knowledge_id,
                "status_code": response.status_code
            }, status_code=400)
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": f"测试知识库时发生错误: {str(e)}",
            "knowledge_id": knowledge_id
        }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting FastAPI server on {HOST}:{PORT}")
    uvicorn.run("api_service:app", host=HOST, port=PORT, reload=True) 
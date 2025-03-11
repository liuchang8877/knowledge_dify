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
    # 登录页面模板 - 使用现代简洁风格，添加淡蓝色信件插图
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
            .illustration {
                background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 50%, #7dd3fc 100%);
                position: relative;
                overflow: hidden;
            }
            .letter {
                position: absolute;
                width: 40px;
                height: 30px;
                background-color: rgba(255, 255, 255, 0.9);
                border-radius: 3px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                display: flex;
                align-items: center;
                justify-content: center;
                animation: float 6s ease-in-out infinite;
            }
            .letter:before {
                content: '';
                position: absolute;
                width: 30px;
                height: 1px;
                background-color: rgba(0, 0, 0, 0.1);
                top: 10px;
            }
            .letter:after {
                content: '';
                position: absolute;
                width: 20px;
                height: 1px;
                background-color: rgba(0, 0, 0, 0.1);
                top: 15px;
            }
            .letter svg {
                width: 16px;
                height: 16px;
                color: #0284c7;
                opacity: 0.7;
            }
            .letter:nth-child(1) {
                top: 20%;
                left: 20%;
                transform: scale(0.8) rotate(5deg);
                animation-delay: 0s;
            }
            .letter:nth-child(2) {
                top: 50%;
                left: 50%;
                transform: scale(1.2) rotate(-3deg);
                animation-delay: 1s;
            }
            .letter:nth-child(3) {
                top: 70%;
                left: 30%;
                transform: scale(0.6) rotate(8deg);
                animation-delay: 2s;
            }
            .letter:nth-child(4) {
                top: 30%;
                left: 70%;
                transform: scale(1) rotate(-5deg);
                animation-delay: 3s;
            }
            .letter:nth-child(5) {
                top: 80%;
                left: 60%;
                transform: scale(0.7) rotate(3deg);
                animation-delay: 4s;
            }
            .letter:nth-child(6) {
                top: 40%;
                left: 25%;
                transform: scale(0.9) rotate(-7deg);
                animation-delay: 2.5s;
            }
            .letter:nth-child(7) {
                top: 60%;
                left: 80%;
                transform: scale(0.8) rotate(6deg);
                animation-delay: 1.5s;
            }
            @keyframes float {
                0% {
                    transform: translateY(0) rotate(0deg) scale(1);
                }
                50% {
                    transform: translateY(-20px) rotate(5deg) scale(1.05);
                }
                100% {
                    transform: translateY(0) rotate(0deg) scale(1);
                }
            }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen flex items-center justify-center p-4">
        <div class="max-w-6xl w-full flex rounded-xl shadow-lg overflow-hidden">
            <!-- 左侧淡蓝色信件插图 -->
            <div class="hidden md:block w-1/2 illustration p-12">
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="letter">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div class="relative z-10 h-full flex items-center justify-center">
                    <div class="text-center">
                        <svg class="w-24 h-24 mx-auto text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                        </svg>
                        <h2 class="mt-6 text-3xl font-bold text-white">知识库管理系统</h2>
                        <p class="mt-3 text-white text-opacity-80">集中管理您的知识资源，提升信息检索效率</p>
                    </div>
                </div>
            </div>
            
            <!-- 右侧登录表单 - 黑白风格 -->
            <div class="w-full md:w-1/2 bg-white p-8 md:p-12">
                <div class="max-w-md mx-auto">
                    <div class="text-center md:text-left">
                        <h1 class="text-2xl md:text-3xl font-bold text-gray-900">管理员登录</h1>
                        <p class="mt-2 text-sm md:text-base text-gray-600">请输入您的凭据以访问管理面板</p>
                    </div>
                    
                    {% if error %}
                    <div class="mt-4 bg-red-50 border-l-4 border-red-500 p-4 rounded" role="alert">
                        <div class="flex">
                            <svg class="h-5 w-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <p class="ml-3 text-sm text-red-700">{{ error }}</p>
                        </div>
                    </div>
                    {% endif %}
                    
                    <form action="/admin/login" method="post" class="mt-8 space-y-6">
                        <div>
                            <label for="username" class="block text-sm font-medium text-gray-700">用户名</label>
                            <div class="mt-1 relative rounded-md shadow-sm">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                    </svg>
                                </div>
                                <input type="text" id="username" name="username" required
                                    class="pl-10 appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-gray-500 focus:border-gray-500 sm:text-sm">
                            </div>
                        </div>
                        <div>
                            <label for="password" class="block text-sm font-medium text-gray-700">密码</label>
                            <div class="mt-1 relative rounded-md shadow-sm">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                    </svg>
                                </div>
                                <input type="password" id="password" name="password" required
                                    class="pl-10 appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-gray-500 focus:border-gray-500 sm:text-sm">
                            </div>
                        </div>
                        <div>
                            <button type="submit" 
                                class="group relative w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-black hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500">
                                <span class="absolute left-0 inset-y-0 flex items-center pl-3">
                                    <svg class="h-5 w-5 text-gray-500 group-hover:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                                    </svg>
                                </span>
                                登录
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 用户列表页面模板 - 使用黑白风格
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
                        <svg class="h-8 w-8 text-gray-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <h1 class="ml-2 text-2xl font-bold text-gray-900">知识库管理系统</h1>
                    </div>
                    <div class="flex items-center">
                        <a href="/admin/logout" 
                           class="ml-4 flex items-center px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition duration-150">
                            <svg class="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                            退出登录
                        </a>
                    </div>
                </div>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div class="mb-8">
                <div class="flex items-center">
                    <svg class="h-8 w-8 text-gray-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                    <h2 class="ml-2 text-3xl font-bold text-gray-900">用户管理</h2>
                </div>
                <p class="mt-2 text-lg text-gray-500">管理系统用户和他们的知识库</p>
                
                {% if message %}
                <div class="mt-4 bg-gray-100 border-l-4 border-gray-500 p-4 rounded" role="alert">
                    <div class="flex">
                        <svg class="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <p class="ml-3 text-sm text-gray-700">{{ message }}</p>
                    </div>
                </div>
                {% endif %}
                
                <!-- 标签导航 -->
                <div class="flex space-x-2 mt-6">
                    <a href="/admin/users" 
                       class="tab-active flex items-center px-6 py-2 rounded-full text-sm font-medium transition duration-150">
                        <svg class="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                        </svg>
                        用户列表
                    </a>
                    <button onclick="document.getElementById('addUserForm').style.display = 'block';" 
                            class="flex items-center px-6 py-2 rounded-full text-sm font-medium text-gray-700 hover:bg-gray-200 transition duration-150">
                        <svg class="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                        添加用户
                    </button>
                </div>
            </div>
            
            <!-- 添加用户表单 -->
            <div id="addUserForm" style="display: none;" 
                 class="bg-white shadow rounded-xl overflow-hidden p-6 mb-8">
                <div class="flex items-center mb-4">
                    <svg class="h-6 w-6 text-gray-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                    </svg>
                    <h3 class="ml-2 text-lg font-medium text-gray-900">添加新用户</h3>
                </div>
                <form action="/admin/users/add" method="post" class="space-y-4">
                    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                            <label for="new-username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                            <div class="relative rounded-md shadow-sm">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                    </svg>
                                </div>
                                <input type="text" id="new-username" name="username" required
                                       class="pl-10 w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-gray-500 focus:border-gray-500">
                            </div>
                        </div>
                        <div>
                            <label for="new-password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                            <div class="relative rounded-md shadow-sm">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                    </svg>
                                </div>
                                <input type="password" id="new-password" name="password" required
                                       class="pl-10 w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-gray-500 focus:border-gray-500">
                            </div>
                        </div>
                    </div>
                    <div class="flex justify-end">
                        <button type="button" onclick="document.getElementById('addUserForm').style.display = 'none';"
                                class="mr-3 flex items-center px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-500 transition duration-150">
                            <svg class="mr-2 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            取消
                        </button>
                        <button type="submit" 
                                class="flex items-center px-4 py-2 text-sm font-medium text-white bg-black hover:bg-gray-800 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition duration-150">
                            <svg class="mr-2 h-5 w-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
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
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="flex items-center">
                                        <div class="flex-shrink-0 h-8 w-8 bg-gray-200 rounded-full flex items-center justify-center">
                                            <span class="text-gray-800 font-medium">{{ user.username[0] | upper }}</span>
                                        </div>
                                        <div class="ml-3">
                                            <div class="text-sm font-medium text-gray-900">{{ user.username }}</div>
                                        </div>
                                    </div>
                                </td>
                                <td class="px-6 py-4 text-sm text-gray-500">
                                    <div class="flex items-center">
                                        <svg class="h-4 w-4 text-gray-400 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                        <div class="max-w-xs truncate" title="{{ user.knowledge_id }}">
                                            {{ user.knowledge_id }}
                                        </div>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                            
                            {% if users|length == 0 %}
                            <tr>
                                <td colspan="4" class="px-6 py-10 text-center text-sm text-gray-500">
                                    <div class="flex flex-col items-center">
                                        <svg class="h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                                        </svg>
                                        <p class="mt-2">没有用户数据</p>
                                    </div>
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
                        class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-black hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500">
                    <svg class="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
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

# 添加一个新的路由，处理 /admin 根路径
@app.get("/admin")
async def admin_root():
    return RedirectResponse(url="/admin/login")

if __name__ == "__main__":
    import uvicorn
    print(f"Starting FastAPI server on {HOST}:{PORT}")
    uvicorn.run("api_service:app", host=HOST, port=PORT, reload=True) 
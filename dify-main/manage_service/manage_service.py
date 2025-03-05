# manage_service.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file
import sqlite3
import uuid
import os
import io
import requests
from werkzeug.utils import secure_filename
import traceback

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_session')

# 使用环境变量或默认值
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 8000))
DB_PATH = os.environ.get('DB_PATH', 'users.db')  # 修改为直接使用根目录下的users.db

# Dify API 配置
DIFY_API_URL = os.environ.get('DIFY_API_URL', "http://api:5001/v1")
DIFY_API_KEY = os.environ.get('DIFY_API_KEY', "dataset-KBWgoCcrXkGwvQSpxmmnhodn")

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

@app.route('/')
def index():
    print("Rendering index page")
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering index page: {str(e)}")
        traceback.print_exc()
        return f"Error rendering index page: {str(e)}", 500

@app.route('/debug')
def debug():
    """调试路由，显示环境信息和模板路径"""
    template_folder = app.template_folder
    static_folder = app.static_folder
    
    # 列出模板目录中的文件
    template_files = []
    if os.path.exists(template_folder):
        template_files = os.listdir(template_folder)
    
    # 获取当前工作目录
    cwd = os.getcwd()
    
    # 获取环境变量
    env_vars = dict(os.environ)
    
    # 构建调试信息
    debug_info = {
        "app_name": app.name,
        "template_folder": template_folder,
        "static_folder": static_folder,
        "template_files": template_files,
        "current_working_directory": cwd,
        "environment_variables": env_vars,
        "routes": [str(rule) for rule in app.url_map.iter_rules()]
    }
    
    return jsonify(debug_info)

@app.route('/simple')
def simple():
    """简单的HTML响应，不使用模板"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simple Page</title>
    </head>
    <body>
        <h1>Simple HTML Page</h1>
        <p>This page is rendered without using templates.</p>
        <a href="/debug">View Debug Info</a>
    </body>
    </html>
    """
    return html

@app.route('/register', methods=['GET', 'POST'])
def register():
    print(f"Register route called with method: {request.method}")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
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
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "用户名已存在", 400
        finally:
            conn.close()
    
    try:
        return render_template('register.html')
    except Exception as e:
        print(f"Error rendering register page: {str(e)}")
        traceback.print_exc()
        return f"Error rendering register page: {str(e)}", 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    print(f"Login route called with method: {request.method}")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                          (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['knowledge_id'] = user['knowledge_id']
            return redirect(url_for('dashboard'))
        
        return "用户名或密码错误", 401
    
    try:
        return render_template('login.html')
    except Exception as e:
        print(f"Error rendering login page: {str(e)}")
        traceback.print_exc()
        return f"Error rendering login page: {str(e)}", 500

@app.route('/dashboard')
def dashboard():
    print("Dashboard route called")
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        return render_template('dashboard.html', username=session.get('username'))
    except Exception as e:
        print(f"Error rendering dashboard page: {str(e)}")
        traceback.print_exc()
        return f"Error rendering dashboard page: {str(e)}", 500

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    
    return jsonify([dict(user) for user in users])

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    
    knowledge_id = session.get('knowledge_id')
    if not knowledge_id:
        return "No knowledge ID found", 400
    
    # 保存文件到临时位置
    filename = secure_filename(file.filename)
    temp_path = os.path.join('/tmp', filename)
    file.save(temp_path)
    
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
            return f"Error uploading file: {response.text}", 400
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Exception uploading file: {str(e)}", 500

@app.route('/query', methods=['POST'])
def query():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    query_text = request.form.get('query')
    if not query_text:
        return "No query provided", 400
    
    knowledge_id = session.get('knowledge_id')
    if not knowledge_id:
        return "No knowledge ID found", 400
    
    # 调用Dify API进行查询
    try:
        headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "inputs": {"query": query_text},
            "query": query_text,
            "response_mode": "streaming",
            "conversation_id": session.get('user_id'),
            "user": session.get('username')
        }
        response = requests.post(f"{DIFY_API_URL}/chat-messages", json=payload, headers=headers)
        
        if response.status_code != 200:
            return f"Error querying: {response.text}", 400
        
        result = response.json()
        return jsonify(result)
    except Exception as e:
        return f"Exception querying: {str(e)}", 500

@app.route('/test')
def test():
    return "Service is running!"

if __name__ == "__main__":
    # 初始化数据库
    init_db()
    print(f"Starting server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
#!/usr/bin/env python3
"""Hazel 状态面板服务器 - 支持知识库搜索 + 密码保护"""
import http.server
import json
import sqlite3
import os
import urllib.parse
import sys
import hashlib
import secrets
import http.cookies

PORT = 3456
KB_DB = "/Users/rickywang/.openclaw/workspace/knowledge/knowledge.db"

# 密码配置 - Ricky 可以改这个
PASSWORD = "hazel2026"

# 会话管理
valid_sessions = {}

def check_auth(handler):
    """检查是否已登录"""
    cookie_header = handler.headers.get('Cookie', '')
    if cookie_header:
        cookies = http.cookies.SimpleCookie(cookie_header)
        if 'session' in cookies:
            token = cookies['session'].value
            if token in valid_sessions:
                return True
    return False

def create_session():
    """创建新会话"""
    token = secrets.token_hex(32)
    valid_sessions[token] = True
    return token

LOGIN_PAGE = '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hazel Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a1a; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.login-box { background: #12122a; border: 1px solid #2a2a4a; border-radius: 16px; padding: 40px; width: 340px; text-align: center; }
.login-box h1 { font-size: 24px; margin-bottom: 8px; color: #fff; }
.login-box p { font-size: 14px; color: #888; margin-bottom: 24px; }
input[type="password"] { width: 100%; padding: 12px 16px; background: #1a1a3a; border: 1px solid #3a3a5a; border-radius: 8px; color: #fff; font-size: 16px; outline: none; margin-bottom: 16px; }
input[type="password"]:focus { border-color: #6366f1; }
button { width: 100%; padding: 12px; background: #6366f1; border: none; border-radius: 8px; color: #fff; font-size: 16px; cursor: pointer; }
button:hover { background: #5558e6; }
.error { color: #ef4444; font-size: 13px; margin-bottom: 12px; display: none; }
</style>
</head>
<body>
<div class="login-box">
<h1>Hazel Dashboard</h1>
<p>Enter password to continue</p>
<div class="error" id="err">Password incorrect</div>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Password" autofocus>
<button type="submit">Enter</button>
</form>
</div>
</body>
</html>'''

LOGIN_PAGE_ERROR = LOGIN_PAGE.replace('display: none', 'display: block')

# 加载嵌入模型（懒加载）
model = None
def get_model():
    global model
    if model is None:
        sys.path.insert(0, "/Users/rickywang/.openclaw/workspace")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

def search_kb(query, limit=5):
    """语义搜索知识库"""
    conn = sqlite3.connect(KB_DB)
    rows = conn.execute(
        "SELECT id, type, title, content, source_url FROM entries WHERE title LIKE ? OR content LIKE ? ORDER BY importance DESC LIMIT ?",
        (f'%{query}%', f'%{query}%', limit)
    ).fetchall()
    results = []
    for row in rows:
        results.append({
            "id": row[0], "type": row[1], "title": row[2],
            "content": row[3][:200], "url": row[4]
        })
    if len(results) < limit:
        try:
            import numpy as np
            m = get_model()
            q_emb = m.encode([query])[0]
            all_rows = conn.execute(
                "SELECT id, type, title, content, url, embedding FROM entries WHERE embedding IS NOT NULL"
            ).fetchall()
            scored = []
            for r in all_rows:
                if r[5]:
                    emb = np.frombuffer(r[5], dtype=np.float32)
                    score = float(np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb)))
                    scored.append((score, r))
            scored.sort(key=lambda x: -x[0])
            seen_ids = {r["id"] for r in results}
            for score, r in scored[:limit]:
                if r[0] not in seen_ids and score > 0.3:
                    results.append({
                        "id": r[0], "type": r[1], "title": r[2],
                        "content": r[3][:200], "url": r[4], "score": round(score, 3)
                    })
        except Exception:
            pass
    conn.close()
    return results[:limit]

class HazelHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        # API 不需要登录验证（内部调用）
        if parsed.path == '/api/kb-search':
            self.handle_search(parsed)
            return
        
        # 其他页面需要登录
        if not check_auth(self):
            self.send_login_page()
            return
        
        super().do_GET()
    
    def do_POST(self):
        if self.path == '/login':
            self.handle_login()
            return
        self.send_error(404)
    
    def handle_login(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(body)
        password = params.get('password', [''])[0]
        
        if password == PASSWORD:
            token = create_session()
            self.send_response(302)
            self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800')
            self.send_header('Location', '/')
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(LOGIN_PAGE_ERROR.encode('utf-8'))
    
    def send_login_page(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(LOGIN_PAGE.encode('utf-8'))

    def handle_search(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        query = params.get('q', [''])[0].strip()
        if not query:
            self.send_json({"error": "请输入搜索词"}, 400)
            return
        try:
            results = search_kb(query)
            self.send_json({"results": results})
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def send_json(self, obj, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        pass

os.chdir("/Users/rickywang/Projects/hazel-demo")
print(f"Hazel 状态面板运行在 http://localhost:{PORT}")
http.server.HTTPServer(('0.0.0.0', PORT), HazelHandler).serve_forever()

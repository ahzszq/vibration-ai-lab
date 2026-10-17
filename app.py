import base64
import hmac
import os
import time
from urllib.parse import urlparse
import json
import threading
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from engine import simulate, train_and_recommend, REQUEST_DEADLINE
from ai_workflow import parse_document, make_plan, execute_plan, execute_sweep, explain, completion, chat_turn
from physics import DEFAULTS
from engine import REQUEST_PROGRESS
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()
PROGRESS = {}
PROGRESS_TTL = 600

class AppServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

class Handler(BaseHTTPRequestHandler):
    timeout = 30

    def allowed_request(self):
        public = os.getenv('APP_PUBLIC', '0') == '1'
        origins = {x.strip().rstrip('/') for x in os.getenv('APP_ALLOWED_ORIGINS', '').split(',') if x.strip()}
        if not public:
            origins |= {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in {urlparse(x).netloc for x in origins}:
            self.reply(403, {'error': '访问地址未配置，请检查APP_ALLOWED_ORIGINS'})
            return False
        if self.headers.get('Origin') not in (None, *origins) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.reply(403, {'error': '来源地址不允许'})
            return False
        if public:
            try:
                scheme, value = self.headers.get('Authorization', '').split(' ', 1)
                user, password = base64.b64decode(value, validate=True).decode('utf-8').split(':', 1)
                expected = os.getenv('APP_DEMO_PASSWORD', '')
                valid = scheme.lower() == 'basic' and user == 'demo' and bool(expected) and hmac.compare_digest(password.encode(), expected.encode())
            except (ValueError, UnicodeError):
                valid = False
            if not valid:
                self.reply(401, {'error': '请输入评审访问账号与密码'}, authenticate=True)
                return False
        return True

    def security_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

    def do_GET(self):
        if self.path == '/healthz':
            self.reply(200, {'ok': True})
            return
        if not self.allowed_request():
            return
        if self.path.startswith('/api/progress?'):
            job = parse_qs(urlparse(self.path).query).get('id', [''])[0]
            self.reply(200, PROGRESS.get(job, {'stage': 'waiting'}))
            return
        if self.path not in ('/', '/index.html', '/assistant.js', '/main.js', '/analysis.js', '/styles.css', '/defaults.js'):
            self.send_error(404)
            return
        content = ('const defaults = ' + json.dumps(DEFAULTS) + ';').encode('utf-8') if self.path == '/defaults.js' else (ROOT / ('index.html' if self.path == '/' else self.path.lstrip('/'))).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ('application/javascript' if self.path.endswith('.js') else 'text/css' if self.path.endswith('.css') else 'text/html') + '; charset=utf-8')
        self.security_headers()
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if not self.allowed_request():
            return
        if self.path not in ('/api/simulate', '/api/learn', '/api/document', '/api/plan', '/api/execute', '/api/sweep', '/api/explain', '/api/test', '/api/chat'):
            self.send_error(404)
            return
        if not LOCK.acquire(timeout=3):
            self.reply(409, {'error': '已有任务运行中，已等待3秒，请稍后重试'})
            return
        token = REQUEST_DEADLINE.set(time.monotonic() + float(os.getenv('APP_TASK_TIMEOUT', '180')))
        job = self.headers.get('X-Job-Id', '')[:80]
        def update_progress(value):
            if job:
                PROGRESS[job] = dict(value, updated=time.time())
        now = time.time()
        for key, value in list(PROGRESS.items()):
            if now - value.get('updated', now) > PROGRESS_TTL:
                PROGRESS.pop(key, None)
        update_progress({'stage': 'preparing'})
        progress_token = REQUEST_PROGRESS.set(update_progress)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 15 * 1024 * 1024:
                raise ValueError('请求大小无效')
            params = json.loads(self.rfile.read(length))
            if not isinstance(params, dict):
                raise ValueError('参数格式无效')
            if self.path == '/api/simulate':
                result = simulate(params)
            elif self.path == '/api/learn':
                result = train_and_recommend(params)
            elif self.path == '/api/document':
                result = parse_document(params)
            elif self.path == '/api/plan':
                result = make_plan(params)
            elif self.path == '/api/execute':
                result = execute_plan(params)
            elif self.path == '/api/sweep':
                result = execute_sweep(params)
            elif self.path == '/api/explain':
                result = explain(params)
            elif self.path == '/api/chat':
                result = chat_turn(params)
            else:
                completion(params.get('config', {}), [dict(role='user', content='Reply OK only.')])
                result = dict(ok=True, message='模型实际调用成功（会产生少量API用量）')
            self.reply(200, result)
        except (ValueError, TypeError, OverflowError, KeyError) as exc:
            from pydantic import ValidationError
            message = '模型或输入结构校验失败，请检查参数与输出格式' if isinstance(exc, ValidationError) else str(exc)
            if os.getenv('APP_PUBLIC', '0') == '1':
                message = '输入或任务校验失败，请检查参数、模型配置、来源引文和计算规模。'
            self.reply(400, {'error': message})
        except Exception:
            self.reply(500, {'error': '任务失败，请查看终端并检查参数'})
        finally:
            update_progress({'stage': 'finished'})
            REQUEST_PROGRESS.reset(progress_token)
            REQUEST_DEADLINE.reset(token)
            LOCK.release()

    def reply(self, status, obj, authenticate=False):
        data = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        if authenticate:
            self.send_header('WWW-Authenticate', 'Basic realm="Vibration AI Demo", charset="UTF-8"')
        self.security_headers()
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        # Request payloads and provider exceptions are intentionally excluded from logs.
        pass

def main():
    public = os.getenv('APP_PUBLIC', '0') == '1'
    if public:
        if len(os.getenv('APP_DEMO_PASSWORD', '')) < 16:
            raise SystemExit('公开演示请设置至少16字符的APP_DEMO_PASSWORD')
        origins = os.getenv('APP_ALLOWED_ORIGINS', '').split(',')
        if not all(x.startswith('https://') and urlparse(x).netloc for x in origins):
            raise SystemExit('公开演示请设置HTTPS格式的APP_ALLOWED_ORIGINS')
    host, port = os.getenv('APP_HOST', '127.0.0.1'), int(os.getenv('PORT', '8765'))
    try:
        server = AppServer((host, port), Handler)
    except OSError as exc:
        if public or exc.errno not in (13, 48, 98, 10013, 10048):
            raise
        # A previous local instance must not make the browser show stale code.
        server = AppServer((host, 0), Handler)
        print(f'端口 {port} 已被占用，已为本次程序选择空闲端口。', flush=True)
    port = server.server_port
    server.daemon_threads = True
    print(f'振动AI实验助手已启动，端口 {port}；按 Ctrl+C 退出。', flush=True)
    if not public:
        print(f'本次访问地址：http://127.0.0.1:{port}', flush=True)
    if not public and os.getenv('APP_NO_BROWSER', '0') != '1':
        webbrowser.open(f'http://127.0.0.1:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()

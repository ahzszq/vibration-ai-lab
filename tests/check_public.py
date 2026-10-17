import base64,json,os,sys,threading,time,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Handler
from engine import simulate,REQUEST_DEADLINE
from ai_workflow import connection
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
password='TEST_DEMO_PASSWORD_123456'
os.environ.update(APP_PUBLIC='1',APP_ALLOWED_ORIGINS='https://judge.example',APP_DEMO_PASSWORD=password)
auth='Basic '+base64.b64encode(('demo:'+password).encode()).decode()
def request(path,headers=None,data=None):
 h={'Host':'judge.example',**(headers or {})}
 req=urllib.request.Request(url+path,headers=h,data=None if data is None else json.dumps(data).encode())
 try:
  with urllib.request.urlopen(req) as r:return r.status,r.read(),r.headers
 except urllib.error.HTTPError as r:return r.code,r.read(),r.headers
assert request('/')[0]==401
assert request('/',{'Authorization':auth})[0]==200
assert request('/',{'Authorization':auth,'Host':'evil.example'})[0]==403
assert request('/api/simulate',{'Authorization':auth,'Origin':'https://evil.example'},data={})[0]==403
code,body,headers=request('/api/simulate',{'Authorization':auth,'Origin':'https://judge.example'},data={'NT_total':10,'NT_start':6,'NN':32})
assert code==200 and json.loads(body)['stats']['points']==128
assert headers['X-Frame-Options']=='DENY' and password.encode() not in body
for base in ('http://127.0.0.1:11434/v1','https://169.254.169.254/v1','https://api.deepseek.com:444/v1'):
 try:connection({'model':'openai/test','api_key':'test','base_url':base})
 except ValueError:pass
 else:raise AssertionError('危险地址未拦截')
assert connection({'model':'deepseek/deepseek-chat','api_key':'test','base_url':'https://api.deepseek.com'})
token=REQUEST_DEADLINE.set(time.monotonic()-1)
try:
 try:simulate({'NT_total':10,'NT_start':6,'NN':32})
 except ValueError:pass
 else:raise AssertionError('计算超时未生效')
finally:REQUEST_DEADLINE.reset(token)
server.shutdown()
print('PASS: public authentication, origin/host rejection, real simulation, provider allowlist, CPU timeout')

import sys,json,threading,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ai_workflow as w
from app import Handler
base=dict(w.DEFAULTS,NT_total=10,NT_start=6,NN=32)
raw={'patch':{'Epsilon33':0.04},'sweep':None,'reply':'已调整'}
class Mock(BaseHTTPRequestHandler):
 def do_POST(self):
  request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  assert 'latest_results' in request['messages'][-1]['content']
  data=json.dumps({'choices':[{'message':{'content':json.dumps(raw)}}]}).encode()
  self.send_response(200);self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass
mock=ThreadingHTTPServer(('127.0.0.1',0),Mock)
threading.Thread(target=mock.serve_forever,daemon=True).start()
config=dict(model='openai/mock',api_key='TEST_NOT_A_REAL_KEY',base_url=f'http://127.0.0.1:{mock.server_port}/v1')
payload=dict(base=base,config=config,message='将Epsilon33改为0.04',history=[dict(role='user',content='上一个问题')])
assert w.chat_turn(payload)['action']['patch']['Epsilon33']==.04
for invalid in ({'NT_total':12},{'Epsilon33':-1},{'unknown':1}):
 raw['patch']=invalid
 try:w.chat_turn(payload)
 except ValueError:pass
 else:raise AssertionError('非法参数未拒绝')
raw.update(patch={},sweep={'param':'Epsilon33','from':.02,'to':.08,'n':6})
s=w.chat_turn(payload)
assert s['action']['sweep']['from']==.02
r=w.execute_sweep(dict(base=base,sweep=s['action']['sweep']))
assert len(r['runs'])==6 and all(x['result']['stats']['points']==128 for x in r['runs'])
for change in ({'n':6.5},{'param':'NN'},{'from':-1}):
 try:w.execute_sweep(dict(base=base,sweep=dict(raw['sweep'],**change)))
 except ValueError:pass
 else:raise AssertionError('非法扫频未拒绝')
try:w.execute_sweep(dict(base=w.DEFAULTS,sweep=raw['sweep']))
except ValueError:pass
else:raise AssertionError('大计算量未拒绝')
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
raw.update(patch={'Epsilon33':.04},sweep=None)
req=urllib.request.Request(url+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
response=json.load(urllib.request.urlopen(req))
assert response['action']['patch']['Epsilon33']==.04
assert 'TEST_NOT_A_REAL_KEY' not in json.dumps(response)
server.shutdown();mock.shutdown()
print('PASS: mock兼容接口、HTTP聊天路由、参数拒绝、6点真实扫频、规模限制、密钥不回传')

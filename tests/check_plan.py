import sys,json,base64,threading,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_workflow import *
from reportlab.pdfgen import canvas
pdf=io.BytesIO(); c=canvas.Canvas(pdf); c.drawString(72,740,'Epsilon33=0.04; Omegaeh=1.0; Fah=0.05');c.save()
doc=parse_document(dict(name='sample.pdf',data=base64.b64encode(pdf.getvalue()).decode()))
assert 'Epsilon33=0.04' in doc['sources'][0]['text']
raw=dict(status='ready',summary='比较阻尼，其余继承当前配置',questions=[],warnings=[],cases=[dict(name=f'damping {n}',changes={'Epsilon33':n},evidence=[dict(parameter='Epsilon33',value=n,source='user',quote=f'Epsilon33={n}')]) for n in [.02,.04,.06]])
class Mock(BaseHTTPRequestHandler):
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  assert self.path=='/v1/chat/completions'
  text=json.dumps(raw,ensure_ascii=False) if 'schema' in body['messages'][-1]['content'] else 'OK'
  out=json.dumps({'choices':[{'message':{'content':text}}]}).encode()
  self.send_response(200);self.end_headers();self.wfile.write(out)
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Mock);threading.Thread(target=server.serve_forever,daemon=True).start()
config=dict(model='openai/mock',api_key='TEST_ONLY_NOT_REAL',base_url=f'http://127.0.0.1:{server.server_port}/v1')
payload=dict(config=config,message='比较 Epsilon33=0.02 Epsilon33=0.04 Epsilon33=0.06',base=dict(NT_total=100,NT_start=60,NN=96),sources=doc['sources'])
plan=make_plan(payload)
experiment=execute_plan(plan)
assert len(experiment['runs'])==3
assert 'TEST_ONLY' not in json.dumps(experiment)
try:
 bad=json.loads(json.dumps(raw));bad['cases'][0]['evidence'][0]['quote']='invented quotation';validate_plan(bad,{},source_map(payload))
 raise AssertionError('fabricated source accepted')
except ValueError:pass
try:
 bad=json.loads(json.dumps(raw));bad['cases'][0]['changes']={'unknown':1};validate_plan(bad,{})
 raise AssertionError('unknown param accepted')
except ValueError:pass
try:connection(dict(model='openai/x',api_key='x',base_url='http://remote.example/v1'));raise AssertionError('insecure remote')
except ValueError:pass
from app import Handler
appserver=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=appserver.serve_forever,daemon=True).start()
for route,data in [('document',dict(name='sample.pdf',data=base64.b64encode(pdf.getvalue()).decode())),('plan',payload),('execute',plan),('test',dict(config=config))]:
 request=urllib.request.Request(f'http://127.0.0.1:{appserver.server_port}/api/{route}',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request) as r:assert r.status==200
print('PASS: PDF extraction, mocked compatible model HTTP call, 3-case planning and real simulation, source validation, parameter rejection, no key in report, 4 application HTTP routes')
server.shutdown();appserver.shutdown()

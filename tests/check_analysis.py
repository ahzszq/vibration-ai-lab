import sys,threading,json,time,urllib.request
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import simulate,REQUEST_PROGRESS
from app import Handler
from physics import Solver
from http.server import ThreadingHTTPServer
updates=[];token=REQUEST_PROGRESS.set(updates.append)
try:r=simulate(dict(NT_total=100,NT_start=60,NN=96))
finally:REQUEST_PROGRESS.reset(token)
assert len(r['states'][0])==7 and len(r['state_tail'])==768
assert updates[0]['stage']=='integrating' and updates[-1]['stage']=='analysis'
assert sum(v[1] for v in r['analysis']['histogram'])==r['stats']['points']
assert len(r['analysis']['rms_windows'])==24
for row in r['state_tail'][::100]:
 assert Solver().F(row[1:],row[0],r['params'])[4]==row[6]
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
for asset,kind in [('analysis.js','javascript'),('styles.css','css')]:
 with urllib.request.urlopen(base+'/'+asset) as response:assert kind in response.headers['Content-Type']
req=urllib.request.Request(base+'/api/simulate',data=json.dumps(dict(NT_total=100,NT_start=60,NN=96)).encode(),headers={'X-Job-Id':'test-progress','Content-Type':'application/json'})
json.load(urllib.request.urlopen(req))
assert json.load(urllib.request.urlopen(base+'/api/progress?id=test-progress'))['stage']=='finished'
server.shutdown()
print('PASS: six-state samples, continuous tail, full-data statistics, solver relation, progress callbacks and HTTP polling')

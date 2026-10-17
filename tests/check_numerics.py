"""Compare to supplied source and independent analytic solutions; no physical calibration claim."""
import json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physics import DEFAULTS, Solver
from engine import simulate
from reference_original import OriginalSolver, DEFAULTS as ORIGINAL_DEFAULTS

assert DEFAULTS == ORIGINAL_DEFAULTS
cases=[]
for change in ({}, {'Fah': .08, 'Epsilon33': .04, 'Fat': .02, 'Omegaet': .8}):
    p=dict(DEFAULTS, NT_total=40, NT_start=20, NN=128, **change)
    result=simulate(p)
    solver=OriginalSolver(); y=[0.]*6; rows=[]
    dt=2*math.pi/p['Omegaeh']/p['NN']
    for step in range(p['NT_total']*p['NN']):
        y=solver.RK4(y,step*dt,dt,p)
        if step>=p['NT_start']*p['NN']:
            rows.append([(step+1)*dt,*y])
    rows=np.asarray(rows)
    sample=rows[::result['sampling']['chart_stride']]
    error=float(np.max(np.abs(sample-np.asarray(result['states']))))
    assert error<1e-12
    assert np.allclose(rows[-len(result['state_tail']):],result['state_tail'],atol=1e-12,rtol=0)
    assert abs(result['series'][0][0]-(p['NT_start']*p['NN']+1)*dt)<1e-12
    assert abs(result['stats']['rms']-np.sqrt(np.mean(rows[:,5]**2)))<1e-12
    assert np.allclose(result['poincare'],rows[p['NN']-1::p['NN'],5:7],atol=1e-12,rtol=0)
    cases.append(dict(changes=change,max_state_error=error,rms=result['stats']['rms'],points=len(rows)))

class Oscillator(Solver):
    def F(self,y,t,p):
        return [y[1],-y[0],y[3],-y[2],y[5],-y[4]]
errors=[]
for n in (32,64,128):
    s=Oscillator(); y=[1.,0.,1.,0.,1.,0.]; dt=1/n
    for i in range(n): y=s.RK4(y,i*dt,dt,{})
    errors.append(float(np.max(np.abs(np.asarray(y)-np.tile([math.cos(1),-math.sin(1)],3)))))
assert errors[0]/errors[1]>14 and errors[1]/errors[2]>14

# Short-window mesh refinement of the actual nonsmooth model, same endpoint.
endpoints=[]
for n in (128,256,512,1024):
    s=Solver(); y=[0.]*6; dt=2*math.pi/n
    for i in range(2*n): y=s.RK4(y,i*dt,dt,DEFAULTS)
    endpoints.append(y.copy())
ref=np.array(endpoints[-1]); mesh=[float(np.max(np.abs(np.array(v)-ref))) for v in endpoints[:-1]]
assert mesh[-1]<mesh[0]
report=dict(reference_cases=cases,analytic_oscillator_errors=errors,short_window_mesh=dict(cycles=2,steps_per_period=[128,256,512],reference_steps_per_period=1024,max_endpoint_errors=mesh),time_axis='RK step endpoint; original GUI labels the same state one dt earlier',limits='Agreement validates code transfer and short-window integration only. No proof of long-time convergence, physical validity or engineering accuracy.')
target=Path(__file__).resolve().parents[1]/'参赛材料/数值核验记录.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: original defaults, two pointwise state comparisons, timestamps, RMS, phase tail, Poincare, analytic RK4 order and short-window refinement')

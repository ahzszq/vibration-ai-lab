"""Interactive real-provider acceptance. Key stays in process memory; no raw model text saved."""
import datetime, getpass, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_workflow import completion, chat_turn, make_plan, execute_plan
from physics import DEFAULTS

print('真实AI验收：将向你选择的服务商发送测试文本、参数和少量统计量，会产生API用量。')
config=dict(base_url=input('API地址（例 https://api.deepseek.com/v1）：').strip(),
            model=input('模型ID（例 openai/deepseek-chat）：').strip(),
            api_key=getpass.getpass('API密钥（隐藏输入，不保存）：'))
base=dict(DEFAULTS,NT_total=40,NT_start=20,NN=128)
checks=[]
def check(name,fn):
    try:
        fn(); checks.append(dict(name=name,passed=True))
        print('PASS:',name)
    except Exception as exc:
        # Even upstream validation messages may contain generated text: do not persist them.
        checks.append(dict(name=name,passed=False,error_type=type(exc).__name__))
        print('FAIL:',name,'请在网页核对配置或重试。')
def connect():
    assert completion(config,[dict(role='user',content='Reply OK only.')]).strip()
def patch():
    r=chat_turn(dict(base=base,config=config,message='将 Epsilon33 改为0.04，其他不变',history=[]))
    assert r['action']['patch']=={'Epsilon33':.04}
def history():
    r=chat_turn(dict(base=base,config=config,message='把刚才那个参数翻倍',history=[dict(role='user',content='接下来讨论 Epsilon33，当前值0.02。'),dict(role='assistant',content='好的，当前讨论Epsilon33。')]))
    assert r['action']['patch']=={'Epsilon33':.04}
def document():
    p=make_plan(dict(base=base,config=config,message='按文档给出的 Epsilon33 做单组仿真，其他参数继承当前值。',sources=[dict(id='page:1',text='Experiment parameter: Epsilon33=0.04.')]))
    assert len(p['plan']['cases'])==1
    assert p['plan']['cases'][0]['changes']=={'Epsilon33':.04}
    r=execute_plan(p)
    assert len(r['runs'])==1 and r['runs'][0]['result']['stats']['points']==2560
for name,fn in [('服务连接',connect),('中文明确改参',patch),('多轮指代改参',history),('文档引文解析并真实求解',document)]:
    check(name,fn)
report=dict(date=datetime.datetime.now().astimezone().isoformat(),model=config['model'],checks=checks,
            scope='4个固定验收样例，仅为小样本功能测试，不代表通用语义准确率。密钥与原始响应均不保存。')
config['api_key']=''
out=Path(__file__).resolve().parents[1]/'参赛材料/真实AI验收结果.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('已保存：',out)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)

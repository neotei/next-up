from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import training
rows=[]
for i in range(8):
    rows.append({'id':i,'key':str(i),'modKey':'[]','stars':3+i*.1,'ar':8.5,'accuracy':96+i*.1,'priority':8-i,'focus':'Tapping demand','stage':'Control','support':5,'provisional':False,'length':90})
plan=training.session(rows,[],[],{'focus':'Tapping demand','evidence':'test'})
assert len(plan['items'])==4 and len({x['key'] for x in plan['items']})==4
assert [x['plays'] for x in plan['items']]==[1,2,2,1]
assert [x['role'] for x in plan['items']]==['warm','focus','focus','check']
assert plan['displayFocus']=='Tapping control'
assert training.session([],[],[]) is None
assert len(training.session(rows[:1],[],[])['items'])==1
print('PASS: distinct four-map route, stable setup, explicit run counts, readable focus and sparse-history fallback.')

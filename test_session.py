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
long_rows=[]
for i in range(50):
    long_rows.append(dict(rows[i%8],id=100+i,key=str(100+i),length=90,priority=50-i))
plans=[training.session(long_rows,[],[],{'focus':'Tapping demand'},minutes=n) for n in (20,40,60)]
assert all(p['version']==3 and not p['limited'] for p in plans)
assert [p['minutes'] for p in plans]==sorted(p['minutes'] for p in plans)
assert len(plans[0]['items'])<len(plans[1]['items'])<len(plans[2]['items'])
for plan in plans:
    assert len({item['key'] for item in plan['items']})==len(plan['items'])
    assert sum(item['role']=='check' for item in plan['items'])>=1
    assert all(item['plays']==2 for item in plan['items'] if item['role']=='focus')
assert training.session(rows[:1],[],[],minutes=60)['limited']
print('PASS: distinct 20/40/60 minute routes, transfer checks, complete-run repeats and truthful sparse-pool duration.')

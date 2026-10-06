from pathlib import Path
import sys,os,time
from unittest.mock import patch
os.environ['APP_ENV']='development'
sys.path.insert(0,str(Path(__file__).resolve().parent))
import app_server as server
import fast_recommender as fast
item=next(m for m in fast.MAPS if not m['mods'] and 3<=m['features']['stars']<=4)
def score(i):return {'id':i,'beatmap':item['base'],'passed':True,'accuracy':.97,'statistics':{'great':int(item['features']['objects'])},'max_combo':item['features']['combo'],'mods':[],'pp':10}
best=[score(2000)];recent=[score(i) for i in range(100)]
state={'user':{'id':999,'username':'independent'},'prefs':{'max_stars':12},'status':{'busy':True},'revision':0}
calls=[]
def api(path,_state):
    calls.append(path)
    if '/best?' in path:return best
    if 'offset=100' in path:
        assert state.get('result') is not None,'Initial list was blocked on enrichment'
        return [score(i) for i in range(100,200)]
    if 'offset=200' in path:return []
    return recent
with patch.object(server,'api',side_effect=api),patch.object(server,'map_file',side_effect=AssertionError('Known reference downloaded')):
    server.build(state)
assert not state['status'].get('error'),state['status']
assert len(state['scores']['recent'])==200 and state['revision']==2
assert state['result']['historyCoverage']['recent']==200
with patch.object(server,'api',side_effect=AssertionError('Warm selection called network')):
    server.start_build(state)
assert not state['status']['busy']
print('PASS: bounded pagination, initial list before enrichment, private history merge, coverage reporting and network-free warm selection.')

# Completed map scores remain reviewable even after the map leaves the current shortlist.
blocked=fast.select(state['user'],best,recent,{'max_stars':12,'blocked_ids':[item['id']]})
key=str(item['id'])+'|[]'
assert key in blocked['practiceAttempts'] and all(m['id']!=item['id'] for m in blocked['maps'])
print('PASS: session review retains submitted score evidence independently of recommendation membership.')

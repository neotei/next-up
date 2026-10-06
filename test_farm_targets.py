"""Regressions for useful farm targets, FC forecasting and independent skill profiles."""
import copy,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fast_recommender as f
import performance_model as model
import recommender as r

def score(item,i,acc=.985,pp=None,miss=0):
    return {'id':i,'beatmap':item['base'],'mods':item['mods'],'accuracy':acc,'passed':True,
            'max_combo':item['features']['combo'],'pp':pp if pp is not None else f.estimate_pp(item,acc*100),
            'statistics':{'great':int(item['features']['objects']*acc),'ok':int(item['features']['objects']*(1-acc)),'miss':miss}}
# A 200+ pp top-100 must not receive 140 pp targets even though a hypothetical
# insertion beyond the known list produces a small positive weighted tail delta.
known=[{'id':i,'beatmap':{'id':10000000+i},'pp':205+i*.5,'mods':[],'passed':True} for i in range(100)]
assert r.weighted_gain(known,123,140)>0
items=[m for m in f.MAPS if not m['mods'] and 215<=f.estimate_pp(m,98.5)<=300 and m['farm']['weight']>0]
items.sort(key=lambda m:m['farm']['weight'],reverse=True)
refs=[score(item,1000+i) for i,item in enumerate(items[:20])]
result=f.select({'id':404,'username':'Independent'},known,refs,{'max_stars':12})
assert result['farmMaps'],'No suitable 200+ pp targets despite successful comparable references'
assert all(m['estimatedPP']>205 for m in result['farmMaps'])
assert all(m['estimatedGain']>=.5 for m in result['farmMaps'])
print('PASS: 200+ pp top-100 receives',len(result['farmMaps']),'supported targets above its cutoff; no 140 pp tail targets.')
# Different identities have no effect, while different performance histories do.
other=f.select({'id':808,'username':'Other'},known,refs,{'max_stars':12})
assert [m['key'] for m in result['farmMaps']]==[m['key'] for m in other['farmMaps']]
# Farm's good-run FC forecast should preserve repeated 99% near-FCs without
# disguising multiple failed attempts as FC accuracy.
item=items[0];records=[]
for i in range(6):records.append({'score':score(item,i,.99,240),'features':item['features'],'topPlay':True})
for i in range(6,12):records.append({'score':score(item,i,.935,160,2),'features':item['features']})
fit=model.assess({'features':item['features']},model.prepare(records),12,[],farming=True)
assert fit and fit['accuracy']>97.5,fit
fails=[]
for i in range(5):
    s=score(item,90+i,.85,0,30);s['passed']=False;fails.append(s)
assert model.assess({'features':item['features']},model.prepare(records),12,fails,farming=True) is None
# Matching bursts is not evidence of sustained-stream ability, and a different
# reading window is not admitted merely because total stars remain equal.
features=dict(item['features'],burstBpm=190,streamBpm=0,streamNotes=6,ar=9)
records=model.prepare([{'score':score(item,i),'features':features} for i in range(6)])
assert model.assess({'features':dict(features,streamBpm=180,streamNotes=32)},records,12,[],farming=True) is None
assert model.assess({'features':dict(features,burstBpm=260)},records,12,[],farming=True) is None
assert model.assess({'features':dict(features,ar=7)},records,12,[],farming=True) is None
print('PASS: demonstrated FC accuracy retained, direct failures reject a target, burst/stream and reading limits stay separate.')
# Essential uncatalogued top plays get a reserved feature-calibration budget.
import os
os.environ['APP_ENV']='development'
import app_server
best=[];recent=[]
for i in range(30):
    s={'id':2000+i,'beatmap':{'id':9000000+i,'difficulty_rating':5.7},'mods':[],'passed':True,'pp':250-i,'accuracy':.99}
    best.append(s)
for i in range(20):recent.append({'id':3000+i,'beatmap':{'id':8000000+i,'difficulty_rating':4.8},'mods':[],'passed':i%2==0,'accuracy':.9})
selected=app_server.reference_candidates({'best':best,'recent':recent})
assert len(selected)==24 and selected[0][0][0]==9000000
assert sum(k[0]>=9000000 for k,s in selected)==16
assert any(not s.get('passed') for k,s in selected)
print('PASS: top achievement, recent passes and recent failures receive bounded reference coverage.')
# Efficient ranking charges real duration, and a higher target needs a bounded
# mechanical stretch without borrowing unsupported reading or streaming ability.
short=f.farm_effort(10,.4,45,.7,1.2,.001)
long=f.farm_effort(10,.4,180,.7,1.2,.001)
assert short[0]>long[0]*3 and short[1]>long[1]*3
base=model.assess({'features':features},records,12,[],farming=True)
challenger=dict(features,stars=features['stars']+.4,aim=features['aim']*1.16)
assert model.assess({'features':challenger},records,12,[],farming=True) is None
stretch=model.assess({'features':challenger},records,12,[],farming=True,stretch=True)
assert stretch and stretch['accuracy']<base['accuracy'] and stretch['fcProbability']<base['fcProbability']
for changes in ({'aim':features['aim']*1.3},{'ar':7},{'streamBpm':180,'streamNotes':32},{'burstBpm':260}):
    assert model.assess({'features':dict(features,**changes)},records,12,[],farming=True,stretch=True) is None
assert model.assess({'features':challenger},records,12,fails,farming=True,stretch=True) is None
print('PASS: effort ranking favors shorter comparable attempts; stretch stays bounded and preserves reading, stream and failure limits.')

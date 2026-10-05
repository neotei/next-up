import sys,copy,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import performance_model as m
import fast_recommender as f
import patterns
base={'stars':4,'aim':2,'speed':1.8,'ar':8,'od':7,'cs':4,'density':3,'length':100,'objects':500,'combo':600,'burstBpm':180,'streamBpm':160,'rhythmVariance':.5,'slider':.4,'bpm':180,'baseStars':4,'rate':1}
def record(i,acc=.97,passed=True,miss=1):
    return {'features':dict(base),'score':{'id':i,'beatmap':{'id':i},'accuracy':acc,'passed':passed,'max_combo':590,'statistics':{'great':490,'ok':9,'miss':miss},'mods':[]}}
refs=m.prepare([record(i) for i in range(6)])
c={'features':dict(base),'transfer':False}
good=m.assess(c,refs,12,[],farming=True)
assert good and good['support']==6
bad=m.prepare([record(i) for i in range(6)]+[record(i,.88,False,30) for i in range(6,18)])
poor=m.assess(c,bad,12,[],farming=True)
assert poor is None or poor['accuracy']<good['accuracy'] and poor['fcProbability']<good['fcProbability']
assert m.assess({**c,'features':{**base,'ar':6}},refs,12,[],farming=True) is None
assert m.assess({**c,'features':{**base,'speed':2.8}},refs,12,[]) is None
assert m.assess(c,refs,3.5,[]) is None
assert m.assess(c,m.prepare([record(1)]),12,[])['provisional']
quit=record(55,.8,False,0);quit['score']['statistics']={'great':5}
assert not m.complete(quit['score'],base)
assert m.profile(refs)['UR'] is None
with tempfile.TemporaryDirectory() as temp:
    path=Path(temp)/'test.osu'
    path.write_text('[TimingPoints]\n0,333.333,4,1,0,100,1,0\n[HitObjects]\n'+'\n'.join(f'256,192,{round(i*83.333)},1,0' for i in range(20)))
    nomod=patterns.describe(path);dt=patterns.describe(path,1.5)
    assert abs(nomod['streamBpm']-180)<2 and abs(dt['streamBpm']-270)<3 and nomod['streamNotes']==20
# Every profile uses identical rules regardless of account identity, and hard feedback survives.
scores=[]
for item in f.MAPS:
    if item['mods'] or not 3.7<=item['features']['stars']<=4.2 or item['features']['ar']>8.5:continue
    score=record(item['id'])['score'];score['beatmap']=item['base'];score['max_combo']=item['features']['combo'];score['pp']=20
    scores.append(score)
    if len(scores)>=12:break
assert scores
one=f.select({'id':1,'username':'A'},scores,[],{'max_stars':4.5})
two=f.select({'id':999,'username':'B'},scores,[],{'max_stars':4.5})
assert [x['key'] for x in one['maps']]==[x['key'] for x in two['maps']]
assert one['maps'] and all(x['stars']<=4.5 for x in one['maps']+one['farmMaps'])
assert all(x['farmEvidence']>0 or x['efficiency']>=1.1 for x in one['farmMaps'])
print('PASS: account-neutral results, sparse profiles, failed attempts, early quits, reading and speed isolation, caps, no fabricated UR, real burst/stream clock rate.')
print('Independent NM profile:',len(one['maps']),'Practice and',len(one['farmMaps']),'Farm;',one['selectionMs'],'ms')

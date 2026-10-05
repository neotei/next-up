"""Select from public precomputed maps; no map downloads or pp calculation at request time."""
import collections
import copy
import json
import math
from pathlib import Path
import statistics
import time
import recommender as r
import training

CATALOG=json.loads((Path(__file__).parent/'catalog.json').read_text())
MAPS=CATALOG['maps']

def canonical(mods):
    result=[]
    for mod in r.normal_mods(mods):
        if mod['acronym']=='CL':continue
        value=copy.deepcopy(mod)
        if value['acronym']=='NC':value['acronym']='DT'
        if value.get('settings')=={'speed_change':1.5}:value.pop('settings')
        result.append(value)
    return r.normal_mods(result)

INDEX={(m['id'],r.signature(m['mods'])):m for m in MAPS}
REFERENCE_FEATURES={}
PP_BANDS=collections.defaultdict(list)
for m in MAPS:
    if m['curve']:PP_BANDS[(r.signature(m['mods']),round(m['features']['stars']*2))].append(m['curve']['99'])
PP_MEDIANS={k:statistics.median(v) for k,v in PP_BANDS.items()}

def estimate_pp(m,accuracy):
    points=sorted((float(a),pp) for a,pp in m['curve'].items())
    for (lo,p),(hi,q) in zip(points,points[1:]):
        if lo<=accuracy<=hi:return p+(q-p)*(accuracy-lo)/(hi-lo)
    return points[0][1] if accuracy<points[0][0] else points[-1][1]

def select(user,best,recent,prefs):
    started=time.perf_counter()
    cap=float(prefs.get('max_stars',12))
    blocked=set(prefs.get('blocked_ids',[]))
    samples={s.get('id',str(s)):s for s in best+recent if r.supported(s) and s.get('beatmap')}
    groups=collections.defaultdict(list);poor=collections.defaultdict(list)
    attempts=collections.defaultdict(list);existing={}
    for s in samples.values():
        key=(s['beatmap']['id'],r.signature(canonical(s.get('mods',[]))))
        existing[key]=s
        m=INDEX.get(key)
        feature=m['features'] if m else REFERENCE_FEATURES.get(key)
        if not feature:continue
        record={'score':s,'features':feature}
        if r.anchor(s,feature,cap):groups[key[1]].append(record)
        elif not s.get('passed') or s.get('accuracy',0)<.92:poor[key[1]].append(record)
    for s in recent:
        if r.supported(s) and s.get('beatmap'):
            attempts[(s['beatmap']['id'],r.signature(canonical(s.get('mods',[]))))].append(s)
    floors={key:r.reading_floor(refs,poor[key]) for key,refs in groups.items()}
    physical=[a for key,refs in groups.items() for a in refs
              if all(m['acronym'] in ('DT','NC','CL') for m in a['score'].get('mods',[]))]
    transfers=set()
    if len(physical)>=3:
        shared=r.reading_floor(physical,[a for values in poor.values() for a in values])
        target=statistics.median(a['features']['ar'] for a in physical)
        target=min((9.3,9.5,9.7,10.),key=lambda ar:abs(ar-target))
        for mods in ([],[{'acronym':'HR'}],[{'acronym':'DA','settings':{'approach_rate':target}}]):
            key=r.signature(mods)
            if len(groups.get(key,[]))<2:
                groups[key]=physical;floors[key]=max(shared,r.reading_floor(physical,poor[key]));transfers.add(key)
    practice=[];farm=[]
    for m in MAPS:
        mid=m['id'];mods=m['mods'];key=r.signature(mods);refs=groups.get(key,[])
        f=m['features']
        if mid in blocked or len(refs)<2:continue
        group_cap=min(cap,float(prefs.get('mod_caps',{}).get(key,cap)))
        if f['stars']>group_cap or f['ar']<floors.get(key,11)-.08:continue
        score=existing.get((mid,key))
        c={'map':m['base'],'features':f,'mods':mods,'score':score,'transfer':key in transfers}
        history=attempts.get((mid,key),[])
        fit=r.assess(c,refs,group_cap,history,floors[key])
        farm_fit=(r.assess(c,refs,group_cap,history,floors[key],farming=True)
                  if key not in transfers and m['curve'] and m['farm']['weight']>0 else None)
        if not fit and not farm_fit:continue
        matched=fit or farm_fit
        ref=matched['neighbor'];ns=ref['score'];nf=ref['features'];nb=ns['beatmap'];nbs=ns.get('beatmapset',{})
        ar=round(f['ar'],1)
        da=any(x['acronym']=='DA' for x in mods)
        row={'id':mid,'key':str(mid)+'|'+key,'modKey':key,'setId':m['setId'],'title':m['title'],'artist':m['artist'],
             'version':m['version'],'mapper':'','stars':round(f['stars'],2),'baseStars':round(f['baseStars'],2),
             'bpm':round(f['bpm']),'length':round(f['length']),'ar':ar,'od':round(f['od'],1),'cs':round(f['cs'],1),
             'mods':r.label(mods),'modSettings':mods,'setupInstructions':('Difficulty Adjust: AR '+str(ar)+'; leave other settings unchanged.' if da else 'Use '+r.label(mods)+'.'),
             'accuracy':matched['accuracy'],'kind':'retry' if score else 'new',
             'cover':f'https://assets.ppy.sh/beatmaps/{m["setId"]}/covers/cover@2x.jpg',
             'url':f'https://osu.ppy.sh/beatmapsets/{m["setId"]}#osu/{mid}',
             'priority':matched['suitability'],'focus':matched['focus'],'stage':matched['stage'],'goal':matched['goal'],
             'style':'Aim leaning' if f['aim']>f['speed']*1.12 else 'Speed leaning' if f['speed']>f['aim']*1.12 else 'Balanced',
             'provisional':key in transfers,'support':matched['support'],'fit':'Similar clean plays',
             'reason':f'Matched to {nbs.get("title","a clean play")} [{nb.get("version","")}] at {nf["stars"]:.2f} stars and {ns["accuracy"]*100:.2f}% accuracy, while keeping reading comfortable and limiting increases in physical demands.',
             'evidence':{'id':nb['id'],'title':nbs.get('title',''),'version':nb.get('version',''),
                         'stars':round(nf['stars'],2),'accuracy':round(ns['accuracy']*100,2),'comboPercent':round(r.coverage(ns,nf)*100)}}
        if fit:practice.append(row)
        if farm_fit:
            acc=farm_fit['accuracy'];pp=estimate_pp(m,acc);gain=r.weighted_gain(best,mid,pp)
            if gain<=.05:continue
            confidence=math.exp(-farm_fit['similarity']*.45)*min(1,farm_fit['support']/4)
            median=PP_MEDIANS.get((key,round(f['stars']*2)),pp)
            efficiency=max(.5,min(2,pp/max(1,median)))
            # Crowd top-score prevalence supplies farm evidence; short attempts reduce work.
            crowd=math.log1p(m['farm']['weight']*10000)
            # Gain leads the ranking. Bounded farm/effort bonuses cannot make
            # a tiny upgrade beat a substantial, physically supported target.
            crowd_bonus=1+.2*math.tanh(crowd/5)
            rank=gain**1.5*crowd_bonus*efficiency**.35*confidence/(f['length']/60+.5)**.3
            farm.append(dict(row,accuracy=acc,estimatedPP=round(pp,1),estimatedGain=round(gain,2),
                maxPP=round(estimate_pp(m,100),1),highAccuracyPP=round(estimate_pp(m,99),1),highAccuracyGain=round(r.weighted_gain(best,mid,estimate_pp(m,99)),2),
                priority=rank,stage='Farm',focus='PP efficiency',provisional=False,
                farmEvidence=round(m['farm']['weight'],6),topScoreUse=m['farm']['topScoreUse'],
                retrySeconds=round(f['length']),efficiency=round(efficiency,2),goal=f'Full combo at {acc:.1f}% accuracy.',
                reason=f'This map appears repeatedly in community top scores after popularity and age adjustments. Its {round(f["length"])}-second attempts and {pp:.1f} estimated FC pp at {acc:.1f}% make it a pp-efficiency pick within your demonstrated range; an improved score is estimated to add {gain:.2f} weighted profile pp.'))
    def distinct(rows,limit):
        seen=set();out=[]
        for row in sorted(rows,key=lambda row:row['priority'],reverse=True):
            if row['id'] in seen:continue
            seen.add(row['id']);out.append(row)
            if len(out)>=limit:break
        return out
    # Keep practice mod variety, while Farm is ranked by pp efficiency rather than novelty.
    buckets=collections.defaultdict(list)
    for row in sorted(practice,key=lambda row:row['priority'],reverse=True):buckets[row['mods']].append(row)
    mixed=[]
    while any(buckets.values()):
        for key in sorted(buckets,key=lambda k:(k!='NM',k)):
            if buckets[key]:mixed.append(buckets[key].pop(0))
    practice_rows=[];seen=set()
    for row in mixed:
        if row['id'] in seen:continue
        seen.add(row['id']);practice_rows.append(row)
        if len(practice_rows)>=60:break
    farm_rows=distinct(farm,60)
    profiles=[{'mods':r.label(json.loads(key)),'ceiling':round(r.ceiling(refs,cap),2),'provisional':key in transfers,
               'count':0 if key in transfers else len(refs),'minAR':floors[key],
               'accuracy':round(statistics.median(a['score']['accuracy']*100 for a in refs),2)}
              for key,refs in groups.items() if len(refs)>=2]
    return {'algorithmVersion':7,'demo':False,'user':user['username'],'userId':user['id'],
        'practiceSession':training.session(practice_rows,best,recent),'profilePP':round(user.get('statistics',{}).get('pp',0)),'maps':practice_rows,'farmMaps':farm_rows,
        'mode':'practice','maxStars':cap,'comfortableCeiling':max((p['ceiling'] for p in profiles),default=cap),
        'profiles':profiles,'sample':len(samples),'cleanSample':sum(p['count'] for p in profiles),'bestCount':len(best),
        'minAR':min(floors.values(),default=9.5),'updated':time.time(),
        'warning':None if practice_rows else 'Not enough matching clean plays in the catalogue yet.',
        'farmWarning':None if farm_rows else 'No supported farm targets currently fit your reading and difficulty limits.',
        'catalogSize':len(MAPS),'selectionMs':round((time.perf_counter()-started)*1000,1),
        'summary':'Farm uses community top-score prevalence, pp efficiency and short repeatable attempts, then matches your actual clean lazer plays. Practice keeps skill-building goals. Maps and pp curves are prepared in advance; pp figures are estimates and exclude bonus pp.'}

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
import performance_model as model

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
    best_ids={s.get('id') for s in best}
    targets=farm_targets(best)
    cap=float(prefs.get('max_stars',12))
    blocked=set(prefs.get('blocked_ids',[]))
    samples={s.get('id',str(s)):s for s in best+recent if r.supported(s) and s.get('beatmap')}
    groups=collections.defaultdict(list);poor=collections.defaultdict(list)
    attempts=collections.defaultdict(list);existing={}
    for s in samples.values():
        key=(s['beatmap']['id'],r.signature(canonical(s.get('mods',[]))))
        if s.get('passed') and (key not in existing or s.get('accuracy',0)>existing[key].get('accuracy',0)):existing[key]=s
        m=INDEX.get(key)
        feature=m['features'] if m else REFERENCE_FEATURES.get(key)
        if not feature:continue
        record={'score':s,'features':feature,'topPlay':s.get('id') in best_ids,'modKey':key[1]}
        groups[key[1]].append(record)
        if not s.get('passed') or s.get('accuracy',0)<.92:poor[key[1]].append(record)
    for s in recent:
        if r.supported(s) and s.get('beatmap'):
            attempts[(s['beatmap']['id'],r.signature(canonical(s.get('mods',[]))))].append(s)
    groups={key:model.prepare(refs) for key,refs in groups.items()}
    floors={key:min((a['features']['ar'] for a in refs if model.success(a)),default=0) for key,refs in groups.items()}
    transfers=set()
    diagnosis=model.diagnose(groups)
    practice=[];farm=[]
    for m in MAPS:
        mid=m['id'];mods=m['mods'];key=r.signature(mods);refs=groups.get(key,[])
        f=m['features']
        if mid in blocked or not refs:continue
        group_cap=min(cap,float(prefs.get('mod_caps',{}).get(key,cap)))
        if f['stars']>group_cap:continue
        score=existing.get((mid,key))
        c={'map':m['base'],'features':f,'mods':mods,'score':score,'transfer':key in transfers}
        history=attempts.get((mid,key),[])
        fit=model.assess(c,refs,group_cap,history,floors[key])
        band_median=PP_MEDIANS.get((key,round(f['stars']*2)),m['curve'].get('99',0))
        intrinsic_efficiency=m['curve'].get('99',0)/max(1,band_median)
        farm_fit=(model.assess(c,refs,group_cap,history,floors[key],farming=True)
                  if key not in transfers and m['curve'] and (m['farm']['weight']>0 or intrinsic_efficiency>=1.1) else None)
        if not fit and not farm_fit:continue
        matched=fit or farm_fit
        ref=matched['neighbor'];ns=ref['score'];nf=ref['features'];nb=ns['beatmap'];nbs=ns.get('beatmapset',{})
        ar=round(f['ar'],1)
        da=any(x['acronym']=='DA' for x in mods)
        row={'id':mid,'key':str(mid)+'|'+key,'modKey':key,'setId':m['setId'],'title':m['title'],'artist':m['artist'],
             'version':m['version'],'mapper':'','stars':round(f['stars'],2),'baseStars':round(f['baseStars'],2),
             'bpm':round(f['bpm']),'length':round(f['length']),'ar':ar,'od':round(f['od'],1),'cs':round(f['cs'],1),
             'mods':r.label(mods),'modSettings':mods,'setupInstructions':('Difficulty Adjust: AR '+str(ar)+'; leave other settings unchanged.' if da else 'Use '+r.label(mods)+'.'),
             'accuracy':matched['accuracy'],'confidence':matched['confidence'],'passProbability':matched['passProbability'],'burstBpm':f.get('burstBpm',0),'streamBpm':f.get('streamBpm',0),'streamNotes':f.get('streamNotes',0),'kind':'retry' if score else 'new',
             'cover':f'https://assets.ppy.sh/beatmaps/{m["setId"]}/covers/cover@2x.jpg',
             'url':f'https://osu.ppy.sh/beatmapsets/{m["setId"]}#osu/{mid}',
             'priority':matched['suitability'],'focus':matched['focus'],'stage':matched['stage'],'goal':matched['goal'],
             'style':model.style(f),
             'provisional':matched['provisional'],'support':matched['support'],'fit':'Comparable outcomes',
             'reason':f'Compared against {matched["support"]} different maps, including {nbs.get("title","a clean play")} [{nb.get("version","")}] at {nf["stars"]:.2f} stars and {ns["accuracy"]*100:.2f}% accuracy, using recent outcomes as well as top scores to limit simultaneous increases in demand.',
             'evidence':{'id':nb['id'],'title':nbs.get('title',''),'version':nb.get('version',''),
                         'stars':round(nf['stars'],2),'accuracy':round(ns['accuracy']*100,2),'comboPercent':round(r.coverage(ns,nf)*100)}}
        if fit:practice.append(row)
        if farm_fit:
            acc=farm_fit['accuracy'];pp=estimate_pp(m,acc);gain=r.weighted_gain(best,mid,pp)
            if pp<targets['minScorePP'] or gain<targets['minGain']:continue
            # Forecasts below a full top-100 boundary are tail estimates, not useful farm targets.
            if targets['top100Cutoff'] and pp<=targets['top100Cutoff']:continue
            confidence=farm_fit['confidence']
            median=PP_MEDIANS.get((key,round(f['stars']*2)),pp)
            efficiency=max(.5,min(2,intrinsic_efficiency))
            # Crowd top-score prevalence supplies farm evidence; short attempts reduce work.
            crowd=math.log1p(m['farm']['weight']*10000)
            # Gain leads the ranking. Bounded farm/effort bonuses cannot make
            # a tiny upgrade beat a substantial, physically supported target.
            crowd_bonus=1+.2*math.tanh(crowd/5)
            # Expected valuable completions per effort, with uncertainty and farm prevalence.
            completion=farm_fit['fcProbability']
            rank=gain*completion*crowd_bonus*efficiency**.5*(.5+.5*confidence)/(f['length']/60+.35)**.6

            farm.append(dict(row,accuracy=acc,estimatedPP=round(pp,1),estimatedGain=round(gain,2),
                maxPP=round(estimate_pp(m,100),1),highAccuracyPP=round(estimate_pp(m,99),1),highAccuracyGain=round(r.weighted_gain(best,mid,estimate_pp(m,99)),2),
                priority=rank,stage='Farm',focus='PP efficiency',provisional=farm_fit['provisional'],
                fcProbability=farm_fit['fcProbability'],confidence=confidence,accuracyLow=farm_fit['accuracyLow'],accuracyHigh=farm_fit['accuracyHigh'],
                farmEvidence=round(m['farm']['weight'],6),topScoreUse=m['farm']['topScoreUse'],
                retrySeconds=round(f['length']),efficiency=round(efficiency,2),goal=f'Full combo at {acc:.1f}% accuracy.',
                reason=('This map appears repeatedly in community top scores after popularity and age adjustments. ' if m['farm']['weight']>0 else f'Its 99% FC pp is {intrinsic_efficiency:.2f} times the median for this mod and star band in the catalogue. ')+f'Its {round(f["length"])}-second attempts and {pp:.1f} estimated FC pp at {acc:.1f}% make it a pp-efficiency pick within your demonstrated range; an improved score is estimated to add {gain:.2f} weighted profile pp, against your {targets["minScorePP"]:.0f} pp target floor.'))
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
    profiles=[{'mods':r.label(json.loads(key)),'ceiling':round(min(cap,max((a['features']['stars'] for a in refs if model.success(a)),default=0)),2),'provisional':key in transfers,
               'count':sum(model.success(a) for a in refs),'minAR':floors[key],
               'accuracy':round(statistics.median(a['score']['accuracy']*100 for a in refs),2)}
              for key,refs in groups.items() if any(model.success(a) for a in refs)]
    return {'algorithmVersion':9,'farmTargets':targets,'featureCoverage':{'matchedBest':sum((s.get('beatmap',{}).get('id'),r.signature(canonical(s.get('mods',[])))) in INDEX or (s.get('beatmap',{}).get('id'),r.signature(canonical(s.get('mods',[])))) in REFERENCE_FEATURES for s in best if r.supported(s)), 'supportedBest':sum(r.supported(s) for s in best)},'performance':model.profile([a for refs in groups.values() for a in refs]),'matchedSample':sum(len(refs) for refs in groups.values()),'demo':False,'user':user['username'],'userId':user['id'],
        'practiceAttempts':{str(mid)+'|'+key:[{'id':s.get('id'),'time':model.score_time(s),'accuracy':round(s.get('accuracy',0)*100,2),'misses':r.miss_count(s),'passed':bool(s.get('passed'))} for s in values[:5]] for (mid,key),values in attempts.items()},'practiceSession':training.session(practice_rows,best,recent,diagnosis),'profilePP':round(user.get('statistics',{}).get('pp',0)),'maps':practice_rows,'farmMaps':farm_rows,
        'mode':'practice','maxStars':cap,'comfortableCeiling':max((p['ceiling'] for p in profiles),default=cap),
        'profiles':profiles,'sample':len(samples),'cleanSample':sum(p['count'] for p in profiles),'bestCount':len(best),
        'minAR':min(floors.values(),default=9.5),'updated':time.time(),
        'warning':None if practice_rows else 'Not enough matching clean plays in the catalogue yet.',
        'farmWarning':None if farm_rows else f'No supported targets currently meet your {targets["minScorePP"]:.0f} pp farm floor. Top-play feature coverage or the available map pool may be incomplete; lower-value maps remain in Practice.',
        'catalogSize':len(MAPS),'selectionMs':round((time.perf_counter()-started)*1000,1),
        'summary':'Recent passes, complete failures and top scores are compared under the same mods, with newer results carrying more weight. Farm requires a worthwhile score relative to your top plays, then balances gain, near-FC outcomes and retry time; Practice changes one demand at a time. PP forecasts describe an FC, while BPM describes map patterns and UR requires replay hit errors.'}


def farm_targets(best):
    # Only the API's visible best scores are known. Do not infer missing tail scores or treat
    # a tiny hypothetical tail insertion as an actionable farm recommendation.
    by_map={}
    for score in best:
        mid=score.get('beatmap_id') or score.get('beatmap',{}).get('id')
        pp=score.get('pp') or 0
        if mid is not None and pp>0:by_map[mid]=max(by_map.get(mid,0),pp)
    values=sorted(by_map.values(),reverse=True)
    if not values:return {'minScorePP':0,'minGain':.5,'top100Cutoff':0,'benchmarkPP':0,'knownBest':0}
    benchmark=statistics.median(values[:20])
    cutoff=values[99] if len(values)>=100 else 0
    return {'minScorePP':round(max(cutoff,benchmark*.85),2),'minGain':round(max(.5,benchmark*.0025),2),
            'top100Cutoff':round(cutoff,2),'benchmarkPP':round(benchmark,2),'knownBest':len(values)}

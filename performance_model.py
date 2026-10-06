"""Player-independent, uncertainty-aware matching of observed score outcomes."""
import collections
import datetime
import math
import statistics
import time
import recommender as r

AXES={'aim':.45,'speed':.4,'ar':.7,'od':.9,'cs':.7,'density':1.4,'length':90,
      'burstBpm':40,'streamBpm':35,'rhythmVariance':.7,'slider':.22,'jumpDistance':60,'streamNotes':25}

def age_weight(score):
    value=score.get('ended_at') or score.get('created_at')
    try:age=max(0,(time.time()-datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp())/86400)
    except (ValueError,TypeError,AttributeError):age=30
    return (.15+.85*math.exp(-age/45))*(.5 if score.get('legacy_score_id') else 1)

def complete(score,f):
    if score.get('passed'):return True
    stats=score.get('statistics',{})
    judged=sum(stats.get(k,0) for k in ('great','ok','meh','miss'))
    # Early quits are not complete-map accuracy or evidence of a BPM limit.
    return judged>=f['objects']*.75

def success(record):
    s=record['score'];f=record['features']
    return s.get('passed') and s.get('accuracy',0)>=.90 and r.miss_count(s)/max(1,f['objects'])<=.025

def prepare(records):
    # Repeated retries must not drown out diverse maps; keep each mod setup separate.
    buckets=collections.defaultdict(list)
    for a in records:
        key=(a['score']['beatmap']['id'],a.get('modKey',r.signature(r.normal_mods(a['score'].get('mods',[])))))
        buckets[key].append(a)
    out=[]
    for values in buckets.values():
        ordered=sorted(values,key=lambda a:age_weight(a['score']),reverse=True)
        for a in ordered[:4]:
            a=dict(a);a['weight']=age_weight(a['score'])/math.sqrt(min(4,len(values)))
            out.append(a)
    # Preserve successful calibration as well as recent ordinary outcomes.
    out.sort(key=lambda a:a['weight'],reverse=True)
    selected=out
    for a in sorted((x for x in out if success(x)),key=lambda x:x['features']['stars'],reverse=True)[:8]:
        if a not in selected:selected.append(a)
    return selected

def distance(a,b):
    total=0;count=0
    for k,scale in AXES.items():
        if k not in a or k not in b:continue
        delta=(a[k]-b[k])/scale
        if k=='length':delta=math.log(max(15,a[k])/max(15,b[k]))/.65
        total+=delta*delta;count+=1
    return math.sqrt(total/max(1,count))

def weighted_quantile(values,q):
    values=sorted(values)
    total=sum(w for _,w in values)
    if not total:return 0
    threshold=total*q;running=0
    for value,w in values:
        running+=w
        if running>=threshold:return value
    return values[-1][0]

def near_fc(a):
    s=a['score'];f=a['features']
    return s.get('passed') and s.get('accuracy',0)>=.92 and r.miss_count(s)<=max(2,f['objects']*.004) and r.coverage(s,f)>=.90

def style(f):
    if f.get('streamNotes',0)>=16:return 'Streams'
    if f.get('slider',0)>=.55:return 'Slider control'
    if f.get('rhythmVariance',0)>.85:return 'Rhythm control'
    if f.get('aim',0)>f.get('speed',0)*1.18:return 'Jumps'
    if f.get('burstBpm',0)>0:return 'Bursts / hybrid'
    return 'Mixed'

def assess(candidate,records,cap,attempts,min_ar=None,farming=False):
    f=candidate['features'];proven=[a for a in records if near_fc(a)] if farming else [a for a in records if success(a)]
    if not proven or f['stars']>cap or f['length']<(20 if farming else 35):return None
    # Match a demonstrated demand envelope under this mod setup, rather than total stars alone.
    envelopes=[]
    for a in proven:
        n=a['features']
        increases={k:f[k]/max(.1,n[k]) for k in ('aim','speed','density','length')}
        if f['stars']>n['stars']+(.25 if farming else .4):continue
        if any(increases[k]>(1.12 if farming else 1.18) for k in ('aim','speed','density')):continue
        if increases['length']>(1.35 if farming else 1.6):continue
        if sum(increases[k]>1.08 for k in ('aim','speed','density'))>1:continue
        # A song's BPM is not a tapping ceiling. Match actual bursts and sustained runs separately.
        if any(f.get(k,0)>n.get(k,0)*(1.06 if farming else 1.12)+3 for k in ('burstBpm','streamBpm')):continue
        if f.get('streamNotes',0)>=16 and (n.get('streamNotes',0)<16 or f['streamNotes']>n['streamNotes']*(1.2 if farming else 1.5)):continue
        if abs(f.get('slider',0)-n.get('slider',0))>.28:continue
        if abs(f['ar']-n['ar'])>(.55 if farming else .8) or f['od']>n['od']+.65 or f['cs']>n['cs']+.5:continue
        if distance(f,n)<=1.25:envelopes.append(a)
    if not envelopes:return None
    nearest=min(envelopes,key=lambda a:distance(f,a['features']))
    neighbors=sorted(records,key=lambda a:distance(f,a['features']))[:12]
    neighbors=[a for a in neighbors if distance(f,a['features'])<=1.35]
    if not neighbors:return None
    weighted=[]
    for a in neighbors:
        d=distance(f,a['features']);w=a.get('weight',age_weight(a['score']))*math.exp(-3*d*d)
        if farming and a.get('topPlay') and near_fc(a):w*=1.5
        if not complete(a['score'],a['features']):w*=.15
        weighted.append((a,w))
    denom=sum(w for a,w in weighted)
    finished=[(a,w) for a,w in weighted if complete(a['score'],a['features'])]
    if not finished:return None
    if farming:
        successful=[(a,w) for a,w in finished if a['score'].get('passed')]
        if successful:finished=successful
    acc=sum(a['score'].get('accuracy',0)*100*w for a,w in finished)/sum(w for a,w in finished)
    if farming:
        achievements=[(a,w) for a,w in finished if near_fc(a)]
        if achievements:
            # FC potential is a repeatable good-run outcome, not the average of every exploratory pass.
            potential=weighted_quantile([(a['score'].get('accuracy',0)*100,w) for a,w in achievements],.60)
            acc=.25*acc+.75*potential
    missrate=sum(r.miss_count(a['score'])/max(1,a['features']['objects'])*w for a,w in finished)/sum(w for a,w in finished)
    passed=(.3+sum(w for a,w in weighted if a['score'].get('passed')))/(.6+denom)
    fc=(.25+sum(w for a,w in weighted if a['score'].get('passed') and r.miss_count(a['score'])==0 and r.coverage(a['score'],a['features'])>=.97))/(1+denom)
    n=nearest['features'];elevated=[k for k in ('aim','speed','density','length') if f[k]>n[k]*1.08]
    if 'speed' not in elevated and any(f.get(k,0)>n.get(k,0)*1.08+3 for k in ('burstBpm','streamBpm')):elevated.append('speed')
    # Wider reading is a challenge only where success exists nearby, never a universal AR floor.
    if abs(f['ar']-n['ar'])>.35:elevated.append('ar')
    if len(elevated)>1 and not farming:return None
    acc-=max(0,f['stars']-n['stars'])*1.5
    direct=[s for s in sorted(attempts,key=score_time,reverse=True) if complete(s,f)][:6]
    if direct:
        direct_acc=[s.get('accuracy',0)*100 for s in direct if s.get('passed')] if farming else [s.get('accuracy',0)*100 for s in direct]
        if direct_acc:acc=.65*statistics.mean(direct_acc)+.35*acc
        passed=.65*sum(bool(s.get('passed')) for s in direct)/len(direct)+.35*passed
        fc=.65*sum(bool(s.get('passed')) and r.miss_count(s)==0 and r.coverage(s,f)>=.97 for s in direct)/len(direct)+.35*fc
    if passed<(.6 if farming else .5) or acc<(92 if farming else 90):return None
    if farming and missrate>.01:return None
    spread=statistics.pstdev([a['score'].get('accuracy',0)*100 for a,w in finished]) if len(finished)>1 else 3
    support=len({a['score']['beatmap']['id'] for a,w in finished})
    confidence=min(.95,support/(support+3))*math.exp(-distance(f,n)*.4)
    provisional=support<3 or candidate.get('transfer',False)
    if candidate.get('transfer'):fc*=.5;confidence*=.5
    challenge=elevated[0] if elevated else None
    focus={'aim':'Aim control','speed':'Tapping demand','density':'Dense patterns','length':'Long-run consistency','ar':'Reading range'}.get(challenge,'Accuracy control' if acc<97 else 'Consistency')
    if challenge=='speed':focus='Stream control' if f.get('streamNotes',0)>=16 else 'Burst control'
    stage='Trial' if provisional else 'Stretch' if challenge else 'Control' if missrate>.003 or acc<97 else 'Explore'
    utility=confidence*passed*math.exp(-((acc-96)/3.5)**2)*(1.15 if challenge else 1)*min(1.3,max(.6,f['length']/90))
    return {'accuracy':round(min(99.7,max(90,acc)),2),'accuracyLow':round(max(0,acc-spread),2),'accuracyHigh':round(min(100,acc+spread),2),
            'neighbor':nearest,'similarity':distance(f,n),'suitability':utility,'support':support,'focus':focus,'stage':stage,
            'challenge':challenge,'provisional':provisional,'passProbability':round(passed,3),'fcProbability':round(fc,3),
            'confidence':round(confidence,3),'goal':f'Complete the run around {acc:.1f}% accuracy, then compare misses across two attempts.'}

def profile(records):
    clean=[a for a in records if success(a)]
    return {'observedBurstBpm':round(max((a['features'].get('burstBpm',0) for a in clean),default=0)),
            'observedStreamBpm':round(max((a['features'].get('streamBpm',0) for a in clean),default=0)),
            'UR':None,'URStatus':'Replay hit errors required; accuracy cannot determine UR.',
            'timingStatus':'BPM figures describe patterns in successful maps, not a measured personal speed limit.',
            'matchedScores':len(records),'successfulMaps':len({a['score']['beatmap']['id'] for a in clean}),
            'modProfiles':skill_profiles(records)}

def diagnose(groups):
    """Matched-demand associations, not causal diagnoses of individual mistakes."""
    labels={'aim':'Aim control','speed':'Tapping demand','burstBpm':'Burst control','streamBpm':'Stream control','density':'Dense patterns','length':'Long-run consistency','ar':'Reading range'}
    findings=[]
    for axis in labels:
        contrasts=[];maps=set()
        for records in groups.values():
            valid=[a for a in records if complete(a['score'],a['features'])][:100]
            for a in valid:
                f=a['features']
                controls=[]
                for b in valid:
                    g=b['features']
                    if a['score']['beatmap']['id']==b['score']['beatmap']['id']:continue
                    if abs(f['stars']-g['stars'])>.45:continue
                    if axis=='ar':
                        if abs(f['ar']-g['ar'])<.4:continue
                    elif f[axis]<g[axis]*1.12:continue
                    held=('aim','speed','density','length','ar')
                    if any(abs(f[k]-g[k])>(.4 if k=='ar' else max(.15,g[k]*.25)) for k in held if k!=axis):continue
                    controls.append(b)
                if not controls:continue
                outcome=lambda s:s.get('accuracy',0)*100- min(10,r.miss_count(s)*.5)-(0 if s.get('passed') else 5)
                contrast=statistics.median(outcome(b['score']) for b in controls)-outcome(a['score'])
                contrasts.append(contrast);maps.add(a['score']['beatmap']['id'])
        if len(maps)>=3 and len(contrasts)>=5:
            loss=statistics.median(contrasts)
            if loss>1:findings.append({'axis':axis,'focus':labels[axis],'loss':round(loss,1),'maps':len(maps),'comparisons':len(contrasts)})
    if not findings:return {'focus':'Balanced control','axis':None,'evidence':'There is not yet enough comparable evidence to isolate one weakness. Use varied, manageable maps and compare complete runs under the same mods.'}
    finding=max(findings,key=lambda a:a['loss'])
    finding['evidence']=f'Across {finding["maps"]} maps and {finding["comparisons"]} comparable observations, outcomes were weaker when the {finding["axis"]} requirement changed. This is a training lead to check across complete runs, rather than proof of the cause of individual misses.'
    return finding


def score_time(score):
    try:return datetime.datetime.fromisoformat((score.get('ended_at') or score.get('created_at')).replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError,AttributeError):return 0


def skill_profiles(records):
    groups=collections.defaultdict(list)
    for a in records:
        if success(a):groups[a.get('modKey',r.signature(r.normal_mods(a['score'].get('mods',[]))))].append(a)
    out=[]
    for key,rows in groups.items():
        weights=[a.get('weight',age_weight(a['score'])) for a in rows]
        def band(axis):
            values=[(a['features'].get(axis,0),w) for a,w in zip(rows,weights)]
            return [round(weighted_quantile(values,q),2) for q in (.15,.5,.85)]
        families=collections.Counter(style(a['features']) for a in rows)
        out.append({'modKey':key,'successfulMaps':len({a['score']['beatmap']['id'] for a in rows}),
                    'arBand':band('ar'),'starBand':band('stars'),'burstBpmBand':band('burstBpm'),
                    'streamBpmBand':band('streamBpm'),'lengthBand':band('length'),'styles':dict(families)})
    return out

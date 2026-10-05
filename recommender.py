"""Evidence-based practice selection with per-mod reading constraints and limited stretch."""
import collections
import json
import math
import statistics
import urllib.parse
import rosu_pp_py as rosu

VERSION = 5
DEFAULT_CAP = 5.25
FEATURE_SCALES = {'stars': .45, 'aim': .35, 'speed': .32, 'ar': .65,
                  'od': .7, 'cs': .65, 'density': 1.2, 'slider': .2,
                  'length': 50, 'bpm': 35}
FEATURE_WEIGHTS = {'stars': 2, 'aim': 1.5, 'speed': 1.5, 'ar': 1.2,
                   'od': .7, 'cs': .7, 'density': 1, 'slider': .4,
                   'length': .5, 'bpm': .5}


def supported(score):
    if score.get('legacy_score_id') or score.get('ruleset_id', 0) != 0:
        return False
    # No fail/reduced difficulty/autoplay scores cannot establish a farm skill level.
    allowed = {'HD', 'HR', 'DT', 'NC', 'CL', 'SD', 'PF', 'DA'}
    return all(mod.get('acronym') in allowed for mod in score.get('mods', []))


def normal_mods(mods):
    # SD/PF only alter failure conditions. Preserve every gameplay setting, including speed.
    return sorted([m for m in mods if m['acronym'] not in ('SD', 'PF')], key=lambda m: m['acronym'])


def signature(mods):
    return json.dumps(normal_mods(mods), sort_keys=True, separators=(',', ':'))


def label(mods):
    labels = []
    for mod in normal_mods(mods):
        name = mod['acronym']
        if name=='DA':
            ar=mod.get('settings',{}).get('approach_rate')
            name=('NM + DA' if len(normal_mods(mods))==1 else 'DA')+(f' AR{ar:g}' if ar is not None else '')
        rate = mod.get('settings', {}).get('speed_change')
        if rate is not None:
            name += f' {rate:g}x'
        labels.append(name)
    return '+'.join(labels) or 'NM'


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low = int(index)
    return values[low] + (values[min(low+1, len(values)-1)] - values[low]) * (index-low)


def features(obj, beatmap, mods):
    difficulty = rosu.Difficulty(mods=mods, lazer=True)
    builder = rosu.BeatmapAttributesBuilder(mods=mods)
    builder.set_map(obj)
    # The pinned attributes builder does not read DA settings from modern mods.
    # Apply explicit base overrides to both calculations so displayed and gated
    # AR/OD/CS stay consistent with the actual lazer setup.
    for mod in mods:
        if mod.get('acronym')=='DA':
            settings=mod.get('settings',{})
            for field,name in [('approach_rate','ar'),('overall_difficulty','od'),('circle_size','cs')]:
                if field in settings:
                    getattr(difficulty,'set_'+name)(settings[field],False)
                    getattr(builder,'set_'+name)(settings[field],False)
    diff=difficulty.calculate(obj)
    effective = builder.build()
    duration = max(10, beatmap.get('hit_length') or beatmap.get('total_length') or 90) / effective.clock_rate
    return {'stars': diff.stars, 'aim': diff.aim or 0, 'speed': diff.speed or 0,
            'ar': effective.ar, 'od': effective.od, 'cs': effective.cs,
            'density': (diff.speed_note_count or 0) / duration,
            'slider': obj.n_sliders / max(1, obj.n_objects), 'length': duration,
            'bpm': (beatmap.get('bpm') or obj.bpm) * effective.clock_rate,
            'combo': diff.max_combo, 'objects': obj.n_objects,
            'baseStars': beatmap.get('difficulty_rating', diff.stars), 'rate': effective.clock_rate,
            '_difficulty':diff}


def distance(a, b):
    return math.sqrt(sum(FEATURE_WEIGHTS[k] * ((a[k]-b[k])/scale)**2
                         for k, scale in FEATURE_SCALES.items()) / sum(FEATURE_WEIGHTS.values()))


def miss_count(score):
    stats = score.get('statistics', {})
    return stats.get('miss', stats.get('count_miss', 0))


def coverage(score, feature):
    return min(1, score.get('max_combo', 0) / max(1, feature['combo']))


def anchor(score, feature, cap):
    return (score.get('passed', False) and feature['stars'] <= cap and
            score.get('accuracy', 0) >= .945 and miss_count(score) <= 1 and
            coverage(score, feature) >= .88)


def ceiling(anchors, cap):
    # A single short or unusually valuable top play cannot raise the whole envelope.
    allowance = .08 if len(anchors) >= 4 else -.10 if len(anchors) >= 2 else -.25
    return min(cap, percentile([a['features']['stars'] for a in anchors], .65) + allowance)


def reading_floor(anchors, poor):
    """Robust lower edge of clean reading evidence, tightened by repeated poor attempts.

    Not a diagnosis: failure can have other causes. Compare only roughly similar
    difficulty and density before treating lower-AR failures as reading evidence.
    """
    if not anchors:
        return None
    values = [a['features']['ar'] for a in anchors]
    baseline = percentile(values,.35)
    floor = baseline-.15 if len(values)>=4 else baseline-.05
    comparable = []
    for record in poor:
        f=record['features']
        if f['ar'] >= baseline:
            continue
        if any(abs(f['stars']-a['features']['stars'])<=.4 and
               f['density']<=a['features']['density']*1.15+.1 and
               f['aim']<=a['features']['aim']*1.1+.03 and
               f['speed']<=a['features']['speed']*1.1+.03 for a in anchors):
            comparable.append(f['ar'])
    if len(comparable)>=3:
        floor=max(floor,min(baseline,percentile(comparable,.8)+.2))
    return round(max(0,floor),2)


def assess(candidate, anchors, cap, attempts, min_ar=9.5, farming=False):
    """Practice fit: isolate one modest challenge while holding reading comfortable."""
    f = candidate['features']
    transfer=candidate.get('transfer',False)
    if len(anchors)<2 or f['ar'] < min_ar-(.08 if transfer else 0) or f['stars'] > min(cap, ceiling(anchors, cap)+(-.10 if transfer else .18)):
        return None
    severe = [s for s in attempts if not s.get('passed', False) and s.get('accuracy', 0) < .9]
    recent_clean = any(s.get('passed', False) and s.get('accuracy', 0) >= .945 and
                       coverage(s, f) >= .88 for s in attempts)
    if len(severe) >= 2 and not recent_clean:
        return None
    # References with similar reading conditions, not lower AR successes the player rejects.
    readable = [a for a in anchors if a['features']['ar'] >= min_ar-.2]
    if not readable:
        return None
    # The closest map may be a short outlier. Look for the closest reference that
    # actually supplies a feasible envelope rather than rejecting on that outlier.
    feasible=[]
    for ref in readable:
        n=ref['features']
        ratios={k:f[k]/max(.1,n[k]) for k in ('aim','speed','density','length')}
        if sum(v>1.05 for v in ratios.values())>1:continue
        if any(ratios[k]>1.10 for k in ('aim','speed','density')):continue
        if ratios['length']>(1.6 if transfer else 1.25):continue
        if transfer and any(ratios[k]>1 for k in ('aim','speed','density')):continue
        if f['od']>n['od']+.3 or f['cs']>n['cs']+.25:continue
        if distance(f,n)<=1.4:feasible.append(ref)
    if not feasible:
        return None
    neighbors = sorted(feasible,key=lambda a:distance(f,a['features']))[:5]
    nearest = neighbors[0]
    n = nearest['features']
    similarity = distance(f, n)
    if similarity > 1.4 or f['length'] < (20 if farming else 40):
        return None
    # No more than one component can exceed the matched clean reference by >5%.
    # Aggregate aim/speed attributes are proxies, not diagnoses of jumps or streams.
    ratios = {k:f[k]/max(.1,n[k]) for k in ('aim','speed','density','length')}
    elevated = [k for k,v in ratios.items() if v>1.05]
    if len(elevated)>1:
        return None
    if any(ratios[k]>1.10 for k in ('aim','speed','density')) or ratios['length']>(1.6 if transfer else 1.25):
        return None
    if transfer and any(ratios[k]>1.0 for k in ('aim','speed','density')):
        return None
    if (f['ar'] > max(a['features']['ar'] for a in readable)+.15 or
        f['od'] > n['od']+.3 or f['cs'] > n['cs']+.25):
        return None
    score = candidate.get('score')
    if score and (not score.get('passed') or score.get('accuracy',0)<.90 or
                  miss_count(score)/max(1,f['objects'])>.03):
        return None
    if not farming and score and score.get('accuracy',0)>=.985 and miss_count(score)==0:
        return None  # Already mastered; use new patterns instead of farming the same FC.
    weights = [1/(.2+distance(f,a['features'])) for a in neighbors]
    expected = sum(a['score']['accuracy']*100*w for a,w in zip(neighbors,weights))/sum(weights)-.4-.35*similarity
    if score:
        target = min(99.5 if farming else 98.5, score['accuracy']*100+.5)
    else:
        target = max(94, min(99 if farming else 98,expected))
    if transfer:
        focus,stage='Mod familiarisation','Trial'
        target=min(target,95)
    elif elevated:
        focus = {'aim':'Aim control','speed':'Tapping control','density':'Pattern density','length':'Consistency'}[elevated[0]]
        stage = 'Stretch'
    elif score and (miss_count(score)>0 or score['accuracy']<.97):
        focus,stage = 'Clean up','Control'
    else:
        focus,stage = 'New patterns','Explore'
    # Practice utility, with no pp or FC incentive. Favor meaningful durations and novelty.
    utility = math.exp(-similarity*.6) * (1 if len(readable)>=4 else .7)
    utility *= min(1.2, max(.5, f['length']/90))
    if transfer:
        utility *= .8
    utility *= 1.1 if stage=='Stretch' else 1.05 if stage=='Control' else 1
    return {'accuracy':round(target,2),'neighbor':nearest,'similarity':similarity,
            'suitability':utility,'support':len(neighbors),'focus':focus,'stage':stage,
            'goal':f'Aim for {target:.1f}% accuracy; '+
                   (f'fewer than {miss_count(score)} misses.' if score and miss_count(score)>0 else 'maintain zero misses.' if score else 'keep misses to 1–2.'),
            'challenge':elevated[0] if elevated else None}


def weighted_gain(scores, beatmap_id, proposed):
    by_map={}
    for score in scores:
        key=score.get('beatmap_id') or score.get('beatmap',{}).get('id')
        if key is not None:by_map[key]=max(by_map.get(key,0),score.get('pp') or 0)
    before=sorted(by_map.values(),reverse=True)
    by_map[beatmap_id]=max(by_map.get(beatmap_id,0),proposed)
    after=sorted(by_map.values(),reverse=True)
    total=lambda values:sum(pp*.95**i for i,pp in enumerate(values[:1000]))
    return max(0,total(after)-total(before))


def farm_eligible(mods):
    for mod in mods:
        if mod['acronym'] not in ('HD','HR','DT','NC','CL'):return False
        settings=mod.get('settings',{})
        if any(key!='speed_change' for key in settings):return False
        if settings and (mod['acronym'] not in ('DT','NC') or settings['speed_change']!=1.5):return False
    return True


def build(user, best, recent, config, api, map_file, status, gain_fn):
    cap = min(12, max(1, float(config.get('max_stars', DEFAULT_CAP))))
    min_ar = None
    samples = {s.get('id', str(s)):s for s in best+recent if supported(s) and s.get('beatmap')}
    attempts = collections.defaultdict(list)
    for score in recent:
        if supported(score) and score.get('beatmap'):
            attempts[(score['beatmap']['id'],signature(score.get('mods',[])))].append(score)
    # Limit expensive references, while preserving good lower-pp plays and distinct setups.
    possible = [s for s in samples.values() if s.get('passed') and s.get('accuracy',0)>=.935
                and s['beatmap'].get('ranked') in (1,2)]
    # Start with strong reliable passes, rather than letting easy SS scores consume
    # the small reference budget before the player's actual range is represented.
    possible.sort(key=lambda s:(miss_count(s)<=1,s['accuracy']>=.945,s.get('pp') or 0,s['accuracy']),reverse=True)
    chosen, seen = [], set()
    reference_limit=int(config.get('reference_limit',100))
    buckets=collections.defaultdict(list)
    for s in possible:
        key=(s['beatmap']['id'],signature(s.get('mods',[])))
        if key not in seen:
            seen.add(key);buckets[key[1]].append(s)
    # Round-robin setups so a short first pass does not erase less-used mods.
    while buckets and len(chosen)<reference_limit:
        for key in list(buckets):
            chosen.append(buckets[key].pop(0))
            if not buckets[key]:del buckets[key]
            if len(chosen)>=reference_limit:break
    groups=collections.defaultdict(list)
    analyzed=[]
    memo={}
    def calculate_feature(b,mods):
        key=(b['id'],signature(mods))
        if key not in memo:
            memo[key]=features(map_file(b['id']),b,mods)
        return memo[key]
    skipped=0
    for i,s in enumerate(chosen):
        status['message']=f'Checking reliable plays ({i+1}/{len(chosen)})…'
        try:
            f=calculate_feature(s['beatmap'],s.get('mods',[]))
            record={'score':s,'features':f}
            analyzed.append(record)
            if anchor(s,f,cap):
                groups[signature(s.get('mods',[]))].append(record)
        except (ValueError,RuntimeError,OSError):skipped+=1
    poor_groups=collections.defaultdict(list)
    poor_seen=set()
    poor_limit=int(config.get('poor_limit',100))
    for score in recent:
        if not supported(score) or not score.get('beatmap'):
            continue
        if score.get('passed') and score.get('accuracy',0)>=.92:
            continue
        poor_key=(score['beatmap']['id'],signature(score.get('mods',[])))
        if poor_key in poor_seen:continue
        if len(poor_seen)>=poor_limit:break
        poor_seen.add(poor_key)
        try:
            poor_groups[signature(score.get('mods',[]))].append(
                {'score':score,'features':calculate_feature(score['beatmap'],score.get('mods',[]))})
        except (ValueError,RuntimeError,OSError):
            skipped+=1
    reading_floors={key:reading_floor(refs,poor_groups[key]) for key,refs in groups.items()}
    # Transfer only from visible, standard-size play. Hidden reading is not interchangeable.
    physical=[a for key,refs in groups.items() for a in refs
              if all(m['acronym'] in ('DT','NC','CL') for m in a['score'].get('mods',[]))]
    transfer_keys=set()
    if len(physical)>=3:
        shared_floor=reading_floor(physical,[a for refs in poor_groups.values() for a in refs])
        target_ar=round(statistics.median(a['features']['ar'] for a in physical),1)
        for mods in ([],[{'acronym':'HR'}],[{'acronym':'DA','settings':{'approach_rate':target_ar}}]):
            key=signature(mods)
            if len(groups.get(key,[]))<2:
                groups[key]=physical
                reading_floors[key]=max(shared_floor,reading_floor(physical,poor_groups.get(key,[])))
                transfer_keys.add(key)
    setup_mods={key:json.loads(key) for key in groups}
    group_order=sorted(groups,key=lambda key:(key not in transfer_keys,len(groups[key])),reverse=True)
    candidates={}
    for record in analyzed:
        s=record['score'];mods=normal_mods(s.get('mods',[]))
        key=(s['beatmap']['id'],signature(mods))
        candidates[key]={'map':s['beatmap'],'set':s['beatmapset'],'score':s,'mods':mods,'features':record['features']}
    known={s.get('beatmap_id') or s.get('beatmap',{}).get('id') for s in best+recent}
    discovery_failed=False
    # Each setup searches its own base range, then passes exact post-mod calculation gates.
    discovery_groups=[key for key in group_order if len(groups[key])>=2][:5]
    for key in discovery_groups:
        refs=groups[key]
        mods=setup_mods[key]
        center=(min(ceiling(refs,cap)-.25,cap-.25)/(1.12 if any(m['acronym']=='HR' for m in mods) else 1) if key in transfer_keys else statistics.median(a['features']['baseStars'] for a in refs))
        query=urllib.parse.urlencode(
            {'m':0,'s':'ranked','sort':'plays_desc','q':f'stars>={max(1,center-.7):.2f} stars<={center+.35:.2f} length>=60'+(' ar>=9.4' if key in transfer_keys and not mods else ' cs<=3.3' if key in transfer_keys and any(m['acronym']=='HR' for m in mods) else '')})
        status['message']=f'Finding playable {label(mods)} maps…'
        try:sets=api('beatmapsets/search?'+query,config).get('beatmapsets',[])
        except (ValueError,OSError):sets=[];discovery_failed=True
        pool=[]
        base_bpm=statistics.median(a['features']['bpm'] if key in transfer_keys else a['score']['beatmap'].get('bpm') or 180 for a in refs)
        base_length=statistics.median(a['features']['length'] if key in transfer_keys else a['score']['beatmap'].get('total_length') or 90 for a in refs)
        for bs in sets:
            for b in bs.get('beatmaps',[]):
                if b.get('mode_int',0)!=0 or b.get('ranked') not in (1,2) or b['id'] in known:continue
                if key in transfer_keys and not mods and b.get('ar',0)<9.45:continue
                if key in transfer_keys and any(m['acronym']=='HR' for m in mods) and b.get('cs',0)>3.3:continue
                if b.get('difficulty_rating',0)>center+.4 or b.get('difficulty_rating',0)<center-.8:continue
                rough=abs(b['difficulty_rating']-center)*2+abs((b.get('bpm') or 180)-base_bpm)/70+abs((b.get('total_length') or 90)-base_length)/150
                pool.append((rough,b,bs))
        for _,b,bs in sorted(pool,key=lambda row:row[0])[:int(config.get('discovery_limit',60))]:
            ckey=(b['id'],key)
            candidates.setdefault(ckey,{'map':b,'set':bs,'score':None,'mods':mods,'transfer':key in transfer_keys})
    rows=[];farm_rows=[];rejected=collections.Counter()
    for i,(key,c) in enumerate(candidates.items()):
        if c['map']['id'] in config.get('blocked_ids', []):
            rejected['playerFeedback']+=1
            continue
        status['message']=f'Matching difficulty and recent results ({i+1}/{len(candidates)})…'
        try:
            if 'features' not in c:c['features']=calculate_feature(c['map'],c['mods'])
            refs=groups.get(key[1],[])
            group_cap=min(cap,float(config.get('mod_caps',{}).get(key[1],cap)))
            c['transfer']=key[1] in transfer_keys
            matched=assess(c,refs,group_cap,attempts.get(key,[]),reading_floors.get(key[1],11))
            farm_match=(assess(c,refs,group_cap,attempts.get(key,[]),reading_floors.get(key[1],11),farming=True)
                        if not c['transfer'] and farm_eligible(c['mods']) else None)
            if not matched and not farm_match:rejected['outsidePlayableRange']+=1;continue
            practice_match=matched
            matched=matched or farm_match
            b,bs,mods,f=c['map'],c['set'],c['mods'],c['features']
            acc=matched['accuracy']
            nearest=matched['neighbor'];ns=nearest['score'];nf=nearest['features']
            nbs=ns.get('beatmapset',{})
            if c['score']:
                s=c['score'];kind='retry'
                reason=f'Your previous pass: {s["accuracy"]*100:.2f}% and {miss_count(s)} misses. Work on a cleaner run rather than an FC or pp target.'
            else:
                kind='new'
                reason=f'Similar to {nbs.get("title","a reliable play")} [{ns["beatmap"].get("version","")}] +{label(ns.get("mods",[]))}: {nf["stars"]:.2f}★, {ns["accuracy"]*100:.2f}% accuracy, {coverage(ns,nf)*100:.0f}% combo. AR stays within the reading range inferred from your clean passes. Only one measured demand may increase slightly.'
            if any(m['acronym']=='DA' for m in mods):
                reason+=' In lazer enable Difficulty Adjust and set only AR to '+str(round(f['ar'],1))+'. Keep the original speed, OD, CS and HP.'
            if c.get('transfer'):
                reason+=' This setup has limited direct evidence. The match uses actual physical demands from your clean plays; treat it as a calibration trial, not established ability.'
            style='Aim leaning' if f['aim']>f['speed']*1.12 else 'Speed leaning' if f['speed']>f['aim']*1.12 else 'Balanced'
            row={'id':b['id'],'key':str(b['id'])+'|'+key[1],'modKey':key[1],'setId':bs['id'],'title':bs['title'],'artist':bs['artist'],
                         'version':b['version'],'mapper':bs.get('creator',''),'stars':round(f['stars'],2),
                         'baseStars':round(f['baseStars'],2),'bpm':round(f['bpm']),'length':round(f['length']),
                         'mods':label(mods),'modSettings':mods,'setupInstructions':('Difficulty Adjust: AR '+str(round(f['ar'],1))+'; leave other settings unchanged. No speed mods.' if any(m['acronym']=='DA' for m in mods) else 'Use '+label(mods)+'.'),'accuracy':acc,'kind':kind,'style':style,
                         'reason':reason,'cover':bs.get('covers',{}).get('cover@2x',''),
                         'url':f'https://osu.ppy.sh/beatmapsets/{bs["id"]}#osu/{b["id"]}',
                         
                         'priority':matched['suitability'],'focus':matched['focus'],'stage':matched['stage'],'goal':matched['goal'],
                         'fit': 'Known attempt' if c['score'] else 'Similar clean plays',
                         'provisional':bool(c.get('transfer')),'support':matched['support'],'ar':round(f['ar'],1),'od':round(f['od'],1),'cs':round(f['cs'],1),
                         'evidence':{'title':nbs.get('title',''),'version':ns['beatmap'].get('version',''),
                                     'stars':round(nf['stars'],2),'accuracy':round(ns['accuracy']*100,2),
                                     'comboPercent':round(coverage(ns,nf)*100),'id':ns['beatmap']['id']}}
            if practice_match:rows.append(row)
            if farm_match:
                target=farm_match['accuracy']
                pp=rosu.Performance(mods=mods,lazer=True,accuracy=target,misses=0).calculate(f['_difficulty']).pp
                gain=gain_fn(best,b['id'],pp)
                if gain>.1:
                    confidence=math.exp(-farm_match['similarity']*.6)*min(1,farm_match['support']/4)
                    farm_rows.append(dict(row,accuracy=target,estimatedPP=round(pp,1),estimatedGain=round(gain,2),
                        priority=gain*confidence,stage='Farm',focus='PP gain',provisional=False,
                        goal=f'Full combo at {target:.1f}% accuracy.',
                        reason=f'A full combo at {target:.1f}% is estimated at {pp:.1f} pp, adding about {gain:.2f} weighted profile pp after replacing any better existing score on this map. Ranked by estimated gain adjusted for similarity and supporting clean plays; this is a target, not a guaranteed result.'))
        except (ValueError,RuntimeError,OSError):skipped+=1
    rows.sort(key=lambda r:r['priority'],reverse=True)
    buckets=collections.defaultdict(list)
    for row in rows:
        buckets[row['mods']].append(row)
    mixed=[]
    while any(buckets.values()):
        for key in sorted(buckets,key=lambda k:(k!='NM',k)):
            if buckets[key]:mixed.append(buckets[key].pop(0))
    rows=mixed
    # Diversity: one map ID and at most two difficulties per song. No wall of the same farm set.
    diverse=[];song_count=collections.Counter();stage_count=collections.Counter();used_ids=set()
    for row in rows:
        song=(row['artist'].casefold(),row['title'].casefold())
        if row['id'] in used_ids or song_count[song]>=1 or (row['stage']=='Stretch' and stage_count['Stretch']>=3):continue
        diverse.append(row);used_ids.add(row['id']);song_count[song]+=1;stage_count[row['stage']]+=1
        if len(diverse)>=12:break
    profiles=[{'mods':label(setup_mods[key]),
               'ceiling':round(ceiling(groups[key],min(cap,float(config.get('mod_caps',{}).get(key,cap)))),2),'provisional':key in transfer_keys,'count':0 if key in transfer_keys else len(groups[key]),'minAR':reading_floors[key],
               'accuracy':round(statistics.median(a['score']['accuracy']*100 for a in groups[key]),2)} for key in group_order if len(groups[key])>=2]
    comfortable=max((p['ceiling'] for p in profiles),default=cap)
    warning='Map discovery was unavailable; only known attempts were checked.' if discovery_failed else None
    if not diverse:warning='No practice maps meet your reading and skill limits. Collect more comfortable passes, then refresh.'
    farm_rows.sort(key=lambda row:row['priority'],reverse=True)
    farms=[];farm_ids=set()
    for row in farm_rows:
        if row['id'] in farm_ids:continue
        farms.append(row);farm_ids.add(row['id'])
        if len(farms)>=12:break
    return {'algorithmVersion':VERSION,'demo':False,'user':user['username'],'userId':user['id'],
            'profilePP':round(user.get('statistics',{}).get('pp',0)), 'maps':diverse,
            'minAR':min(reading_floors.values(),default=9.5),'mode':'practice','maxStars':cap,'comfortableCeiling':round(comfortable,2),'profiles':profiles,
            'sample':len(samples),'cleanSample':sum(len(v) for k,v in groups.items() if k not in transfer_keys),'bestCount':len(best),
            'warning':warning,'skipped':skipped,'rejected':dict(rejected),
            'farmMaps':farms,'farmWarning':None if farms else 'No supported maps offer a positive estimated pp gain within your current reading and difficulty limits.',
            'summary':'Practice uses readable maps, nearby clean passes and at most one modest challenge. Farm estimates FC pp and weighted profile gain from the same playable pool, excluding unranked adjustments and unfamiliar mod trials. Calculator estimates may differ from live osu! pp and exclude bonus pp.'}

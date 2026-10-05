"""Evidence-bounded training sessions assembled from already checked maps."""
import statistics
import recommender as r

def mod_key(mods):
    normalized=[]
    for mod in r.normal_mods(mods):
        if mod['acronym']=='CL':continue
        value=dict(mod)
        if value['acronym']=='NC':value['acronym']='DT'
        if value.get('settings')=={'speed_change':1.5}:value.pop('settings')
        normalized.append(value)
    return r.signature(normalized)

def session(maps,best,recent):
    if not maps:return None
    established=[m for m in maps if not m['provisional']]
    pool=established or maps
    scores={}
    for s in best+recent:
        if s.get('beatmap'):
            scores.setdefault(s['beatmap']['id'],[]).append(s)
    clean=[s for s in best if s.get('passed') and s.get('accuracy',0)>=.945 and r.miss_count(s)<=1]
    median=statistics.median(s['accuracy']*100 for s in clean) if clean else None
    focus='Accuracy control' if median is not None and median<98 else 'Consistency'
    if focus=='Accuracy control':
        explanation=f'Your clean reference scores have a median accuracy of {median:.1f}%. Start with timing control on readable maps before raising physical difficulty.'
        instruction='Complete each map twice, listening for uneven tapping and noting where 100s appear. Compare both runs rather than keeping only the better score.'
    else:
        explanation='Use complete, readable runs to test whether clean sections hold together across a whole map. Score summaries cannot establish a specific pattern weakness.'
        instruction='Complete each map twice without restarting after a miss. Notice whether errors recur in the same section or move between runs.'
    used=set()
    def take(values,n):
        out=[]
        for m in values:
            if m['id'] not in used:out.append(m);used.add(m['id'])
            if len(out)>=n:break
        return out
    warm=take(sorted(pool,key=lambda m:(m['stage']=='Stretch',m['stars'],m['length'])),2)
    if focus=='Accuracy control':
        ordered=sorted(pool,key=lambda m:(m['stage']=='Stretch',-m['support'],abs(m['length']-100)))
    else:ordered=sorted(pool,key=lambda m:(m['stage']=='Stretch',-m['length'],-m['support']))
    drill=take(ordered,3)
    check=take(sorted(pool,key=lambda m:(m['id'] not in scores,m['stage']=='Stretch',-m['support'])),1)
    blocks=[('warm','Warm up','Play each once; use a relaxed grip and finish the run.',warm),
            ('focus',focus,instruction,drill),
            ('check','Check transfer','Play once without a retry and compare with the focused block. Return to this map next session under the same mods.',check)]
    items=[]
    for role,title,instruction,rows in blocks:
        for m in rows:
            matching=[s for s in recent if s.get('beatmap',{}).get('id')==m['id'] and mod_key(s.get('mods',[]))==m['modKey']]
            attempts=[{'accuracy':round(s.get('accuracy',0)*100,2),'misses':r.miss_count(s),'passed':bool(s.get('passed'))} for s in matching[:3]]
            items.append({'key':m['key'],'role':role,'title':title,'instruction':instruction,'attempts':attempts})
    minutes=round(sum(m['length']*(2 if role=='focus' else 1) for role,_,_,rows in blocks for m in rows)/60)
    return {'focus':focus,'evidence':explanation,'minutes':minutes,'items':items,
            'review':'Refresh after playing to see your latest attempts. Keep the same mods when comparing runs; look for fewer misses with steady accuracy across several complete plays, then try a different map. Move on after two focused attempts, and lower the challenge if you lose the patterns.'}

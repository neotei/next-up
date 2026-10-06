"""A compact, stable-mod practice route with explicit play instructions."""
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

def session(maps,best,recent,diagnosis=None):
    if not maps:return None
    pool=[m for m in maps if not m['provisional']] or maps
    focus=(diagnosis or {}).get('focus','Balanced control')
    ordered=sorted(pool,key=lambda m:(m['focus']!=focus,m['stage']=='Trial',-m['priority']))
    lead=ordered[0]
    # A warm-up should prepare the session's setup, not switch to unfamiliar reading.
    same=[m for m in pool if m['modKey']==lead['modKey']]
    warm=sorted(same,key=lambda m:(m['stars']>lead['stars'],abs(m['ar']-lead['ar'])>.35,-m['accuracy'],m['stars']))[0]
    used={warm['id']}
    drills=[]
    for m in ordered:
        if m['id'] in used or m['modKey']!=lead['modKey']:continue
        drills.append(m);used.add(m['id'])
        if len(drills)==2:break
    check=next((m for m in sorted(same,key=lambda m:(m['stage']=='Stretch',abs(m['stars']-lead['stars']),-m['support'])) if m['id'] not in used),None)
    route=[('warm','Warm up',1,'Finish one relaxed run before moving to the focused maps.',warm)]
    route += [('focus',f'Train {i+1}',2,'Play twice without restarting, then compare your accuracy and misses.',m) for i,m in enumerate(drills)]
    if check:route.append(('check','Check progress',1,'Play once without a retry to see whether the same control carries over.',check))
    items=[]
    for role,title,plays,instruction,m in route:
        matching=[s for s in recent if s.get('beatmap',{}).get('id')==m['id'] and mod_key(s.get('mods',[]))==m['modKey']]
        attempts=[{'id':s.get('id'),'accuracy':round(s.get('accuracy',0)*100,2),'misses':r.miss_count(s),'passed':bool(s.get('passed'))} for s in matching[:3]]
        items.append({'key':m['key'],'role':role,'title':title,'plays':plays,'instruction':instruction,'attempts':attempts})
    return {'version':2,'focus':focus,'displayFocus':{'Tapping demand':'Tapping control','Long-run consistency':'Staying consistent','Balanced control':'Build control','Reading range':'Reading patterns','Dense patterns':'Busy patterns'}.get(focus,focus),'evidence':(diagnosis or {}).get('evidence','More comparable results are needed before choosing a specific weakness.'),
            'minutes':max(1,round(sum(m['length']*plays for _,_,plays,_,m in route)/60)),'items':items,
            'review':'Refresh your scores after the session to compare complete runs under the same mods. Fewer misses with steady accuracy across different maps is a useful sign of progress.'}

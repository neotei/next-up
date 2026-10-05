"""Public beatmap descriptors, not player technique or replay measurements."""
import math
import statistics

def describe(path,rate=1):
    section='';objects=[];tempos=[]
    for line in path.read_text(encoding='utf-8-sig',errors='replace').splitlines():
        line=line.strip()
        if line.startswith('['):section=line
        if not line or line.startswith('//'):continue
        parts=line.split(',')
        try:
            if section=='[TimingPoints]' and len(parts)>=7 and parts[6]=='1' and float(parts[1])>0:
                tempos.append(60000/float(parts[1])*rate)
            if section=='[HitObjects]' and len(parts)>=5:
                kind=int(parts[3]);objects.append((int(parts[2])/rate,int(parts[0]),int(parts[1]),bool(kind&1),bool(kind&8)))
        except ValueError:continue
    gaps=[];runs=[];run=[];jumps=[]
    for a,b in zip(objects,objects[1:]):
        gap=b[0]-a[0]
        if gap<=0 or a[4] or b[4]:run=[];continue
        gaps.append(gap);jumps.append(math.hypot(b[1]-a[1],b[2]-a[2]))
        # Consecutive circles only, regular spacing, excludes slider travel/ticks.
        if a[3] and b[3] and 35<=gap<=250:
            if run and abs(gap-statistics.median(run))>statistics.median(run)*.12:
                if len(run)>=3:runs.append(run)
                run=[]
            run.append(gap)
        else:
            if len(run)>=3:runs.append(run)
            run=[]
    if len(run)>=3:runs.append(run)
    burst=[15000/statistics.median(v) for v in runs]
    sustained=[15000/statistics.median(v) for v in runs if len(v)>=15]
    return {'burstBpm':round(max(burst,default=0),2),'streamBpm':round(max(sustained,default=0),2),
            'streamNotes':max((len(v)+1 for v in runs),default=0),
            'maxMapBpm':round(max(tempos,default=0),2),
            'jumpDistance':round(statistics.median(jumps) if jumps else 0,2),
            'rhythmVariance':round(statistics.pstdev(gaps)/max(1,statistics.mean(gaps)) if gaps else 0,3)}

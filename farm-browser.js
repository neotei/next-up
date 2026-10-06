/* Farm catalogue ranking is local; the shared map data contains no player scores. */
(function(root){
 const interpolate=(curve,acc)=>{const points=Object.keys(curve).map(Number).sort((a,b)=>a-b);for(let i=1;i<points.length;i++){const lo=points[i-1],hi=points[i];if(acc<=hi)return curve[lo]+(curve[hi]-curve[lo])*(acc-lo)/(hi-lo);}return curve[points.at(-1)];};
 function gain(best,id,pp){const old=best.map(x=>x.pp).sort((a,b)=>b-a),existing=best.find(x=>x.id===id)?.pp||0;if(pp<=existing)return 0;const next=best.filter(x=>x.id!==id).map(x=>x.pp).concat(pp).sort((a,b)=>b-a);const total=values=>values.reduce((n,v,i)=>n+v*.95**i,0);return Math.max(0,total(next)-total(old));}
 function fit(features,refs){
  if(!refs?.length)return .12;
  let best=0;
  for(const ref of refs){const f=ref.features;let loss=((features.ar-f.ar)/.85)**2+((features.cs-f.cs)/1.2)**2+Math.max(0,features.stars-f.stars)**2;
   for(const axis of ['aim','speed','density'])loss+=(Math.max(0,features[axis]/Math.max(.1,f[axis])-1)/.25)**2;
   loss+=(Math.max(0,features.length/Math.max(20,f.length)-1)/1.5)**2;
   for(const axis of ['burstBpm','streamBpm'])loss+=(Math.max(0,(features[axis]||0)-(f[axis]||0)-5)/35)**2;
   if(features.streamNotes>=16&&f.streamNotes<16)loss+=6;
   loss+=Math.abs((features.slider||0)-(f.slider||0));best=Math.max(best,Math.exp(-loss/3));
  }
  return best;
 }
 function decorate(library,result){
  const matched=new Map((result.farmMaps||[]).map(m=>[m.key,m])),best=result.farmBest||[];
  const rows=library.map(item=>{const f=item.features,known=matched.get(item.key),pp=known?.estimatedPP??item.curve['99'];const delta=known?.estimatedGain??gain(best,item.id,pp),personalFit=known?Math.max(.6,known.confidence):fit(f,result.farmReferences?.[item.modKey]);
   const useful=Math.min(1,delta/Math.max(1,(result.farmTargets?.benchmarkPP||100)*.02));
   const priority=item.farmScore*(.25+.75*personalFit)*(.1+.9*useful);
   return {...item,stars:f.stars,baseStars:f.baseStars,ar:f.ar,od:f.od,cs:f.cs,bpm:Math.round(f.bpm),length:Math.round(f.length),burstBpm:f.burstBpm,streamBpm:f.streamBpm,streamNotes:f.streamNotes,
    cover:`https://assets.ppy.sh/beatmaps/${item.setId}/covers/cover@2x.jpg`,url:`https://osu.ppy.sh/beatmapsets/${item.setId}#osu/${item.id}`,
    kind:best.some(x=>x.id===item.id)?'retry':'new',accuracy:99,estimatedPP:pp,estimatedGain:delta,maxPP:item.curve['100'],highAccuracyPP:item.curve['99'],
    referenceOnly:!known,fitScore:Math.round(personalFit*100),provisional:!known,confidence:0,priority,higherPriority:delta*Math.sqrt(personalFit)*Math.sqrt(item.farmScore/100)/Math.sqrt((f.length+12)/60),
    gainPerMinute:delta*personalFit/((f.length+12)/60),reason:'The farm score combines community overweightness with short repeatable attempts and relative PP yield. This catalogue entry has no close enough personal FC forecast, so its 99% FC value is a reference target, not a prediction of your accuracy.',
    ...known,farmScore:item.farmScore,rawFarmScore:item.farmEvidence,
    browsePriority:priority,browseHigherPriority:delta*Math.sqrt(personalFit)*Math.sqrt(item.farmScore/100)/Math.sqrt((f.length+12)/60)};
  });
  return rows;
 }
 function defaults(result){const bands=result.performance?.modProfiles||[],stars=bands.map(p=>p.starBand[1]),ar=bands.map(p=>p.arBand[1]);return {minStars:stars.length?Math.max(1,Math.min(...stars)-1):1,maxStars:stars.length?Math.min(12,Math.max(...stars)+1):8,minAR:ar.length?Math.max(0,Math.min(...ar)-.7):0,maxAR:ar.length?Math.min(11,Math.max(...ar)+.7):11,minPP:Math.round(result.farmTargets?.minScorePP||0),maxSeconds:180,maxBPM:0,matchedOnly:false,hidden:[]};}
 function select(rows,limits,mode,query=''){const q=query.toLowerCase().trim();return rows.filter(m=>m.stars>=limits.minStars&&m.stars<=limits.maxStars&&m.ar>=limits.minAR&&m.ar<=limits.maxAR&&m.highAccuracyPP>=limits.minPP&&(!limits.maxSeconds||m.length<=limits.maxSeconds)&&(!limits.maxBPM||m.bpm<=limits.maxBPM)&&(!limits.matchedOnly||!m.referenceOnly)&&!limits.hidden.includes(m.key)&&(!q||`${m.title} ${m.artist} ${m.version}`.toLowerCase().includes(q))).sort((a,b)=>mode==='higher'?b.browseHigherPriority-a.browseHigherPriority:mode==='rate'?b.gainPerMinute-a.gainPerMinute:b.browsePriority-a.browsePriority);}
 const api={interpolate,gain,fit,decorate,defaults,select};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.FarmBrowser=api;
})(typeof window!=='undefined'?window:this);

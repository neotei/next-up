const $=s=>document.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url=value=>{try{let u=new URL(value);return u.protocol==='https:'?u.href:'';}catch{return '';}};
const duration=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
const modName=m=>m.modSettings?.some(x=>x.acronym==='DA')?'AR adjusted':m.mods==='NM'?'No Mod':m.mods;
function ppMeter(m){return `<div class="pp-meter"><div class="pp-max"><span>100% FC</span><strong>${m.maxPP?.toFixed(0)||'...'}<small> pp</small></strong></div><div class="pp-predicted"><span>${m.accuracy.toFixed(1)}% FC${m.referenceOnly?' / ref':''}</span><strong>${m.estimatedPP.toFixed(0)}<small> pp</small></strong></div></div>`;}
function practiceText(m){
 if(section==='farm')return m.referenceOnly?`+${m.estimatedGain.toFixed(1)} profile pp if you reach 99% FC`:`+${m.estimatedGain.toFixed(1)} profile pp at ${m.accuracy.toFixed(1)}% FC`;
 const goal=m.goal||`Complete the run around ${m.accuracy.toFixed(1)}% accuracy, then compare both attempts.`;
 return m.modSettings?.some(x=>x.acronym==='DA')?`Use Difficulty Adjust at AR ${m.ar} with other settings unchanged, then ${goal.charAt(0).toLowerCase()+goal.slice(1)}`:goal;
}
let section=localStorage.getItem('next-up-section')==='farm'?'farm':'practice';
let farmMode=localStorage.getItem('next-up-farm-mode')||'efficient',visibleCount=30;
if(!['efficient','higher','rate'].includes(farmMode))farmMode='efficient';
let publicLibrary=null,libraryRows=[],libraryResult=null,libraryLoading=false,libraryError='',farmLimits=null,limitsUser=null,farmQuery='';
const limitsKey=()=>`next-up-farm-limits-${result?.userId}`;
function saveFarmLimits(){try{localStorage.setItem(limitsKey(),JSON.stringify(farmLimits));}catch{}}
function prepareLibrary(){
 if(!result){libraryRows=[];libraryResult=null;farmLimits=null;limitsUser=null;return;}
 if(limitsUser!==result.userId){limitsUser=result.userId;farmLimits=FarmBrowser.defaults(result);try{let saved=JSON.parse(localStorage.getItem(limitsKey()));if(saved&&['minStars','maxStars','minAR','maxAR','minPP','maxSeconds','maxBPM'].every(k=>Number.isFinite(saved[k]))&&saved.minStars<=saved.maxStars&&saved.minAR<=saved.maxAR)farmLimits={...farmLimits,...saved,hidden:Array.isArray(saved.hidden)?saved.hidden:[]};}catch{} syncLimits();}
 if(publicLibrary&&libraryResult!==result){libraryRows=FarmBrowser.decorate(publicLibrary,result);libraryResult=result;}
}
function syncLimits(){if(!farmLimits)return;for(const name of ['minStars','maxStars','minAR','maxAR','minPP','maxSeconds','maxBPM'])$('#farm-limits-form').elements[name].value=Number(farmLimits[name].toFixed(1));$('#farm-limits-form').elements.matchedOnly.checked=farmLimits.matchedOnly;}
async function loadLibrary(){if(publicLibrary||libraryLoading)return;libraryLoading=true;try{const response=await fetch('/api/farm-library');if(!response.ok)throw new Error();const data=await response.json();publicLibrary=data.maps;libraryResult=null;libraryError='';}catch{libraryError='Catalogue could not load; reload to try again.';}finally{libraryLoading=false;prepareLibrary();render();}}
const activeMaps=()=>section==='farm'?(result?(publicLibrary&&farmLimits?FarmBrowser.select(libraryRows,farmLimits,farmMode,farmQuery).filter(m=>!(result?.farmBlocked||[]).includes(m.id)):(result?.farmMaps||[]).slice().sort((a,b)=>b.priority-a.priority)):[]):(result?.maps||[]);
const activeWarning=()=>section==='farm'?(result&&!activeMaps().length?'No maps match these limits. Widen them or choose Full catalogue.':null):result?.warning;
let result=null,configured=false,busy=false,filter='all',modFilter='all',selected=null,expanded=new Set(),revision=null,timer;
function toast(message,sticky=false){clearTimeout(timer);$('#toast').textContent=message;$('#toast').hidden=false;if(!sticky)timer=setTimeout(()=>$('#toast').hidden=true,5500);}
async function post(path,body={}){if(window.NEXT_UP_BACKEND)return window.NEXT_UP_BACKEND.post(path,body);let response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let data=await response.json();if(!response.ok)throw new Error(data.error||'Request failed.');return data;}
let browsePractice=false,route=null,practiceMinutes=Number(localStorage.getItem('next-up-practice-minutes'))||40;
if(![20,40,60].includes(practiceMinutes))practiceMinutes=40;
const routeKey=()=>`next-up-route-${result?.userId}`;
function saveRoute(){try{localStorage.setItem(routeKey(),JSON.stringify(route));}catch{}}
function clearRoute(){route=null;try{localStorage.removeItem(routeKey());}catch{}}
function getRoute(){
 if(!result?.practiceSession)return null;
 if(!route||route.userId!==result.userId){try{route=JSON.parse(localStorage.getItem(routeKey()));}catch{route=null;}}
 const plan=result.practicePlans?.[practiceMinutes]||result.practiceSession;
 if(!route||route.userId!==result.userId||route.version!==plan.version||route.requestedMinutes!==plan.requestedMinutes||!Array.isArray(route.items)||!route.items.length||!Number.isInteger(route.index)||route.index<0||route.index>route.items.length||Date.now()-route.created>6*3600000||route.items.some(x=>!x.map||x.map.stars>result.maxStars)||route.items.slice(route.index).some(x=>!result.maps.some(m=>m.key===x.key))){
  route={version:plan.version,requestedMinutes:plan.requestedMinutes,limited:plan.limited,userId:result.userId,created:Date.now(),index:0,focus:plan.displayFocus||plan.focus,evidence:plan.evidence,minutes:plan.minutes,
   items:plan.items.map(item=>({...item,map:result.maps.find(m=>m.key===item.key),status:null,baselineIds:item.attempts.map(a=>a.id)})).filter(x=>x.map)};
  saveRoute();
 }
 return route;
}
function mapFacts(m){return `<span class="mod">${esc(modName(m))}</span><span>${m.stars.toFixed(2)} ★</span><span>${duration(m.length)}</span><span>AR ${m.ar.toFixed(1)}</span>`;}
function renderTraining(){
 const el=$('#training-session'),session=getRoute();
 el.hidden=section!=='practice'||browsePractice||!session;if(el.hidden)return;
 const done=session.index>=session.items.length,item=session.items[session.index];
 const signature=JSON.stringify([session,result.practiceAttempts,busy]);
 if(el.dataset.session===signature)return;el.dataset.session=signature;
 const steps=session.items.map((x,i)=>({x,i})).slice(Math.max(0,session.index-2),Math.max(5,session.index+3)).map(({x,i})=>`<button data-step="${i}" ${i>session.index?'disabled':''} class="route-stop ${i===session.index?'current':''} ${x.status?'visited':''}" aria-current="${!done&&i===session.index?'step':'false'}"><b>${x.status==='done'?'✓':x.status==='skipped'?'↷':i+1}</b><span>${esc(x.title)}<small>${x.plays} ${x.plays===1?'run':'runs'}</small></span></button>`).join('');
 const heading=`<div class="session-top"><div><h2>${esc(session.focus)}</h2></div><span>${Math.min(session.index+1,session.items.length)} / ${session.items.length} · ~${session.minutes} min <details class="route-tools"><summary title="Session options" aria-label="Session options">•••</summary><button data-route="restart">Restart route</button></details></span></div><nav class="session-route" aria-label="Session steps">${steps}</nav>`;
 if(done){
  const rows=session.items.map(x=>{
   const fresh=(result.practiceAttempts?.[x.key]||[]).filter(a=>!x.baselineIds.includes(a.id)&&a.time*1000>=session.created);
   return `<li><span>${esc(x.map.title)}<small>${esc(modName(x.map))} · ${x.status==='skipped'?'Skipped':'Marked played'}</small></span><strong>${fresh.length?fresh.map(a=>a.passed?`${a.accuracy.toFixed(1)}% / ${a.misses} misses`:'Failed run').join('<br>'):'No new score'}</strong></li>`;
  }).join('');
  el.innerHTML=heading+`<div class="session-finished"><h3>Session complete</h3><ul class="session-results">${rows}</ul><div class="session-actions"><button class="route-primary" data-route="sync" ${busy?'disabled':''}>${busy?'Updating scores…':'Refresh scores'}</button><button data-route="restart">Play again</button></div><details class="review-info"><summary>About these results</summary><p>Refresh to find new submitted scores. Marking a map played saves your place without verifying a score.</p></details></div>`;
  return;
 }
 const m=item.map,attempts=result.practiceAttempts?.[item.key]||item.attempts;
 el.innerHTML=heading+`${session.index>0&&session.index%5===0?'<p class="session-pool-note">Take a short break before the next block.</p>':''}${session.limited?'<p class="session-pool-note">This route uses all matching maps available for this setup.</p>':''}<div class="session-player"><svg class="stage-art" viewBox="0 0 1000 330" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs><linearGradient id="stageSilver" x2=".8" y2="1"><stop stop-color="#dae8e1"/><stop offset=".45" stop-color="#536b73"/><stop offset=".5" stop-color="#b7c8c8"/><stop offset="1" stop-color="#324b58"/></linearGradient><linearGradient id="stagePink"><stop stop-color="#da9cba"/><stop offset="1" stop-color="#694d71"/></linearGradient></defs><g fill="none" stroke="#9ab7bc" opacity=".16"><path d="M-40 210C160 10 470-40 710 96S930 340 1100 64M-40 223C160 23 470-27 710 109S930 353 1100 77M-40 236C160 36 470-14 710 122S930 366 1100 90"/><ellipse cx="272" cy="195" rx="263" ry="120" transform="rotate(-23 272 195)"/><ellipse cx="272" cy="195" rx="276" ry="132" transform="rotate(-23 272 195)"/></g><path d="M670-40C632 45 700 88 839 106S1024 155 1040 257" fill="none" stroke="#122936" stroke-width="22"/><path d="M670-40C632 45 700 88 839 106S1024 155 1040 257" fill="none" stroke="url(#stageSilver)" stroke-width="13"/><path d="M708-40C673 41 721 56 849 78S1050 120 1080 236" fill="none" stroke="url(#stagePink)" stroke-width="6"/><g transform="translate(921 268) rotate(-28)"><circle r="95" fill="#152e38" stroke="#7f9ea7" stroke-width="2"/><circle r="86" fill="none" stroke="#314c59" stroke-width="14"/><circle r="70" fill="none" stroke="#b6cbc7" stroke-width="1" stroke-dasharray="1 9"/><circle r="58" fill="none" stroke="#64828b" stroke-width="2"/><path d="M-43-38A58 58 0 0 1 49-31M40 41A58 58 0 0 1-45 35" fill="none" stroke="#c4d993" stroke-width="4"/><circle r="34" fill="none" stroke="#8a6681" stroke-width="14"/><circle r="21" fill="none" stroke="#bdcfc7"/><circle r="8" fill="#49626a"/></g><path d="M0 305h61l20-20h72M30 321h52l20-20h161" fill="none" stroke="#aec883" opacity=".55"/><g fill="#d995b7"><rect x="23" y="17" width="3" height="18"/><rect x="29" y="17" width="3" height="18"/><rect x="35" y="17" width="3" height="18"/></g></svg><div class="session-art">${url(m.cover)?`<img src="${esc(url(m.cover))}" alt="" referrerpolicy="no-referrer">`:''}</div><div class="session-track"><h3>${esc(m.title)}</h3><p class="session-diff">${esc(m.version)} <span>/ ${esc(m.artist)}</span></p><div class="session-facts">${mapFacts(m)}</div><div class="session-task"><div class="practice-readout"><span><b>${item.plays}</b> ${item.plays===1?'run':'runs'}</span><span><b>${m.accuracy.toFixed(1)}%</b> target</span></div><p>${item.plays===1?(session.index===0?'Warm up without restarting.':'Compare accuracy and misses with your earlier runs.'):'Play both runs without restarting; compare accuracy and misses.'}</p></div><div class="session-actions"><a class="play-button" href="osu://b/${Number(m.id)}">▶ Open in osu!</a><button class="route-primary" data-route="next" title="Mark this map played and advance" aria-label="Mark played and go to next map">Next →</button></div><details class="session-secondary"><summary>Details</summary><button data-route="skip">Skip this map</button><button data-route="hard" ${busy?'disabled':''}>Too hard</button><a href="${esc(url(m.url))}" target="_blank" rel="noopener noreferrer">Map page</a><div class="session-help"><p>${esc(item.instruction)}</p><p>${esc(session.evidence)}</p><p>${esc(m.reason)}</p>${attempts.length?`<p>Recent submitted runs: ${attempts.map(a=>a.passed?`${a.accuracy.toFixed(1)}% with ${a.misses} misses`:'Failed run').join(' · ')}</p>`:''}<p>Your place is saved in this browser. Use the displayed mods in lazer; the accuracy target is an estimate.</p></div></details></div></div>`;
}
function render(selectionOnly=false,append=false){
 prepareLibrary();
 const maps=activeMaps(),warning=activeWarning(),list=maps.filter(m=>(filter==='all'||m.kind===filter)&&(modFilter==='all'||m.mods===modFilter)),first=list.find(m=>m.key===selected)||list[0];
 $('#farm-mode').hidden=section!=='farm'||!result;
 document.querySelectorAll('[data-farm-mode]').forEach(b=>{const active=b.dataset.farmMode===farmMode;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 $('#farm-mode-note').textContent=publicLibrary?`${publicLibrary.length.toLocaleString()} setups`:'Loading catalogue…';
 $('#farm-search').hidden=section!=='farm'||!result;
 $('#catalogue-status').textContent=libraryError;
 $('#practice-length').hidden=section!=='practice'||!result||browsePractice;
 document.querySelectorAll('[data-minutes]').forEach(b=>{const active=Number(b.dataset.minutes)===practiceMinutes;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 $('#load-more').hidden=section!=='farm'||list.length<=visibleCount;
 $('#loaded-count').textContent=section==='farm'&&list.length?`${Math.min(visibleCount,list.length)} / ${list.length}`:'';
 document.querySelectorAll('[data-section]').forEach(b=>{const active=b.dataset.section===section;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 $('#section-description').textContent=section==='farm'?'Browse farm maps.':'Choose a session and work through it.';
 $('#map-heading').textContent=section==='farm'?'Farm':browsePractice?'Map library':'Practice';
 $('.intro').hidden=!!result;
 $('#practice-library').hidden=section!=='practice'||!result;
 $('#practice-count').textContent=`(${result?.maps.length||0})`;
 $('#browse-practice').hidden=browsePractice;$('#return-session').hidden=!browsePractice;
 $('#browse-practice').setAttribute('aria-expanded',browsePractice);
 $('#table-title').textContent=section==='farm'?'100% FC / personal or reference FC':'Map library';
 $('#method-details').textContent=section==='farm'?'Farm score is our 0-100 catalogue score: 75% community overweightness percentile, 15% short-attempt value and 10% PP yield relative to the mod/star band. Its community component uses osu!pps top-score frequency adjusted by player population and map age. Sorting also accounts for similarity to your successful plays and meaningful profile gains. Gain/min and Higher PP are alternative rankings; use Limits to browse beyond the suggested range. Max pp means a 100% FC, while personal predicted pp assumes an FC at the displayed accuracy; values labelled ref are 99% FC references without a personal accuracy forecast; both exclude bonus pp. The likelihood is a local heuristic rather than a validated probability.':'Practice compares recent passes and complete failures under the same mods, with newer results carrying more weight. A focus needs several comparable observations across different maps; otherwise the session uses balanced control. Each candidate holds other demands stable while introducing a manageable challenge. Early quits do not supply full-map accuracy, and UR requires replay hit errors.';

 if(result){
  const coverage=result.featureCoverage,targets=result.farmTargets;
  const bands=result.performance?.modProfiles||[];
  $('#method-details').innerHTML=`<p>${esc($('#method-details').textContent)}</p>${targets&&section==='farm'?`<p>Farm score floor: ${targets.minScorePP.toFixed(0)} pp, based on your top-score distribution. Targets must also offer at least +${targets.minGain.toFixed(1)} estimated weighted pp.</p>`:''}${coverage?`<p>Top-play features matched: ${coverage.matchedBest} / ${coverage.supportedBest}. More references may be learned in the background.</p>`:''}${bands.length?`<table class="profile-bands"><thead><tr><th>Mods</th><th>Typical AR</th><th>Bursts</th><th>Streams</th></tr></thead><tbody>${bands.map(p=>`<tr><td>${esc(p.modKey==='[]'?'NM':JSON.parse(p.modKey).map(x=>x.acronym).join('+'))}</td><td>${p.arBand[0].toFixed(1)}–${p.arBand[2].toFixed(1)}</td><td>${p.burstBpmBand[2]?Math.round(p.burstBpmBand[2])+' BPM':'n/a'}</td><td>${p.streamBpmBand[2]?Math.round(p.streamBpmBand[2])+' BPM':'n/a'}</td></tr>`).join('')}</tbody></table><p>BPM values describe patterns in successful maps, rather than a measured personal maximum. UR requires replay hit errors.</p>`:''}`;
 }

 renderTraining();
 $('#total-count').textContent=maps.length;
 const setups=[...new Set(maps.map(m=>m.mods))];
 $('#mod-tabs').innerHTML=['all',...setups].map(m=>`<button data-mod="${esc(m)}" class="${modFilter===m?'active':''}" aria-pressed="${modFilter===m}">${m==='all'?'Any mods':esc(m.startsWith('NM + DA')?'Normal speed':m)}</button>`).join('');
 document.querySelectorAll('.filter').forEach(b=>{let active=b.dataset.filter===filter;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 $('#profile-summary').textContent=result?`${result.user} / lazer`:'osu!standard / lazer';
 $('#notice').classList.toggle('live',!!result);
 $('#notice').querySelector('span').textContent=result?'Your range':configured?'No current list':'Not connected';
 $('#notice').querySelector('p').textContent=result?(warning||`${result.profiles.filter(p=>!p.provisional).slice(0,2).map(p=>`${p.mods}: AR ${p.minAR.toFixed(1)}+`).join(' · ')}`):configured?'Refresh to rebuild your recommendations from reliable plays.':'Connect your osu! profile to find maps in your range.';
 $('#connect-banner').hidden=configured;
 $('#notice').hidden=!!result&&!warning;
 $('#updated').textContent=result?.updated?new Date(result.updated*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'';
 $('#limit-form').hidden=!configured;
 if(result&&!$('#star-limit').matches(':focus'))$('#star-limit').value=result.maxStars;
 $('#method').textContent=result?`${result.summary} Evidence: ${result.historyCoverage?.recent??result.sample} recent scores, ${result.matchedSample} matched observations. UR needs replay hit errors.`:'Recommendations compare recent outcomes under the same mods.';
 $('#empty').hidden=!!first;
 $('.crate').hidden=!first;
 $('.selection-layout').hidden=!first||(section==='practice'&&!browsePractice&&!!result?.practiceSession);
 $('.list-top').hidden=!configured||(section==='practice'&&!browsePractice&&!!result?.practiceSession);
 $('.workspace-tools').hidden=!configured;
 if(!first){$('#featured').innerHTML='';$('#rows').innerHTML='';$('#empty').innerHTML=`<p>${warning?esc(warning):maps.length?(filter==='retry'?'No previously played maps match these filters.':'No new maps in this list.'):configured?'No recommendations yet. Refresh to build your list.':'Connect your profile to get started.'}</p>${maps.length?'<button id="reset-filter">Show all maps</button>':''}`;$('#reset-filter')?.addEventListener('click',()=>{filter='all';modFilter='all';render();});return;}
 $('#featured').innerHTML=`<article class="featured-card"><div class="art">${url(first.cover)?`<img src="${esc(url(first.cover))}" alt="" referrerpolicy="no-referrer">`:'<span class="no-art">Artwork unavailable</span>'}<div class="art-heading">${first.referenceOnly?'<div class="pick-label">Catalogue target</div>':first.provisional?'<div class="pick-label">Trial map</div>':''}<h2>${esc(first.title)}</h2><p class="artist">${esc(first.artist)}</p></div></div><div class="feature-info">${section==='farm'?ppMeter(first):''}<div class="feature-main"><p class="difficulty">${esc(first.version)} <span>by ${esc(first.mapper)}</span></p><div class="map-meta"><span class="stars">${first.stars.toFixed(2)} ★</span><span class="mod">${esc(modName(first))}</span><span>${duration(first.length)}</span></div></div><div class="practice-focus"><strong>${section==='farm'?`Farm score ${first.farmScore?.toFixed(0)||'...'}`:'Your goal'}</strong><p>${esc(practiceText(first))}</p></div><div class="map-actions"><a class="play-button" href="osu://b/${Number(first.id)}"><span aria-hidden="true">▶</span> Open in osu!</a><details class="farm-options"><summary>Details</summary><a class="website-link" href="${esc(url(first.url))}" target="_blank" rel="noopener noreferrer">View on website</a><button id="too-hard">${first.referenceOnly?'Hide map':'Too hard'}</button><div class="reason"><p>${esc(first.reason)}</p>${section==='farm'&&!first.referenceOnly?`<p>${first.stretch?'Higher PP stretch target. ':''}Estimated gain rate: +${(first.gainPerMinute||0).toFixed(2)} profile pp/min of attempts, allowing 12 seconds to restart after each full run. This is a ranking estimate, not a measured rate.</p><p>Estimated FC likelihood: ${Math.round((first.fcProbability||0)*100)}%, with an accuracy range of ${first.accuracyLow?.toFixed(1)}–${first.accuracyHigh?.toFixed(1)}% across comparable runs. This forecast has not been statistically calibrated.</p>`:''}${section==='farm'?`<p>Farm score: ${first.farmScore?.toFixed(1)||'n/a'} / 100; community overweightness: ${(first.rawFarmScore||0).toPrecision(3)}. ${first.referenceOnly?'99% FC is a reference, not a personal forecast.': 'Personal forecast available.'}</p>`:''}<p class="extra-stats">AR ${first.ar} · OD ${first.od} · ${duration(first.length)} · Use the shown mods</p><p>Circle bursts: ${Math.round(first.burstBpm||0)} BPM equivalent; sustained runs: ${first.streamBpm?Math.round(first.streamBpm)+' BPM equivalent':'none identified'}. These describe map patterns, not your personal speed limit.</p></div></details></div></div></article>`;
 if(!selectionOnly){const rowStart=append?$('#rows').children.length:0;const markup=(section==='farm'?list.slice(rowStart,visibleCount):list).map((m,i)=>`<article class="map-row ${section==='farm'?'farm-row':'library-row'} ${m.key===first.key?'selected':''}"><span class="rank" aria-hidden="true">${String(i+rowStart+1).padStart(2,'0')}</span><div class="row-sleeve"><span class="sleeve-disc" aria-hidden="true"></span><button class="mini-art" data-select="${esc(m.key)}" aria-label="Select artwork for ${esc(m.title)} ${esc(m.version)}">${url(m.cover)?`<img src="${esc(url(m.cover))}" alt="" loading="lazy" referrerpolicy="no-referrer">`:''}</button></div><div class="row-text"><h3 class="row-name"><button class="select-map" data-select="${esc(m.key)}" aria-label="Select ${esc(m.title)} ${esc(m.version)}">${esc(m.title)}</button></h3><div class="row-sub">${esc(m.version)}${section==='farm'?`<span class="farm-score-badge" title="Catalogue farm score out of 100">FARM <b>${m.farmScore?.toFixed(0)||'...'}</b></span>`:''}</div><div class="row-meta"><span class="stars">${m.stars.toFixed(2)} ★</span><span class="mod">${esc(modName(m))}</span><span class="track-time">${duration(m.length)}</span></div></div>${section==='farm'?ppMeter(m):`<div class="library-readout"><span>${esc(m.focus)}</span><strong>${m.accuracy.toFixed(1)}<small>%</small></strong></div>`}</article>`).join('');if(append)$('#rows').insertAdjacentHTML('beforeend',markup);else $('#rows').innerHTML=markup;}
 $('#too-hard').disabled=busy;
 $('#too-hard').addEventListener('click',async()=>{if(first.referenceOnly){farmLimits.hidden.push(first.key);saveFarmLimits();selected=null;render();return;}try{let response=await post('/api/feedback',{id:first.id,key:first.key});clearRoute();await state();toast(`This map has been removed, and its mod setup is now limited to ${response.limit.toFixed(2)}★.`);}catch(e){toast(e.message);}});
}
async function state(){try{let response=await window.NEXT_UP_BACKEND.state();let data=await response.json(),wasBusy=busy;busy=data.state.busy;configured=data.configured;$('#refresh').disabled=busy;$('#save-settings').disabled=!data.available;$('#disconnect').hidden=!configured;$('#reset-feedback').hidden=!configured;$('#limit-form button').disabled=busy;if($('#too-hard'))$('#too-hard').disabled=busy;$('#account').classList.toggle('connected',configured);$('#account-label').textContent=data.username||'Connect profile';
 let nextRevision=data.result?JSON.stringify([data.revision,data.result.updated,data.result.maps.length,data.result.maxStars]):'none';
 if(nextRevision!==revision||!!result!==!!data.result){result=data.result;revision=nextRevision;render();if(result&&!publicLibrary&&!libraryLoading)loadLibrary();}
 $('#limit-form').hidden=!configured;$('.workspace-tools').hidden=!configured;$('.list-top').hidden=!configured||(section==='practice'&&!browsePractice&&!!result?.practiceSession);$('#mod-tabs').hidden=!configured;$('#details-button').hidden=!configured;$('#empty').hidden=!configured||!!activeMaps().length;
 $('#notice').hidden=configured&&!activeWarning();$('#connect-banner').hidden=configured;
 if(!configured){$('#notice').querySelector('span').textContent='Your next practice session';$('#notice').querySelector('p').textContent='Connect your profile and we’ll pick readable maps that build on your clean lazer plays.';}
 $('#sync-status').textContent=busy?(result?'Updating history…':'Finding your maps…'):data.state.error||'';
 if(!busy&&wasBusy&&data.state.error)toast(data.state.error,true);
 if(!data.available){$('#settings-error').textContent='Sign-in is being set up. Please check back shortly.';}
}catch{toast('The connection was interrupted; try reloading the page.',true);}}
function settings(){$('#settings-error').textContent='';$('#settings-title').textContent=configured?'Your profile':'Connect your profile';$('#username').hidden=configured;document.querySelector('label[for="username"]').hidden=configured;$('#save-settings').hidden=configured;$('#reset-feedback').hidden=!configured;$('#disconnect').hidden=!configured;$('#settings').showModal();}
$('#account').addEventListener('click',settings);$('#connect-banner').addEventListener('click',settings);$('#close-settings').addEventListener('click',()=>$('#settings').close());
$('#settings-form').addEventListener('submit',e=>{e.preventDefault();location.assign('/auth/login?user_id='+encodeURIComponent($('#username').value.trim()));});
$('#reset-feedback').addEventListener('click',async()=>{try{await post('/api/reset-feedback');$('#settings').close();await post('/api/refresh');await state();}catch(e){toast(e.message);}});
$('#disconnect').addEventListener('click',async()=>{try{await post('/api/disconnect');$('#settings').close();result=null;selected=null;filter='all';modFilter='all';revision=null;render();await state();toast('Signed out; your session has been removed.');}catch(e){$('#settings-error').textContent=e.message;}});
$('#refresh').addEventListener('click',async()=>{if(!configured)return settings();try{await post('/api/refresh');await state();if(!busy)toast('Both lists are updated.');}catch(e){toast(e.message);}});
$('#limit-form').addEventListener('submit',async e=>{e.preventDefault();try{await post('/api/preferences',{max_stars:Number($('#star-limit').value)});await state();await post('/api/refresh');await state();}catch(err){toast(err.message);}});
document.querySelectorAll('.filter').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;selected=null;visibleCount=30;render();}));
$('#mod-tabs').addEventListener('click',e=>{const button=e.target.closest('[data-mod]');if(button){modFilter=button.dataset.mod;selected=null;visibleCount=30;render();}});
$('#rows').addEventListener('click',e=>{let select=e.target.closest('[data-select]'),detail=e.target.closest('[data-detail]');if(select){selected=select.dataset.select;render(true);document.querySelectorAll('#rows .map-row').forEach(row=>row.classList.toggle('selected',row.querySelector('[data-select]')?.dataset.select===selected));}else if(detail){let key=detail.dataset.detail;expanded.has(key)?expanded.delete(key):expanded.add(key);render();}});
$('#details-button').addEventListener('click',()=>{let d=$('#method-details');d.hidden=!d.hidden;$('#details-button').setAttribute('aria-expanded',!d.hidden);$('#details-button').lastElementChild.textContent=d.hidden?'+':'−';});
$('#section-switch').addEventListener('click',e=>{const button=e.target.closest('[data-section]');if(!button)return;section=button.dataset.section;visibleCount=30;browsePractice=false;localStorage.setItem('next-up-section',section);selected=null;filter='all';modFilter='all';render();});
$('#farm-mode').addEventListener('click',e=>{const button=e.target.closest('[data-farm-mode]');if(!button)return;farmMode=button.dataset.farmMode;localStorage.setItem('next-up-farm-mode',farmMode);visibleCount=30;selected=null;filter='all';modFilter='all';render();});
$('#load-more').addEventListener('click',()=>{visibleCount+=30;render(false,true);});
async function poll(){await state();setTimeout(poll,busy?350:15000);}
render();poll();
const authError=new URLSearchParams(location.search).get('auth_error');
if(authError){const messages={mismatch:'The signed-in account does not match that user ID; try again with your own ID.',denied:'osu! authorization was cancelled.',state:'The sign-in request expired; please try again.',id:'Enter a numeric osu! user ID.',unavailable:'Sign-in is being set up. Please check back shortly.',busy:'The service is busy; please try again later.',failed:'osu! sign-in could not be completed; please try again.'};toast(messages[authError]||messages.failed,true);}
if(location.search)history.replaceState(null,'',location.pathname);

$('#browse-practice').addEventListener('click',()=>{browsePractice=true;selected=null;render();});
$('#return-session').addEventListener('click',()=>{browsePractice=false;render();});
$('#training-session').addEventListener('click',async e=>{
 const button=e.target.closest('[data-route],[data-step]');if(!button||!route)return;
 if(button.dataset.step!==undefined){route.index=Number(button.dataset.step);saveRoute();render();return;}
 const action=button.dataset.route;
 if(action==='restart'){clearRoute();render();return;}
 if(action==='sync'){try{await post('/api/refresh');await state();}catch(error){toast(error.message);}return;}
 if(action==='hard'){
  const m=route.items[route.index]?.map;if(!m)return;
  try{await post('/api/feedback',{id:m.id,key:m.key});clearRoute();await state();render();toast('The session has been rebuilt at an easier limit.');}catch(error){toast(error.message);}return;
 }
 const item=route.items[route.index];if(!item)return;
 item.status=action==='skip'?'skipped':'done';route.index++;saveRoute();render();
});

$('#farm-query').addEventListener('input',e=>{farmQuery=e.target.value;visibleCount=30;selected=null;render();});
$('#farm-limits-form').addEventListener('submit',e=>{e.preventDefault();const form=e.target;const next={...farmLimits};for(const key of ['minStars','maxStars','minAR','maxAR','minPP','maxSeconds','maxBPM'])next[key]=Number(form.elements[key].value);next.matchedOnly=form.elements.matchedOnly.checked;if(next.minStars>next.maxStars||next.minAR>next.maxAR){toast('The minimum must be below the maximum.');return;}farmLimits=next;saveFarmLimits();visibleCount=30;selected=null;render();$('.farm-limits').open=false;});
$('#reset-farm-limits').addEventListener('click',()=>{farmLimits=FarmBrowser.defaults(result);syncLimits();saveFarmLimits();visibleCount=30;selected=null;render();});
$('#all-farm-limits').addEventListener('click',()=>{farmLimits={minStars:1,maxStars:12,minAR:0,maxAR:11,minPP:0,maxSeconds:0,maxBPM:0,matchedOnly:false,hidden:[]};syncLimits();saveFarmLimits();visibleCount=30;selected=null;filter='all';modFilter='all';farmQuery='';$('#farm-query').value='';render();$('.farm-limits').open=false;});
$('#practice-length').addEventListener('click',e=>{const button=e.target.closest('[data-minutes]');if(!button)return;practiceMinutes=Number(button.dataset.minutes);localStorage.setItem('next-up-practice-minutes',practiceMinutes);clearRoute();render();});
const loadObserver=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&section==='farm'&&!$('#load-more').hidden){visibleCount+=30;render(false,true);}},{rootMargin:'350px'});loadObserver.observe($('#load-more'));

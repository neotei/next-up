const $=s=>document.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url=value=>{try{let u=new URL(value);return u.protocol==='https:'?u.href:'';}catch{return '';}};
const duration=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
const modName=m=>m.modSettings?.some(x=>x.acronym==='DA')?'AR adjusted':m.mods==='NM'?'No Mod':m.mods;
function ppMeter(m){return `<div class="pp-meter"><div class="pp-max"><span>MAX FC · 100%</span><strong>${m.maxPP?.toFixed(0)||'...'}<small> pp</small></strong></div><div class="pp-predicted"><span>PREDICTED · ${m.accuracy.toFixed(1)}%</span><strong>${m.estimatedPP.toFixed(0)}<small> pp</small></strong></div></div>`;}
function practiceText(m){
 if(section==='farm')return `Your predicted FC would add about +${m.estimatedGain.toFixed(1)} profile pp.`;
 const goal=m.goal||`Complete the run around ${m.accuracy.toFixed(1)}% accuracy, then compare both attempts.`;
 return m.modSettings?.some(x=>x.acronym==='DA')?`Use Difficulty Adjust at AR ${m.ar} with other settings unchanged, then ${goal.charAt(0).toLowerCase()+goal.slice(1)}`:goal;
}
let section=localStorage.getItem('next-up-section')==='farm'?'farm':'practice';
const activeMaps=()=>section==='farm'?(result?.farmMaps||[]):(result?.maps||[]);
const activeWarning=()=>section==='farm'?result?.farmWarning:result?.warning;
let result=null,configured=false,busy=false,filter='all',modFilter='all',selected=null,expanded=new Set(),revision=null,timer;
function toast(message,sticky=false){clearTimeout(timer);$('#toast').textContent=message;$('#toast').hidden=false;if(!sticky)timer=setTimeout(()=>$('#toast').hidden=true,5500);}
async function post(path,body={}){if(window.NEXT_UP_BACKEND)return window.NEXT_UP_BACKEND.post(path,body);let response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let data=await response.json();if(!response.ok)throw new Error(data.error||'Request failed.');return data;}
let browsePractice=false,route=null;
const routeKey=()=>`next-up-route-${result?.userId}`;
function saveRoute(){try{localStorage.setItem(routeKey(),JSON.stringify(route));}catch{}}
function clearRoute(){route=null;try{localStorage.removeItem(routeKey());}catch{}}
function getRoute(){
 if(!result?.practiceSession)return null;
 if(!route||route.userId!==result.userId){try{route=JSON.parse(localStorage.getItem(routeKey()));}catch{route=null;}}
 const plan=result.practiceSession;
 if(!route||route.userId!==result.userId||route.version!==2||!Array.isArray(route.items)||!route.items.length||!Number.isInteger(route.index)||route.index<0||route.index>route.items.length||Date.now()-route.created>6*3600000||route.items.some(x=>!x.map||x.map.stars>result.maxStars)||route.items.slice(route.index).some(x=>!result.maps.some(m=>m.key===x.key))){
  route={version:2,userId:result.userId,created:Date.now(),index:0,focus:plan.displayFocus||plan.focus,evidence:plan.evidence,minutes:plan.minutes,
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
 const steps=session.items.map((x,i)=>`<button data-step="${i}" ${i>session.index?'disabled':''} class="route-stop ${i===session.index?'current':''} ${x.status?'visited':''}" aria-current="${!done&&i===session.index?'step':'false'}"><b>${x.status==='done'?'✓':x.status==='skipped'?'↷':i+1}</b><span>${esc(x.title)}<small>${x.plays} ${x.plays===1?'run':'runs'}</small></span></button>`).join('');
 const heading=`<div class="session-top"><div><span class="panel-label">PRACTICE ROUTE</span><h2>${esc(session.focus)}</h2></div><span>~${session.minutes} min <details class="route-tools"><summary>Session options</summary><button data-route="restart">Restart route</button></details></span></div><nav class="session-route" aria-label="Session steps">${steps}</nav>`;
 if(done){
  const rows=session.items.map(x=>{
   const fresh=(result.practiceAttempts?.[x.key]||[]).filter(a=>!x.baselineIds.includes(a.id)&&a.time*1000>=session.created);
   return `<li><span>${esc(x.map.title)}<small>${esc(modName(x.map))} · ${x.status==='skipped'?'Skipped':'Marked played'}</small></span><strong>${fresh.length?fresh.map(a=>a.passed?`${a.accuracy.toFixed(1)}% / ${a.misses} misses`:'Failed run').join('<br>'):'No new score yet'}</strong></li>`;
  }).join('');
  el.innerHTML=heading+`<div class="session-finished"><span class="panel-label">SESSION REVIEW</span><h3>You’ve reached the end of the route</h3><p>Refresh your scores to check the submitted runs against what you played.</p><ul class="session-results">${rows}</ul><div class="session-actions"><button class="route-primary" data-route="sync" ${busy?'disabled':''}>${busy?'Updating scores…':'Check my scores'}</button><button data-route="restart">Repeat this route</button></div><small>Marking a map played saves your place; it does not verify a score.</small></div>`;
  return;
 }
 const m=item.map,attempts=result.practiceAttempts?.[item.key]||item.attempts;
 el.innerHTML=heading+`<div class="session-player"><div class="session-art">${url(m.cover)?`<img src="${esc(url(m.cover))}" alt="" referrerpolicy="no-referrer">`:''}<span>${esc(item.title)} · ${session.index+1} / ${session.items.length}</span></div><div class="session-track"><h3>${esc(m.title)}</h3><p class="session-diff">${esc(m.version)} <span>/ ${esc(m.artist)}</span></p><div class="session-facts">${mapFacts(m)}</div><div class="session-task"><strong class="run-count">${item.plays} ${item.plays===1?'run':'runs'}</strong><p>${esc(item.instruction)}</p><span>Suggested accuracy <b>${m.accuracy.toFixed(1)}%</b></span></div><div class="session-actions"><a class="play-button" href="osu://b/${Number(m.id)}">▶ Open in osu!</a><button class="route-primary" data-route="next">${item.status?'Continue':'Done, next map'} →</button></div><details class="session-secondary"><summary>Map options</summary><button data-route="skip">Skip this map</button><button data-route="hard" ${busy?'disabled':''}>Too hard</button><a href="${esc(url(m.url))}" target="_blank" rel="noopener noreferrer">Map page</a></details></div></div><details class="session-help"><summary>Why this session?</summary><p>${esc(session.evidence)}</p><p>${esc(m.reason)}</p>${attempts.length?`<p>Recent submitted runs: ${attempts.map(a=>a.passed?`${a.accuracy.toFixed(1)}% with ${a.misses} misses`:'Failed run').join(' · ')}</p>`:''}<p>Your place is saved in this browser. Use the displayed mods in lazer; the accuracy target is an estimate.</p></details>`;
}
function render(selectionOnly=false){
 const maps=activeMaps(),warning=activeWarning(),list=maps.filter(m=>(filter==='all'||m.kind===filter)&&(modFilter==='all'||m.mods===modFilter)),first=list.find(m=>m.key===selected)||list[0];
 document.querySelectorAll('[data-section]').forEach(b=>{const active=b.dataset.section===section;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 $('#section-description').textContent=section==='farm'?'Pick a score worth going for.':'Follow a short route, one map at a time.';
 $('#map-heading').textContent=section==='farm'?'Choose your next PP target':browsePractice?'Browse practice maps':'Your next practice session';
 $('.intro').hidden=section==='practice'&&!browsePractice&&!!result?.practiceSession;
 $('#practice-library').hidden=section!=='practice'||!result;
 $('#practice-count').textContent=`(${result?.maps.length||0})`;
 $('#browse-practice').hidden=browsePractice;$('#return-session').hidden=!browsePractice;
 $('#browse-practice').setAttribute('aria-expanded',browsePractice);
 $('#table-title').textContent=section==='farm'?'PP targets':'More practice maps';
 $('#method-details').textContent=section==='farm'?'Farm combines community top-score prevalence, relative pp efficiency, estimated FC likelihood, profile gain and retry duration. Max pp means a 100% FC, while predicted pp assumes an FC at the displayed accuracy; both exclude bonus pp. The likelihood is a local heuristic rather than a validated probability.':'Practice compares recent passes and complete failures under the same mods, with newer results carrying more weight. A focus needs several comparable observations across different maps; otherwise the session uses balanced control. Each candidate holds other demands stable while introducing a manageable challenge. Early quits do not supply full-map accuracy, and UR requires replay hit errors.';

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
 $('#featured').innerHTML=`<article class="featured-card"><div class="art">${url(first.cover)?`<img src="${esc(url(first.cover))}" alt="" referrerpolicy="no-referrer">`:'<span class="no-art">Artwork unavailable</span>'}<div class="art-heading">${first.provisional?'<div class="pick-label">Trial map</div>':''}<h2>${esc(first.title)}</h2><p class="artist">${esc(first.artist)}</p></div></div><div class="feature-info">${section==='farm'?ppMeter(first):''}<div class="feature-main"><p class="difficulty">${esc(first.version)} <span>by ${esc(first.mapper)}</span></p><div class="map-meta"><span class="stars">${first.stars.toFixed(2)} ★</span><span class="mod">${esc(modName(first))}</span><span>${duration(first.length)}</span></div></div><div class="practice-focus"><strong>${section==='farm'?'FC target':'Your goal'}</strong><p>${esc(practiceText(first))}</p></div><div class="map-actions"><a class="play-button" href="osu://b/${Number(first.id)}"><span aria-hidden="true">▶</span> Open in osu!</a><details class="farm-options"><summary>Map options</summary><a class="website-link" href="${esc(url(first.url))}" target="_blank" rel="noopener noreferrer">View on website</a><button id="too-hard">Too hard</button></details></div></div><details class="reason"><summary>Why this map?</summary><p>${esc(first.reason)}</p>${section==='farm'?`<p>Estimated FC likelihood: ${Math.round((first.fcProbability||0)*100)}%, with an accuracy range of ${first.accuracyLow?.toFixed(1)}–${first.accuracyHigh?.toFixed(1)}% across comparable runs. This forecast has not been statistically calibrated.</p>`:''}<p class="extra-stats">AR ${first.ar} · OD ${first.od} · ${duration(first.length)} · Use the shown mods</p><p>Circle bursts: ${Math.round(first.burstBpm||0)} BPM equivalent; sustained runs: ${first.streamBpm?Math.round(first.streamBpm)+' BPM equivalent':'none identified'}. These describe map patterns, not your personal speed limit.</p></details></article>`;
 if(!selectionOnly) $('#rows').innerHTML=list.map((m,i)=>`<article class="map-row ${m.key===first.key?'selected':''}" style="--arrival:${Math.min(i,11)*35}ms"><div class="rank">${i+1}</div><div class="row-track">${url(m.cover)?`<button class="mini-art" data-select="${esc(m.key)}" aria-label="Select artwork for ${esc(m.title)} ${esc(m.version)}"><img src="${esc(url(m.cover))}" alt="" loading="lazy" referrerpolicy="no-referrer"></button>`:''}<div class="row-text"><h3 class="row-name"><button class="select-map" data-select="${esc(m.key)}" aria-label="Select ${esc(m.title)} ${esc(m.version)}">${esc(m.title)}</button></h3><div class="row-sub">${esc(m.version)} <span class="row-artist">/ ${esc(m.artist)}</span></div></div></div>${section==='farm'?ppMeter(m):''}<div class="row-difficulty"><span class="stars">${m.stars.toFixed(2)} ★</span><span class="mod">${esc(modName(m))}</span></div></article>`).join('');
 $('#too-hard').disabled=busy;
 $('#too-hard').addEventListener('click',async()=>{try{let response=await post('/api/feedback',{id:first.id,key:first.key});clearRoute();await state();toast(`This map has been removed, and its mod setup is now limited to ${response.limit.toFixed(2)}★.`);}catch(e){toast(e.message);}});
}
async function state(){try{let response=await window.NEXT_UP_BACKEND.state();let data=await response.json(),wasBusy=busy;busy=data.state.busy;configured=data.configured;$('#refresh').disabled=busy;$('#save-settings').disabled=!data.available;$('#disconnect').hidden=!configured;$('#reset-feedback').hidden=!configured;$('#limit-form button').disabled=busy;if($('#too-hard'))$('#too-hard').disabled=busy;$('#account').classList.toggle('connected',configured);$('#account-label').textContent=data.username||'Connect profile';
 let nextRevision=data.result?JSON.stringify([data.revision,data.result.updated,data.result.maps.length,data.result.maxStars]):'none';
 if(nextRevision!==revision||!!result!==!!data.result){result=data.result;revision=nextRevision;render();}
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
document.querySelectorAll('.filter').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;selected=null;render();}));
$('#mod-tabs').addEventListener('click',e=>{const button=e.target.closest('[data-mod]');if(button){modFilter=button.dataset.mod;selected=null;render();}});
$('#rows').addEventListener('click',e=>{let select=e.target.closest('[data-select]'),detail=e.target.closest('[data-detail]');if(select){selected=select.dataset.select;render(true);document.querySelectorAll('#rows .map-row').forEach(row=>row.classList.toggle('selected',row.querySelector('[data-select]')?.dataset.select===selected));}else if(detail){let key=detail.dataset.detail;expanded.has(key)?expanded.delete(key):expanded.add(key);render();}});
$('#details-button').addEventListener('click',()=>{let d=$('#method-details');d.hidden=!d.hidden;$('#details-button').setAttribute('aria-expanded',!d.hidden);$('#details-button').lastElementChild.textContent=d.hidden?'+':'−';});
$('#section-switch').addEventListener('click',e=>{const button=e.target.closest('[data-section]');if(!button)return;section=button.dataset.section;browsePractice=false;localStorage.setItem('next-up-section',section);selected=null;filter='all';modFilter='all';render();});
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

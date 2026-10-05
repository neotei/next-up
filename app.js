const $=s=>document.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url=value=>{try{let u=new URL(value);return u.protocol==='https:'?u.href:'';}catch{return '';}};
const duration=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
const modName=m=>m.modSettings?.some(x=>x.acronym==='DA')?'AR adjusted':m.mods==='NM'?'No Mod':m.mods;
function ppMeter(m){return `<div class="pp-meter"><div class="pp-max"><span>MAX FC · 100%</span><strong>${m.maxPP?.toFixed(0)||'...'}<small> pp</small></strong></div><div class="pp-predicted"><span>PREDICTED · ${m.accuracy.toFixed(1)}%</span><strong>${m.estimatedPP.toFixed(0)}<small> pp</small></strong></div></div>`;}
function practiceText(m){
 if(section==='farm')return `Your predicted FC would add about +${m.estimatedGain.toFixed(1)} profile pp.`;
 const fewer=(m.goal||'').match(/fewer than (\d+) misses/);
 const ending=fewer?`with fewer than ${fewer[1]} misses`:(m.goal||'').includes('zero misses')?'without missing':'with no more than two misses';
 const goal=`Aim for ${m.accuracy.toFixed(1).replace(/\.0$/,'')}% accuracy ${ending}.`;
 return m.modSettings?.some(x=>x.acronym==='DA')?`In lazer, use Difficulty Adjust at AR ${m.ar} with the other settings unchanged, then ${goal.charAt(0).toLowerCase()+goal.slice(1)}`:goal;
}
let section=localStorage.getItem('next-up-section')==='farm'?'farm':'practice';
const activeMaps=()=>section==='farm'?(result?.farmMaps||[]):(result?.maps||[]);
const activeWarning=()=>section==='farm'?result?.farmWarning:result?.warning;
let result=null,configured=false,busy=false,filter='all',modFilter='all',selected=null,expanded=new Set(),revision=null,timer;
function toast(message,sticky=false){clearTimeout(timer);$('#toast').textContent=message;$('#toast').hidden=false;if(!sticky)timer=setTimeout(()=>$('#toast').hidden=true,5500);}
async function post(path,body={}){if(window.NEXT_UP_BACKEND)return window.NEXT_UP_BACKEND.post(path,body);let response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let data=await response.json();if(!response.ok)throw new Error(data.error||'Request failed.');return data;}
function renderTraining(){
 const el=$('#training-session'),plan=result?.practiceSession;
 el.hidden=section!=='practice'||!plan;if(el.hidden)return;
 if(el.dataset.session===JSON.stringify(plan))return;el.dataset.session=JSON.stringify(plan);
 el.innerHTML=`<div class="training-heading"><h2>${esc(plan.focus)}</h2><span>~${plan.minutes} minutes of play</span></div><p class="training-evidence">${esc(plan.evidence)}</p><div class="training-blocks">${['warm','focus','check'].map((role,i)=>{const items=plan.items.filter(x=>x.role===role);if(!items.length)return '';return `<div class="training-block"><h3><b>0${i+1}</b> ${esc(items[0].title)}</h3><p>${esc(items[0].instruction)}</p>${items.map(item=>{const m=result.maps.find(m=>m.key===item.key);if(!m)return '';return `<button data-training="${esc(m.key)}"><span>${esc(m.title)}</span><small>${esc(m.version)} · ${m.stars.toFixed(2)}★ · ${esc(modName(m))}</small></button>${item.attempts.length?`<div class="training-attempts">Recent: ${item.attempts.map(a=>a.passed?`${a.accuracy.toFixed(1)}% / ${a.misses} misses`:'Failed').join(' · ')}</div>`:''}`;}).join('')}</div>`;}).join('')}</div><details class="training-review"><summary>How to judge the session</summary><p>${esc(plan.review)}</p><p>These are starting goals, not a diagnosis of individual patterns. Lazer score summaries do not provide hit-error timing or replay-level technique analysis.</p></details>`;
}
function render(selectionOnly=false){
 const maps=activeMaps(),warning=activeWarning(),list=maps.filter(m=>(filter==='all'||m.kind===filter)&&(modFilter==='all'||m.mods===modFilter)),first=list.find(m=>m.key===selected)||list[0];
 document.querySelectorAll('[data-section]').forEach(b=>{const active=b.dataset.section===section;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 $('#section-description').textContent=section==='farm'?'Community farm picks ranked by pp for the effort.':'Readable maps that build on your clean plays.';
 $('#map-heading').textContent=section==='farm'?'Farm your next score':'Your practice session';
 $('#table-title').textContent=section==='farm'?'PP targets':'More practice maps';
 $('#method-details').textContent=section==='farm'?'Farm starts with osu!pps community top-score data and favours maps that are disproportionately common in top plays, give strong pp for their difficulty and allow short repeatable attempts. It then checks your reading and physical range. FC pp and weighted gain are estimates based on your latest top 100 scores, excluding bonus pp; live values may differ. The map catalogue is precomputed, so switching and recalculating do not download candidate maps.':'Practice uses your clean passes and recent failures to keep reading comfortable while introducing at most one modest challenge. Trial setups have less direct evidence, and Difficulty Adjust changes only AR when shown. Mark unreadable maps as Too hard; aggregate attributes cannot diagnose individual patterns or technique.';
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
 $('#method').textContent=result?.summary||'Recommendations use reliable passes, exact mod difficulty and recent failures.';
 $('#empty').hidden=!!first;
 $('.crate').hidden=!first;
 $('.selection-layout').hidden=!first;
 if(!first){$('#featured').innerHTML='';$('#rows').innerHTML='';$('#empty').innerHTML=`<p>${warning?esc(warning):maps.length?(filter==='retry'?'No previously played maps match these filters.':'No new maps in this list.'):configured?'No recommendations yet. Refresh to build your list.':'Connect your profile to get started.'}</p>${maps.length?'<button id="reset-filter">Show all maps</button>':''}`;$('#reset-filter')?.addEventListener('click',()=>{filter='all';modFilter='all';render();});return;}
 $('#featured').innerHTML=`<article class="featured-card"><div class="art">${url(first.cover)?`<img src="${esc(url(first.cover))}" alt="" referrerpolicy="no-referrer">`:'<span class="no-art">Artwork unavailable</span>'}<div class="art-heading">${first.provisional?'<div class="pick-label">Trial map</div>':''}<h2>${esc(first.title)}</h2><p class="artist">${esc(first.artist)}</p></div></div><div class="feature-info">${section==='farm'?ppMeter(first):''}<div class="feature-main"><p class="difficulty">${esc(first.version)} <span>by ${esc(first.mapper)}</span></p><div class="map-meta"><span class="stars">${first.stars.toFixed(2)} ★</span><span class="mod">${esc(modName(first))}</span><span>${duration(first.length)}</span></div></div><div class="practice-focus"><strong>${section==='farm'?'FC target':'Your goal'}</strong><p>${esc(practiceText(first))}</p></div><div class="map-actions"><a class="play-button" href="osu://b/${Number(first.id)}"><span aria-hidden="true">▶</span> Open in osu!</a><a class="website-link" href="${esc(url(first.url))}" target="_blank" rel="noopener noreferrer">View on website</a><button id="too-hard">Too hard</button></div></div><details class="reason"><summary>Why this map?</summary><p>${esc(first.reason)}</p><p class="extra-stats">AR ${first.ar} · OD ${first.od} · ${duration(first.length)} · Use the shown mods</p></details></article>`;
 if(!selectionOnly) $('#rows').innerHTML=list.map((m,i)=>`<article class="map-row ${m.key===first.key?'selected':''}" style="--arrival:${Math.min(i,11)*35}ms"><div class="rank">${i+1}</div><div class="row-track">${url(m.cover)?`<button class="mini-art" data-select="${esc(m.key)}" aria-label="Select artwork for ${esc(m.title)} ${esc(m.version)}"><img src="${esc(url(m.cover))}" alt="" loading="lazy" referrerpolicy="no-referrer"></button>`:''}<div class="row-text"><h3 class="row-name"><button class="select-map" data-select="${esc(m.key)}" aria-label="Select ${esc(m.title)} ${esc(m.version)}">${esc(m.title)}</button></h3><div class="row-sub">${esc(m.version)} <span class="row-artist">/ ${esc(m.artist)}</span></div></div></div>${section==='farm'?ppMeter(m):''}<div class="row-difficulty"><span class="stars">${m.stars.toFixed(2)} ★</span><span class="mod">${esc(modName(m))}</span></div></article>`).join('');
 $('#too-hard').disabled=busy;
 $('#too-hard').addEventListener('click',async()=>{try{let response=await post('/api/feedback',{id:first.id,key:first.key});await state();toast(`This map has been removed, and its mod setup is now limited to ${response.limit.toFixed(2)}★.`);}catch(e){toast(e.message);}});
}
async function state(){try{let response=await window.NEXT_UP_BACKEND.state();let data=await response.json(),wasBusy=busy;busy=data.state.busy;configured=data.configured;$('#refresh').disabled=busy;$('#save-settings').disabled=!data.available;$('#disconnect').hidden=!configured;$('#reset-feedback').hidden=!configured;$('#limit-form button').disabled=busy;if($('#too-hard'))$('#too-hard').disabled=busy;$('#account').classList.toggle('connected',configured);$('#account-label').textContent=data.username||'Connect profile';
 let nextRevision=data.result?JSON.stringify([data.revision,data.result.updated,data.result.maps.length,data.result.maxStars]):'none';
 if(nextRevision!==revision||!!result!==!!data.result){result=data.result;revision=nextRevision;render();}
 $('#limit-form').hidden=!configured;$('.list-top').hidden=!configured;$('#mod-tabs').hidden=!configured;$('#details-button').hidden=!configured;$('#empty').hidden=!configured||!!activeMaps().length;
 $('#notice').hidden=configured&&!activeWarning();$('#connect-banner').hidden=configured;
 if(!configured){$('#notice').querySelector('span').textContent='Your next practice session';$('#notice').querySelector('p').textContent='Connect your profile and we’ll pick readable maps that build on your clean lazer plays.';}
 if(busy)toast(data.state.message,true);else if(wasBusy)toast(data.state.error||'Your maps are ready.',!!data.state.error);
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
$('#section-switch').addEventListener('click',e=>{const button=e.target.closest('[data-section]');if(!button)return;section=button.dataset.section;localStorage.setItem('next-up-section',section);selected=null;filter='all';modFilter='all';render();});
async function poll(){await state();setTimeout(poll,busy?350:15000);}
render();poll();
const authError=new URLSearchParams(location.search).get('auth_error');
if(authError){const messages={mismatch:'The signed-in account does not match that user ID; try again with your own ID.',denied:'osu! authorization was cancelled.',state:'The sign-in request expired; please try again.',id:'Enter a numeric osu! user ID.',unavailable:'Sign-in is being set up. Please check back shortly.',busy:'The service is busy; please try again later.',failed:'osu! sign-in could not be completed; please try again.'};toast(messages[authError]||messages.failed,true);}
if(location.search)history.replaceState(null,'',location.pathname);

$('#training-session').addEventListener('click',e=>{const b=e.target.closest('[data-training]');if(!b)return;selected=b.dataset.training;filter='all';modFilter='all';render();$('#featured').scrollIntoView({block:'nearest',behavior:'instant'});});

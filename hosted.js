/* OAuth tokens and recommendations stay in the server session. */
(()=>{
 const service=document.documentElement.dataset.service||'';
 if(service&&location.origin!==new URL(service).origin){location.replace(service+location.search);return;}
 for(const key of ['next-up-last-list-v1','next-up-preferences-v1'])localStorage.removeItem(key);
 let csrf='',userId=null,restored=false;
 const key=()=>`next-up-user-${userId}`;
 const read=()=>{try{return JSON.parse(localStorage.getItem(key()))||{max_stars:12,blocked_ids:[],mod_caps:{}};}catch{return {max_stars:12,blocked_ids:[],mod_caps:{}};}};
 const save=p=>{try{localStorage.setItem(key(),JSON.stringify(p));}catch{}};
 async function post(path,body={}){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'This request could not be completed.');
  if(data.preferences)save(data.preferences);
  return data;
 }
 window.NEXT_UP_BACKEND={post,async state(){
  let response;
  try{response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw new Error();}
  catch{return {ok:true,json:async()=>({configured:false,available:false,username:'',result:null,state:{busy:false,message:'',error:null}})};}
  const data=await response.json();csrf=data.csrf||'';
  if(data.configured){
   if(userId!==data.userId){userId=data.userId;restored=false;}
   if(!restored){restored=true;await post('/api/preferences',read());if(!data.result&&!data.state.busy){await post('/api/refresh');data.state={busy:true,message:'Finding maps from your lazer scores…',error:null};}}
  }else{userId=null;restored=false;}
  return {ok:true,json:async()=>data};
 }};
})();

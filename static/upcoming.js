
const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
async function load(){const days=document.getElementById("days").value,r=await fetch(`/api/upcoming?days=${days}`),d=await r.json();count.textContent=`${d.results.length} upcoming episode${d.results.length===1?"":"s"}`;list.innerHTML=d.results.length?`<table class="compact-table"><tr><th>Date</th><th>Show</th><th>Episode</th><th>Title</th><th>Network</th><th>Status</th></tr>${d.results.map(e=>`<tr><td>${esc(e.airdate)}</td><td>${esc(e.show_name)}</td><td>S${String(e.season).padStart(2,"0")}E${String(e.episode).padStart(2,"0")}</td><td>${esc(e.name)}</td><td>${esc(e.network)}</td><td><span class="status-pill ${esc(e.status_label)}">${esc(e.status_label)}</span></td></tr>`).join("")}</table>`:'<div class="empty-state compact">No episodes in this window.</div>'}days.addEventListener("change",load);load();

let calendarDate=new Date(),calendarOpen=false;
const calendarElement=id=>document.getElementById(id);
async function calendarJson(url,options={}){const r=await fetch(url,options),d=await r.json();if(!r.ok)throw new Error(d.error||'Calendar request failed');return d;}
function localDay(d){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
async function renderCalendar(){
 const start=new Date(calendarDate.getFullYear(),calendarDate.getMonth(),1),end=new Date(calendarDate.getFullYear(),calendarDate.getMonth()+1,0);
 calendarElement('calendarMonth').textContent=start.toLocaleDateString(undefined,{month:'long',year:'numeric'});
 try{
  const data=await calendarJson('/api/calendar?start='+localDay(start)+'&end='+localDay(end)),byDate=new Map();
  for(const episode of data.results){if(!byDate.has(episode.airdate))byDate.set(episode.airdate,[]);byDate.get(episode.airdate).push(episode);}
  let html=Array.from({length:start.getDay()},()=>'<div class="calendar-day empty" aria-hidden="true"></div>').join('');
  for(let day=1;day<=end.getDate();day++){
   const date=new Date(start.getFullYear(),start.getMonth(),day),key=localDay(date),items=byDate.get(key)||[];
   html+=`<section class="calendar-day ${key===localDay(new Date())?'today':''}" aria-label="${esc(date.toLocaleDateString())}"><strong>${esc(date.toLocaleDateString(undefined,{weekday:'short',day:'numeric'}))}</strong>${items.map(e=>`<a href="/show/${Number(e.show_id)}">${esc(e.show_name)} S${String(e.season).padStart(2,'0')}E${String(e.episode).padStart(2,'0')} — ${esc(e.name)}</a>`).join('')}</section>`;
  }
  calendarElement('calendarGrid').innerHTML='<div class="episode-calendar">'+html+'</div>';
 }catch(e){calendarElement('calendarGrid').textContent=e.message;}
}
calendarElement('calendarToggle').onclick=()=>{
 calendarOpen=!calendarOpen;calendarElement('calendarToggle').textContent=calendarOpen?'List View':'Calendar View';
 for(const id of ['calendarGrid','calendarPrev','calendarNext','calendarMonth'])calendarElement(id).hidden=!calendarOpen;
 calendarElement('upcomingListPanel').hidden=calendarOpen;if(calendarOpen)renderCalendar();
};
calendarElement('calendarPrev').onclick=()=>{calendarDate=new Date(calendarDate.getFullYear(),calendarDate.getMonth()-1,1);renderCalendar();};
calendarElement('calendarNext').onclick=()=>{calendarDate=new Date(calendarDate.getFullYear(),calendarDate.getMonth()+1,1);renderCalendar();};
calendarElement('calendarSubscribe').onclick=async()=>{try{const d=await calendarJson('/api/calendar/subscription',{method:'POST'});calendarElement('calendarSubscription').textContent='Copy this private URL into your calendar app (previous link revoked): '+d.url;}catch(e){calendarElement('calendarSubscription').textContent=e.message;}};
calendarElement('calendarRevoke').onclick=async()=>{try{await calendarJson('/api/calendar/subscription',{method:'DELETE'});calendarElement('calendarSubscription').textContent='Subscription link revoked.';}catch(e){calendarElement('calendarSubscription').textContent=e.message;}};

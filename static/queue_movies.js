// Movie downloads on the Queue page, so episodes and movies are watched in one place.
(()=>{
 const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
 const box=document.getElementById('movieQueue');if(!box)return;
 const ACTIVE=['Queued','Downloading','Downloaded'];
 async function load(){
  try{
   const r=await fetch('/api/movies/downloads'),d=await r.json();
   const active=d.downloads.filter(x=>ACTIVE.includes(x.status)),recent=d.downloads.filter(x=>!ACTIVE.includes(x.status)).slice(0,5);
   const row=x=>`<a class="feed-row" href="/movie/${Number(x.movie_id)}"><span class="status-pill ${esc(x.status)}">${esc(x.status==='Downloaded'?'Importing':x.status)}</span><div class="feed-main"><strong>${esc(x.title)}${x.year?` (${esc(x.year)})`:''}</strong><small>${esc(x.release_name)}${x.message?' · '+esc(x.message):''}</small></div><div class="feed-side"><small>${esc(x.client)}${x.status==='Downloading'?' · '+Math.round((x.progress||0)*100)+'%':''}</small></div></a>`;
   box.innerHTML=(active.length?active.map(row).join(''):'<div class="empty-state compact">No movie downloads in progress.</div>')+(recent.length?`<h3 class="feed-subhead">Recently finished</h3>${recent.map(row).join('')}`:'');
  }catch(e){box.innerHTML=`<div class="notice error">Movie downloads could not load: ${esc(e.message)}</div>`;}
 }
 load();setInterval(load,30000);
})();

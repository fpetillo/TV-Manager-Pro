const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
async function jsonFetch(url,opt){const r=await fetch(url,opt);const ct=r.headers.get('content-type')||'';const d=ct.includes('application/json')?await r.json():{error:await r.text()};if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
const post=(url,body)=>jsonFetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
const $=id=>document.getElementById(id);
const id=document.body.dataset.movieId;
const sizeText=b=>!b?'—':b>=1073741824?(b/1073741824).toFixed(1)+' GB':(b/1048576).toFixed(0)+' MB';
const STATUS={Wanted:'Wanted',Snatched:'Downloading',Downloaded:'In library',Ignored:'Ignored'};
const VIA={auto:'Added by discovery',manual:'Added by you',plex:'Found in Plex',library:'Found in a library folder'};
function when(v){if(!v)return '—';const s=String(v);const d=new Date(/^\d{4}-\d\d-\d\d \d\d:\d\d/.test(s)?s.replace(' ','T')+'Z':s);return isNaN(d)?s:d.toLocaleString();}
function setMessage(text,kind){const el=$('actionMessage');el.className='message'+(kind?' '+kind:'');el.textContent=text||'';}

function hero(m,downloads){
 const active=downloads.find(d=>['Queued','Downloading','Downloaded'].includes(d.status));
 const state=active?`${active.client}: ${active.status}${active.status==='Downloading'?' '+Math.round((active.progress||0)*100)+'%':''}`:m.status==='Wanted'&&!m.available?`Waiting for digital release${m.available_date?' on '+m.available_date:''}`:'';
 const poster=m.poster_path?`<img class="movie-hero-poster" alt="" src="https://image.tmdb.org/t/p/w342${esc(m.poster_path)}">`:'<div class="movie-hero-poster placeholder">🎬</div>';
 $('heroBackdrop').style.backgroundImage=m.poster_path?`url("https://image.tmdb.org/t/p/w780${encodeURI(m.poster_path)}")`:'';
 const chips=[m.rating?`★ ${Number(m.rating).toFixed(1)}${m.votes?` (${Number(m.votes).toLocaleString()} votes)`:''}`:null,m.genres,m.quality].filter(Boolean).map(x=>`<span class="chip">${esc(x)}</span>`).join('');
 const links=[m.tmdb_id?`<a class="btn secondary" target="_blank" rel="noopener" href="https://www.themoviedb.org/movie/${encodeURIComponent(m.tmdb_id)}">TMDb</a>`:'',m.imdb_id?`<a class="btn secondary" target="_blank" rel="noopener" href="https://www.imdb.com/title/${encodeURIComponent(m.imdb_id)}/">IMDb</a>`:''].join('');
 const toggle=m.status==='Ignored'?'<button class="secondary" id="wantBtn">Want this movie</button>':m.status!=='Downloaded'?'<button class="secondary" id="ignoreBtn">Ignore</button>':'';
 document.querySelector('#movieHero .movie-hero-body').innerHTML=`${poster}<div class="movie-hero-text"><div class="movie-hero-top"><span class="type-pill movie">Movie</span><span class="status-pill ${esc(m.status)}">${esc(STATUS[m.status]||m.status)}</span></div><h2>${esc(m.title)} ${m.year?`<span>(${esc(m.year)})</span>`:''}</h2><div class="chip-row">${chips}</div>${state?`<p class="movie-state">${esc(state)}</p>`:''}<p class="movie-overview">${esc(m.overview||'No overview yet.')}</p><div class="actions">${m.status!=='Ignored'?`<button class="blue" id="heroSearch">${m.status==='Downloaded'?'Look for an upgrade':'Search and download'}</button>`:''}${toggle}${links}</div></div>`;
 document.title=`${m.title}${m.year?` (${m.year})`:''} — Movies`;$('pageTitle').textContent=m.title;
 const hs=$('heroSearch');if(hs)hs.onclick=()=>runSearch(true,hs);
 const ib=$('ignoreBtn');if(ib)ib.onclick=async()=>{await post(`/api/movies/${id}`,{status:'Ignored'});load();};
 const wb=$('wantBtn');if(wb)wb.onclick=async()=>{await post(`/api/movies/${id}`,{status:'Wanted'});load();};
}

function facts(m){
 const rows=[['Status',STATUS[m.status]||m.status],['File',m.file_path||'—'],['Size',sizeText(m.size)],['Quality',m.quality||(m.resolution?m.resolution+'p':'—')],
  ['Release',m.release_name||'—'],['Digital / disc release',m.available_date||'Unknown'],['Theatrical release',m.release_date||'—'],
  ['Origin',VIA[m.added_via]||m.added_via||'—'],['Added',when(m.added_at)],['Downloaded',when(m.downloaded_at)],
  ['Last search',m.last_search?when(m.last_search):'Never'],['Searches',m.search_count||0],['Monitored',m.monitored?'Yes':'No']];
 if(m.message)rows.push(['Note',m.message]);
 $('facts').innerHTML=rows.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
}

function releases(list){
 const usable=list.filter(r=>!r.rejected_reason).length;
 $('releaseNote').textContent=list.length?`${usable} usable of ${list.length} found in the last search. Rejected releases show the reason.`:'No releases found yet. Search now, or wait for the hourly search.';
 $('releaseRows').innerHTML=list.length?list.map(r=>`<tr class="${r.rejected_reason?'rejected':''}"><td class="wrap">${esc(r.title)}</td><td>${esc(r.provider)}</td><td>${esc(r.quality)}</td><td class="nowrap">${sizeText(r.size)}</td><td>${r.protocol==='torrent'?esc(r.seeders):'NZB'}</td><td>${r.status==='Grabbed'?'<span class="status-pill Downloaded">Sent</span>':r.rejected_reason?`<small>${esc(r.rejected_reason)}</small>`:`<button class="blue small-btn grab" data-r="${r.id}">Download</button>`}</td></tr>`).join('')
  :'<tr><td colspan="6" class="muted">Nothing yet.</td></tr>';
 document.querySelectorAll('.grab').forEach(b=>b.onclick=async()=>{b.disabled=true;b.textContent='Sending…';try{const g=await post(`/api/movies/results/${b.dataset.r}/grab`);setMessage(`Sent to ${g.client}.`,'success');load();}catch(e){b.disabled=false;b.textContent='Download';setMessage(e.message,'error');}});
}

function history(list){
 $('history').innerHTML=list.length?list.map(d=>`<div class="feed-row"><span class="status-pill ${esc(d.status)}">${esc(d.status)}</span><div class="feed-main"><strong>${esc(d.release_name)}</strong><small>${esc(d.client)}${d.message?' · '+esc(d.message):''}${d.destination?' · '+esc(d.destination):''}</small></div><div class="feed-side"><small>${esc(when(d.created_at))}</small>${['Queued','Downloading','Downloaded'].includes(d.status)?`<button class="secondary small-btn fail-dl" data-d="${d.id}">Try another release</button>`:''}</div></div>`).join('')
  :'<div class="empty-state compact">No downloads for this movie yet.</div>';
 document.querySelectorAll('.fail-dl').forEach(b=>b.onclick=async()=>{if(!confirm('Blocklist this release and search for another one?'))return;await post(`/api/movies/downloads/${b.dataset.d}/fail`);load();});
}

function events(list){
 $('events').innerHTML=list.length?list.map(e=>`<div class="feed-row activity ${esc(String(e.level||'info').toLowerCase())}"><div class="feed-main"><strong>${esc(e.message)}</strong></div><div class="feed-side"><small>${esc(when(e.created_at))}</small></div></div>`).join('')
  :'<div class="empty-state compact">No activity recorded for this movie yet.</div>';
}

async function runSearch(autoGrab,button){
 const target=button||$('searchNow');const label=target.textContent;target.disabled=true;target.textContent='Searching…';
 try{const d=await post(`/api/movies/${id}/search`,{auto_grab:autoGrab});
  const usable=d.results.filter(r=>!r.rejected_reason).length;
  setMessage(d.grabbed?`Sent the best release to ${d.grabbed.client}.`:usable?`${usable} usable release${usable===1?'':'s'} found.`:`No usable release found${d.errors&&d.errors.length?' ('+d.errors.join('; ')+')':''}.`,d.grabbed||usable?'success':'warn');
  load();
 }catch(e){setMessage(e.message,'error');}finally{target.disabled=false;target.textContent=label;}
}

async function load(){
 try{const d=await jsonFetch(`/api/movies/${id}/detail`);hero(d.movie,d.downloads);facts(d.movie);releases(d.results);history(d.downloads);events(d.events);}
 catch(e){document.querySelector('#movieHero .movie-hero-body').innerHTML=`<div class="notice error">${esc(e.message)}</div>`;}
}
$('searchNow').onclick=()=>runSearch(false);
load();

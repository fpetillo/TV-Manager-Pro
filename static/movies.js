const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
async function jsonFetch(url,opt){const r=await fetch(url,opt);const ct=r.headers.get('content-type')||'';const d=ct.includes('application/json')?await r.json():{error:await r.text()};if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
const post=(url,body)=>jsonFetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
const $=id=>document.getElementById(id);
const poster=p=>p?`<img class="movie-poster" loading="lazy" alt="" src="https://image.tmdb.org/t/p/w185${esc(p)}">`:'<div class="movie-poster placeholder">🎬</div>';
const sizeText=b=>!b?'':b>=1073741824?(b/1073741824).toFixed(1)+' GB':(b/1048576).toFixed(0)+' MB';
const STATUS_LABEL={Wanted:'Wanted',Snatched:'Downloading',Downloaded:'Downloaded',Ignored:'Ignored'};
function setMessage(el,text,kind){el.className='message'+(kind?' '+kind:'');el.textContent=text||'';}

// ---------- tabs
document.querySelectorAll('.movie-tab').forEach(tab=>tab.onclick=()=>showTab(tab.dataset.tab));
function showTab(name){
  document.querySelectorAll('.movie-tab').forEach(t=>{const on=t.dataset.tab===name;t.classList.toggle('active',on);t.setAttribute('aria-selected',on);});
  document.querySelectorAll('.movie-view').forEach(v=>v.hidden=v.id!=='view-'+name);
  try{localStorage.setItem('tvmanager.movies.tab',name)}catch{}
  if(name==='downloads')loadDownloads();
  if(name==='settings')loadSettings();
  if(name==='discover'&&!$('discoverResults').children.length)loadDiscover(false);
}

// ---------- status
async function loadSummary(){
  try{
    const d=await jsonFetch('/api/movies/summary');const c=d.counts||{},s=d.settings||{};
    const tile=(n,l,tone,filter)=>`<a class="media-kpi ${tone||''}" href="#" data-filter="${filter}"><strong>${Number(n||0).toLocaleString()}</strong><span>${esc(l)}</span></a>`;
    $('movieStatus').innerHTML=tile(c.Downloaded,'In library','good','Downloaded')+tile(c.Wanted,'Wanted',c.Wanted?'warn':'','Wanted')+tile(d.active_downloads,'Downloading',d.active_downloads?'live':'','Snatched')+tile(c.Ignored,'Ignored','','Ignored');
    $('movieStatus').querySelectorAll('[data-filter]').forEach(a=>a.onclick=e=>{e.preventDefault();showTab('library');$('movieStatusFilter').value=a.dataset.filter;page=1;loadMovies();});
    const problems=[];
    if(String(s.enabled)!=='1')problems.push('Movies automation is turned off in Settings.');
    if(!s.automation_enabled)problems.push('TV Manager automation is off (Settings › Automation), so scheduled movie jobs will not run.');
    if(s.simulation_mode)problems.push('Simulation mode is on: movies are searched but nothing is downloaded or moved.');
    if(!s.effective_library_root)problems.push('No movie destination folder yet — add one under Settings.');
    else if((s.destination_status||[]).length&&!s.destination_status.some(d=>d.reachable))problems.push('No movie destination folder can be reached from this server — check Settings.');
    if(!s.tmdb_configured)problems.push('TMDb is not configured, so discovery cannot run.');
    if(!s.indexers)problems.push('No indexers with a matching download client are configured.');
    setMessage($('movieReadiness'),problems.length?problems.join(' '):`Running automatically. New movies go to: ${(s.destination_list||[]).join(', ')}. Indexers: ${s.indexers}. Clients: ${[s.nzb_client,s.torrent_client].filter(Boolean).join(' + ')||'none'}.`,problems.length?'warn':'success');
  }catch(e){setMessage($('movieReadiness'),e.message,'error');}
}

// ---------- library
let page=1;
async function loadMovies(){
  const q=new URLSearchParams({status:$('movieStatusFilter').value,q:$('movieSearch').value,sort:$('movieSort').value,page});
  try{
    const d=await jsonFetch('/api/movies?'+q);
    $('movieList').innerHTML=d.movies.length?d.movies.map(movieCard).join(''):'<p class="muted">No movies here yet. New releases are added automatically, or use Discover to add one.</p>';
    const pages=Math.max(1,Math.ceil(d.total/d.page_size));
    $('moviePageInfo').textContent=`${d.total} movies · page ${d.page} of ${pages}`;
    $('moviePrev').hidden=d.page<=1;$('movieNext').hidden=d.page>=pages;
    bindCards();setMessage($('movieMessage'),'');
  }catch(e){setMessage($('movieMessage'),e.message,'error');}
}
function movieCard(m){
  const dl=m.download;
  const state=dl?`${dl.client}: ${dl.status}${dl.status==='Downloading'?' '+Math.round((dl.progress||0)*100)+'%':''}`:(m.status==='Wanted'&&!m.available?'Waiting for digital release':'');
  return `<article class="movie-card" data-id="${m.id}"><a class="movie-poster-link" href="/movie/${m.id}" aria-label="${esc(m.title)} details">${poster(m.poster_path)}</a><div class="movie-card-body">
  <div class="trakt-card-head"><h3><a href="/movie/${m.id}">${esc(m.title)}</a> ${m.year?`<span>(${esc(m.year)})</span>`:''}</h3><span class="status-pill ${esc(m.status)}">${esc(STATUS_LABEL[m.status]||m.status)}</span></div>
  <p class="result-meta">${[m.quality,sizeText(m.size),m.rating?('★ '+Number(m.rating).toFixed(1)):null,m.added_via==='auto'?'Auto-added':null].filter(Boolean).map(esc).join(' • ')}</p>
  ${state?`<p class="movie-state">${esc(state)}</p>`:''}${m.message?`<p class="muted">${esc(m.message)}</p>`:''}
  <div class="actions">
   ${m.status!=='Ignored'?`<button class="blue small-btn act-search">Search</button>`:''}
   <button class="secondary small-btn act-results">Releases</button>
   ${m.status==='Ignored'?`<button class="secondary small-btn act-want">Want</button>`:`<button class="secondary small-btn act-ignore">Ignore</button>`}
  </div></div></article>`;
}
function bindCards(){
  document.querySelectorAll('#movieList .movie-card').forEach(card=>{
    const id=card.dataset.id;
    const b=(sel,fn)=>{const el=card.querySelector(sel);if(el)el.onclick=()=>fn(el);};
    b('.act-search',async el=>{el.disabled=true;el.textContent='Searching…';try{const d=await post(`/api/movies/${id}/search`,{auto_grab:true});el.textContent=d.grabbed?'Sent to '+d.grabbed.client:(d.results.some(r=>!r.rejected_reason)?'Found':'Nothing usable');if(!d.grabbed)openResults(id);loadMovies();loadSummary();}catch(e){el.disabled=false;el.textContent='Search';alert(e.message);}});
    b('.act-results',()=>openResults(id));
    b('.act-ignore',async()=>{await post(`/api/movies/${id}`,{status:'Ignored'});loadMovies();loadSummary();});
    b('.act-want',async()=>{await post(`/api/movies/${id}`,{status:'Wanted'});loadMovies();loadSummary();});
  });
}
async function openResults(id){
  const d=await jsonFetch(`/api/movies/${id}`);
  $('dialogTitle').textContent=`${d.movie.title}${d.movie.year?' ('+d.movie.year+')':''}`;
  const rows=d.results.map(r=>`<tr class="${r.rejected_reason?'rejected':''}"><td class="wrap">${esc(r.title)}</td><td>${esc(r.provider)}</td><td>${esc(r.quality)}</td><td>${esc(sizeText(r.size))}</td><td>${r.protocol==='torrent'?esc(r.seeders):'NZB'}</td><td>${r.rejected_reason?esc(r.rejected_reason):`<button class="blue small-btn grab" data-r="${r.id}">Download</button>`}</td></tr>`).join('');
  $('dialogContent').innerHTML=`${d.movie.file_path?`<p class="muted">File: ${esc(d.movie.file_path)}</p>`:''}<p class="muted">${esc(d.movie.overview||'')}</p>`+(rows?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Release</th><th>Indexer</th><th>Quality</th><th>Size</th><th>Seeds</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`:'<p class="muted">No releases found yet. Use Search.</p>');
  $('dialogContent').querySelectorAll('.grab').forEach(b=>b.onclick=async()=>{b.disabled=true;b.textContent='Sending…';try{const g=await post(`/api/movies/results/${b.dataset.r}/grab`);b.textContent='Sent to '+g.client;loadMovies();loadSummary();}catch(e){b.disabled=false;b.textContent='Download';alert(e.message);}});
  $('movieDialog').showModal();
}
$('dialogClose').onclick=()=>$('movieDialog').close();
let filterTimer;
$('movieSearch').oninput=()=>{clearTimeout(filterTimer);filterTimer=setTimeout(()=>{page=1;loadMovies();},300);};
['movieStatusFilter','movieSort'].forEach(id=>$(id).onchange=()=>{page=1;loadMovies();});
$('movieReload').onclick=()=>{loadMovies();loadSummary();};
$('moviePrev').onclick=()=>{page--;loadMovies();};
$('movieNext').onclick=()=>{page++;loadMovies();};

// ---------- discover
let discoverPage=1,discoverRows=[];
async function loadDiscover(more){
  discoverPage=more?discoverPage+1:1;
  const q=new URLSearchParams({list:$('discoverList').value,q:$('discoverQuery').value,page:discoverPage});
  setMessage($('discoverMessage'),'Loading…');
  try{
    const d=await jsonFetch('/api/movies/discover?'+q);
    discoverRows=more?discoverRows.concat(d.results):d.results;
    $('discoverResults').innerHTML=discoverRows.length?discoverRows.map((m,i)=>`<article class="movie-card">${poster(m.poster_path)}<div class="movie-card-body"><div class="trakt-card-head"><h3>${esc(m.title)} ${m.year?`<span>(${esc(m.year)})</span>`:''}</h3>${m.status?`<span class="status-pill ${esc(m.status)}">${esc(STATUS_LABEL[m.status]||m.status)}</span>`:''}</div><p class="result-meta">${[m.release_date,m.rating?('★ '+Number(m.rating).toFixed(1)+' ('+m.votes+')'):null].filter(Boolean).map(esc).join(' • ')}</p><p>${esc(m.overview||'')}</p><div class="actions"><button class="blue small-btn add-movie" data-i="${i}" ${m.status?'disabled':''}>${m.status?'In Movies':'Add'}</button></div></div></article>`).join(''):'<p class="muted">No movies matched.</p>';
    $('discoverMore').hidden=d.page>=d.total_pages;
    setMessage($('discoverMessage'),'');
    document.querySelectorAll('.add-movie').forEach(b=>b.onclick=async()=>{b.disabled=true;b.textContent='Adding…';try{const r=await post('/api/movies',{tmdb_id:discoverRows[+b.dataset.i].tmdb_id});b.textContent=r.created?'Added':'Already in Movies';discoverRows[+b.dataset.i].status=r.movie.status;loadSummary();}catch(e){b.disabled=false;b.textContent='Add';alert(e.message);}});
  }catch(e){setMessage($('discoverMessage'),e.message,'error');}
}
$('discoverLoad').onclick=()=>loadDiscover(false);
$('discoverQuery').onkeydown=e=>{if(e.key==='Enter')loadDiscover(false);};
$('discoverList').onchange=()=>{$('discoverQuery').value='';loadDiscover(false);};
$('discoverMore').onclick=()=>loadDiscover(true);

// ---------- downloads
async function loadDownloads(){
  try{
    const d=await jsonFetch('/api/movies/downloads');
    $('downloadRows').innerHTML=d.downloads.length?d.downloads.map(x=>`<tr><td>${esc(x.title)} ${x.year?'('+esc(x.year)+')':''}</td><td class="wrap">${esc(x.release_name)}</td><td>${esc(x.client)}</td><td><span class="status-pill ${esc(x.status)}">${esc(x.status)}</span></td><td>${x.status==='Completed'?'100%':Math.round((x.progress||0)*100)+'%'}</td><td>${esc((x.created_at||'').replace('T',' '))}</td><td class="wrap">${esc(x.message||x.destination||'')}</td><td>${['Queued','Downloading','Downloaded'].includes(x.status)?`<button class="secondary small-btn fail-dl" data-d="${x.id}" title="Blocklist this release and search for another">Try another release</button>`:''}</td></tr>`).join(''):'<tr><td colspan="8" class="muted">No movie downloads yet.</td></tr>';
    document.querySelectorAll('.fail-dl').forEach(b=>b.onclick=async()=>{if(!confirm('Blocklist this release and search for another one?'))return;await post(`/api/movies/downloads/${b.dataset.d}/fail`);loadDownloads();loadSummary();});
  }catch(e){$('downloadRows').innerHTML=`<tr><td colspan="8" class="message error">${esc(e.message)}</td></tr>`;}
}
$('downloadsReload').onclick=loadDownloads;

// ---------- settings
async function loadSettings(){
  const s=await jsonFetch('/api/movies/settings');const f=$('movieSettings');
  for(const el of f.elements){if(!el.name||!(el.name in s))continue;if(el.type==='checkbox')el.checked=['1','true','on','yes'].includes(String(s[el.name]).toLowerCase());else el.value=s[el.name]??'';}
  renderScan(s.last_scan_report||{});
  renderDestinations(s);
  loadRelocation();
  $('clientInfo').textContent=`Using your TV Manager download clients: NZB ${s.nzb_client||'none'}, torrent ${s.torrent_client||'none'}; ${s.indexers} indexer(s). Movies go to their own category or label so they stay apart from TV.`;
}
function renderDestinations(s){
  const list=s.destination_status||[];
  $('destStatus').innerHTML=list.length?list.map(d=>`<div class="dest-row ${d.reachable?'ok':'bad'}"><span class="dest-path">${esc(d.path)}</span><span>${d.reachable?(d.free_gb!=null?`${d.free_gb.toLocaleString()} GB free of ${d.total_gb.toLocaleString()} GB`:'Reachable'):'Not reachable from this server'}</span></div>`).join(''):'<div class="dest-row bad"><span>No destination folder yet. New movies cannot be imported until one is added.</span></div>';
}
async function loadRelocation(){
  const box=$('relocateBox');
  try{const p=await jsonFetch('/api/movies/relocate');
    if(!p.items.length&&!p.skipped.length){box.hidden=true;return;}
    box.hidden=false;
    box.innerHTML=`<strong>${p.items.length?`${p.items.length} imported movie${p.items.length===1?' is':'s are'} outside the destination folders.`:'Imported movies that cannot be moved automatically'}</strong>
      <ul>${p.items.slice(0,6).map(i=>`<li>${esc(i.title)}${i.year?` (${esc(i.year)})`:''} <small class="muted">${esc(i.from)} → ${esc(i.dest)}</small></li>`).join('')}${p.items.length>6?`<li class="muted">and ${p.items.length-6} more</li>`:''}</ul>
      ${p.skipped.length?`<p class="muted">${p.skipped.length} cannot be moved: ${p.skipped.slice(0,3).map(x=>esc(x.title+' — '+x.reason)).join('; ')}</p>`:''}
      ${p.items.length?`<button type="button" class="blue" id="relocateBtn">Move ${p.items.length} movie${p.items.length===1?'':'s'} into the destination folders</button>`:''}`;
    const b=$('relocateBtn');if(b)b.onclick=async()=>{if(!confirm(`Move ${p.items.length} movie folder(s) into the destination folders? Plex scans its movie libraries afterwards.`))return;b.disabled=true;b.textContent='Moving… (see Logs)';try{await post('/api/movies/relocate');setTimeout(loadRelocation,5000);}catch(e){b.disabled=false;alert(e.message);}};
  }catch(e){box.hidden=true;}
}
function renderScan(r){
  if(!r.sources){$('scanSummary').textContent='No library scan yet. Use "Scan library now".';$('scanSources').innerHTML='';return;}
  const when=(r.scanned_at||'').replace('T',' ');
  $('scanSummary').textContent=`${r.owned} movies owned in total (${r.plex_movies} entries from Plex, ${r.folder_movies} from folders; the same movie in both counts once). Scanned ${when}.`+(r.complete?'':' Some Plex libraries could not be read, so automatic adding is paused until the next complete scan.');
  $('scanSources').innerHTML=r.sources.map(x=>{const name=x.kind==='plex'?`${esc(x.library||'(server)')}${x.locations&&x.locations.length?`<br><small class="muted">${x.locations.map(esc).join('<br>')}</small>`:''}`:esc(x.path);
    const status=!x.ok?`<span class="status-pill Failed">Problem</span> ${esc(x.error)}`:(x.error?`<span class="muted">${esc(x.error)}</span>`:'<span class="status-pill Completed">Read</span>');
    return `<tr><td>${x.kind==='plex'?'Plex: '+esc(x.server):esc(x.source)}</td><td class="wrap">${name}</td><td>${x.error&&x.ok?'—':esc(x.count)}</td><td class="wrap">${status}</td></tr>`;}).join('');
}
$('movieSettings').onsubmit=async e=>{
  e.preventDefault();const body={};
  for(const el of e.target.elements){if(!el.name)continue;body[el.name]=el.type==='checkbox'?(el.checked?'1':'0'):el.value;}
  try{await post('/api/movies/settings',body);setMessage($('settingsMessage'),'Saved.','success');await loadSettings();loadSummary();}catch(err){setMessage($('settingsMessage'),err.message,'error');}
};
document.querySelectorAll('.job-run').forEach(b=>b.onclick=async()=>{b.disabled=true;const label=b.textContent;try{await post(`/api/movies/jobs/${b.dataset.job}/run`);b.textContent='Started — see Jobs/Logs';setTimeout(()=>{b.disabled=false;b.textContent=label;loadSummary();loadMovies();},4000);}catch(e){b.disabled=false;alert(e.message);}});

loadSummary();loadMovies();
try{const h=location.hash.slice(1);const t=['library','discover','downloads','settings'].includes(h)?h:localStorage.getItem('tvmanager.movies.tab');if(t&&t!=='library')showTab(t);}catch{}

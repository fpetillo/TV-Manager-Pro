const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const num=v=>Number(v||0).toLocaleString();
// SQLite CURRENT_TIMESTAMP values are UTC ("YYYY-MM-DD HH:MM:SS"); ISO values with a "T" are server-local.
function parseWhen(v){if(!v)return null;const s=String(v);const d=new Date(/^\d{4}-\d\d-\d\d \d\d:\d\d/.test(s)?s.replace(' ','T')+'Z':s);return isNaN(d)?null:d;}
function ago(v){const d=parseWhen(v);if(!d)return esc(v||'—');const m=Math.round((Date.now()-d)/60000);
 const t=m<1?'just now':m<60?`${m} min ago`:m<1440?`${Math.round(m/60)} h ago`:m<10080?`${Math.round(m/1440)} d ago`:d.toLocaleDateString();
 return `<time datetime="${esc(d.toISOString())}" title="${esc(d.toLocaleString())}">${t}</time>`;}
const kpi=(label,value,href,tone)=>`<a class="media-kpi ${tone||''}" href="${href}"><strong>${num(value)}</strong><span>${esc(label)}</span></a>`;
const typePill=t=>t==='movie'?'<span class="type-pill movie">Movie</span>':'<span class="type-pill tv">TV</span>';
const tmdbPoster=p=>p?`https://image.tmdb.org/t/p/w185${p}`:'';
const JOB_LABELS={movie_library_scan:'Movie library scan',movie_discovery:'Movie discovery',movie_search:'Movie search',movie_downloads:'Movie downloads & import'};
const jobGroup=n=>n.startsWith('movie_')?'Movies':(/database|backup|artwork|library_health/.test(n)?'System':'TV');
let downloadFilter='all',lastData=null;

function renderOverview(d,health){
 const s=d.stats||{},m=(d.movies&&d.movies.counts)||{};
 document.getElementById('tvKpis').innerHTML=[kpi('Shows',s.shows,'/show-queue'),kpi('Episodes',s.episodes,'/show-queue'),kpi('Downloaded',s.downloaded,'/show-queue','good'),
  kpi('Wanted',s.wanted,'/missing',s.wanted?'warn':''),kpi('Downloading',s.snatched,'/queue',s.snatched?'live':''),kpi('Upcoming',s.unaired,'/upcoming')].join('');
 document.getElementById('movieKpis').innerHTML=[kpi('In library',m.owned,'/movies','good'),kpi('Wanted',m.wanted,'/movies',m.wanted?'warn':''),
  kpi('Downloading',m.downloading,'/movies',m.downloading?'live':''),kpi('Coming to digital',m.waiting,'/upcoming'),
  kpi('Added this week',m.imported_week,'/movies'),kpi('Failed this week',m.failed_week,'/movies',m.failed_week?'bad':'')].join('');
 const armed=!!health.automation;
 const tv=document.getElementById('tvState');tv.className='media-state '+(armed?'ok':'warn');
 tv.textContent=armed?`Automation on · ${num(health.providers)} indexer${health.providers==1?'':'s'}`:'Automation paused — scheduled searches are not running';
 const ms=document.getElementById('movieState'),problems=(d.movies&&d.movies.problems)||[];
 if(d.movies&&d.movies.error){ms.className='media-state warn';ms.textContent='Movie summary unavailable';}
 else if(problems.length){ms.className='media-state warn';ms.innerHTML=`Needs setup: <a href="${esc(problems[0].href)}">${esc(problems[0].title)}</a>${problems.length>1?` and ${problems.length-1} more`:''}`;}
 else if(!armed){ms.className='media-state warn';ms.textContent='Automation paused — movie jobs are not running';}
 else{const next=d.movies.next_release;ms.className='media-state ok';ms.textContent='Running automatically'+(next?` · next: ${next.title} on ${next.available_date}`:'');}
}

function renderRecent(d){
 const movies=((d.movies&&d.movies.recent)||[]).map(x=>({type:'movie',title:x.title,sub:[x.year,x.quality].filter(Boolean).join(' · '),img:tmdbPoster(x.poster_path),href:`/movie/${x.id}`,when:x.downloaded_at}));
 const seen=new Set();
 const tv=(d.downloads||[]).filter(x=>String(x.status).toLowerCase()==='completed'&&x.show_name).filter(x=>{const k=`${x.show_name}|${x.season}|${x.episode}`;if(seen.has(k))return false;seen.add(k);return true;})
  .map(x=>({type:'tv',title:x.show_name,sub:x.season!=null?`S${String(x.season).padStart(2,'0')}E${String(x.episode).padStart(2,'0')}`:'',img:x.show_poster||'',href:x.show_id?`/show/${x.show_id}`:'/queue',when:x.completed_at||x.added_at}));
 const items=movies.concat(tv).sort((a,b)=>(parseWhen(b.when)||0)-(parseWhen(a.when)||0)).slice(0,16);
 document.getElementById('recentNote').textContent=items.length?`${items.length} latest`:'';
 const fallback=t=>`<span class="poster-fallback">${t==='movie'?'🎬':'TV'}</span>`;
 document.getElementById('recentRail').innerHTML=items.length?items.map(x=>`<a class="poster-tile ${x.type}" href="${esc(x.href)}"><span class="poster-frame">${x.img?`<img loading="lazy" alt="" src="${esc(x.img)}" data-fallback="${x.type}">`:fallback(x.type)}${typePill(x.type)}</span><strong>${esc(x.title)}</strong><small>${esc(x.sub)}</small><small class="muted">${ago(x.when)}</small></a>`).join('')
  :'<div class="empty-state compact">New episodes and movies appear here as soon as they are imported.</div>';
 document.querySelectorAll('#recentRail img[data-fallback]').forEach(img=>img.addEventListener('error',()=>{img.outerHTML=fallback(img.dataset.fallback);},{once:true}));
}

function renderDownloads(){
 const d=lastData;if(!d)return;
 const tv=(d.downloads||[]).map(x=>({type:'tv',name:x.show_name?`${x.show_name}${x.season!=null?` S${String(x.season).padStart(2,'0')}E${String(x.episode).padStart(2,'0')}`:''}`:x.release_name,release:x.release_name,status:x.status,client:x.client,when:x.added_at,href:x.show_id?`/show/${x.show_id}`:'/queue'}));
 const mv=(d.movie_downloads||[]).map(x=>({type:'movie',name:`${x.title}${x.year?` (${x.year})`:''}`,release:x.release_name,status:x.status,client:x.client,when:x.created_at,href:`/movie/${x.movie_id}`}));
 const rows=tv.concat(mv).filter(x=>downloadFilter==='all'||x.type===downloadFilter).sort((a,b)=>(parseWhen(b.when)||0)-(parseWhen(a.when)||0)).slice(0,14);
 document.getElementById('downloads').innerHTML=rows.length?rows.map(x=>`<a class="feed-row" href="${esc(x.href)}">${typePill(x.type)}<div class="feed-main"><strong>${esc(x.name)}</strong><small>${esc(x.release)}</small></div><div class="feed-side"><span class="status-pill ${esc(x.status)}">${esc(x.status)}</span><small>${esc(x.client||'')} · ${ago(x.when)}</small></div></a>`).join('')
  :'<div class="empty-state compact">No downloads yet.</div>';
}

function renderActivity(list){
 document.getElementById('activity').innerHTML=list.length?list.slice(0,14).map(x=>{const movie=String(x.event_type||'').startsWith('movie_');const lvl=String(x.level||'info').toLowerCase();
  return `<div class="feed-row activity ${esc(lvl)}">${movie?typePill('movie'):x.show_name?typePill('tv'):'<span class="type-pill sys">System</span>'}<div class="feed-main"><strong>${esc(x.message)}</strong></div><div class="feed-side"><small>${ago(x.created_at)}</small></div></div>`}).join('')
  :'<div class="empty-state compact">No activity yet.</div>';
}

function every(n){return n>=60&&n%60===0?`${n/60} h`:`${n} min`;}
function renderJobs(jobs){
 const groups={TV:[],Movies:[],System:[]};
 for(const j of jobs)groups[jobGroup(j.name)].push(j);
 document.getElementById('jobs').innerHTML=Object.entries(groups).filter(([,l])=>l.length).map(([g,l])=>`<div class="job-group"><h3>${g}</h3>${l.map(j=>`<div class="scheduler-row dashboard-job"><div><strong>${esc(JOB_LABELS[j.name]||j.name.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()))}</strong><div class="muted">${esc(j.last_status||'Never run')}</div></div><div>${j.enabled?'<span class="status-pill Downloaded">Enabled</span>':'<span class="status-pill">Paused</span>'}</div><div>every ${every(j.interval_minutes)}</div><div>${j.last_run?ago(j.last_run):'—'}</div></div>`).join('')}</div>`).join('');
}

function renderHealth(d,health){
 const lh=d.library_health||{},m=d.movies||{};
 const issues=(m.problems||[]).length;
 document.getElementById('health').innerHTML=`<div class="notice ${health.automation?'good':'warn'}">Automation ${health.automation?'armed':'paused'}</div><div class="health-lines"><div><span>Indexers</span><strong>${num(health.providers)}</strong></div><div><span>Database</span><strong>OK</strong></div><div><span>Missing episode files</span><strong>${num(lh.missing_episode_files)}</strong></div><div><span>Duplicate groups</span><strong>${num(lh.duplicate_groups)}</strong></div><div><span>Movie automation</span><strong class="${issues?'warn-text':'ok-text'}">${issues?`${issues} to fix`:'Ready'}</strong></div></div><a class="btn secondary" href="/library-health">Open Library Health</a>`;
}

async function load(){
 try{
  const [r,h]=await Promise.all([fetch('/api/dashboard/full'),fetch('/api/health')]);const d=await r.json(),health=await h.json();
  lastData=d;renderOverview(d,health);renderRecent(d);renderDownloads();renderActivity(d.activity||[]);renderJobs(d.jobs||[]);renderHealth(d,health);
 }catch(e){document.getElementById('tvState').textContent='Dashboard could not load: '+e.message;}
}
document.querySelectorAll('.segmented .seg').forEach(b=>b.onclick=()=>{downloadFilter=b.dataset.filter;document.querySelectorAll('.segmented .seg').forEach(x=>x.classList.toggle('active',x===b));renderDownloads();});
load();setInterval(load,30000);
const RANK={bad:0,error:0,warn:1,info:2,good:3};
fetch('/api/insights').then(r=>r.json()).then(d=>{document.getElementById('insights').innerHTML=d.results.slice().sort((a,b)=>(RANK[a.severity]??2)-(RANK[b.severity]??2)).slice(0,4).map(x=>`<a class="insight-card ${esc(x.severity)}" href="${esc(x.href)}"><strong>${esc(x.title)}</strong><span>${esc(x.detail)}</span></a>`).join('')});

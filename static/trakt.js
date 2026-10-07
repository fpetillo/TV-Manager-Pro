const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const msg=document.getElementById('traktMessage');
const results=document.getElementById('traktResults');
async function jsonFetch(url,opt){const r=await fetch(url,opt);const ct=r.headers.get('content-type')||'';const d=ct.includes('application/json')?await r.json():{error:await r.text()};if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
async function loadStatus(){try{const d=await jsonFetch('/api/trakt/status');traktStatus.className=d.configured?'notice good':'notice warn';traktStatus.textContent=d.message+(d.credential_source?` Source: ${d.credential_source}.`:'');}catch(e){traktStatus.className='notice error';traktStatus.textContent=e.message;}}
async function saveSettings(){try{await jsonFetch('/api/trakt/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:traktClientId.value,access_token:traktAccessToken.value})});traktClientId.value='';traktAccessToken.value='';await loadStatus();msg.className='message success';msg.textContent='Trakt settings saved. Restart is not required.';}catch(e){msg.className='message error';msg.textContent=e.message;}}
function metric(row){if(row.watchers)return `${Number(row.watchers).toLocaleString()} watchers`;if(row.list_count)return `${Number(row.list_count).toLocaleString()} lists`;if(row.rank_score)return `Score ${row.rank_score}`;return row.category||'';}
async function addShow(button,row){button.disabled=true;button.textContent='Adding…';try{const destination=await chooseShowDestination(row.name||row.title);if(!destination){button.disabled=false;button.textContent='Add';return;}const d=await jsonFetch('/api/trakt/add-show',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...row,...destination})});button.textContent=d.created?'Added':'Already in Library';button.className='secondary';}catch(e){button.disabled=false;button.textContent='Add';alert(e.message);}}
function card(row,i){return `<article class="trakt-card"><div class="trakt-card-head"><div><p class="eyebrow">${esc(metric(row))}</p><h3>${esc(row.name)} ${row.year?`<span>(${esc(row.year)})</span>`:''}</h3></div><span class="status-pill ${esc(row.status||'Wanted')}">${esc(row.status||'new')}</span></div><p>${esc(row.overview||'No overview returned by Trakt.')}</p><div class="result-meta">${[row.network,row.country,row.imdb_id,row.tmdb_id?'TMDb '+row.tmdb_id:null].filter(Boolean).map(esc).join(' • ')}</div><div class="actions"><button class="blue add-trakt" data-i="${i}" ${row.saved?'disabled':''}>${row.saved?'Already in Library':'Add Show'}</button>${row.imdb_id?`<a class="btn secondary" target="_blank" href="https://www.imdb.com/title/${esc(row.imdb_id)}/">IMDb</a>`:''}</div></article>`;}
const FILTER_KEY='tvmanager.trakt.filters';
let nextPage=null;
function readFilters(){try{return JSON.parse(localStorage.getItem(FILTER_KEY)||'{}')||{};}catch{return {};}}
function saveFilters(){try{localStorage.setItem(FILTER_KEY,JSON.stringify({hide:traktHideLibrary.checked,from:traktYearFrom.value,to:traktYearTo.value}));}catch{}}
(()=>{const f=readFilters();traktHideLibrary.checked=!!f.hide;traktYearFrom.value=f.from||'';traktYearTo.value=f.to||'';})();
function bindAddButtons(){document.querySelectorAll('.add-trakt').forEach(b=>b.onclick=()=>addShow(b,window.traktRows[+b.dataset.i]));}
async function loadShows(more){
  saveFilters();
  if(!more){window.traktRows=[];results.innerHTML='<div class="loading-box">Loading Trakt discovery…</div>';}
  msg.className='message';msg.textContent=more?'Loading more Trakt shows…':'Loading Trakt shows…';
  traktMore.disabled=true;loadTrakt.disabled=true;
  try{
    const p=new URLSearchParams({category:traktCategory.value,q:traktSearch.value.trim(),limit:traktLimit.value,page:String(more&&nextPage?nextPage:1)});
    if(traktHideLibrary.checked)p.set('hide_library','1');
    if(traktYearFrom.value.trim())p.set('year_from',traktYearFrom.value.trim());
    if(traktYearTo.value.trim())p.set('year_to',traktYearTo.value.trim());
    const d=await jsonFetch('/api/trakt/shows?'+p);
    const start=window.traktRows.length;
    window.traktRows=window.traktRows.concat(d.results||[]);
    const html=(d.results||[]).map((row,i)=>card(row,start+i)).join('');
    if(more)results.insertAdjacentHTML('beforeend',html);else results.innerHTML=html||'<div class="notice warn">No shows returned for this filter.</div>';
    bindAddButtons();
    nextPage=d.next_page||null;traktMore.hidden=!nextPage;
    const parts=[`Showing ${window.traktRows.length} Trakt show${window.traktRows.length===1?'':'s'}`];
    if(d.years)parts.push(`first aired ${d.years.replace('1900-','up to ').replace(/-2100$/,' or later')}`);
    if(d.hide_library)parts.push(`${d.hidden_in_library||0} already in your library hidden`);
    msg.className='message success';msg.textContent=parts.join(' · ')+'.';
  }catch(e){msg.className='message error';msg.textContent=e.message;if(!more)results.innerHTML='';}
  finally{traktMore.disabled=false;loadTrakt.disabled=false;}
}
traktMore.onclick=()=>loadShows(true);
traktHideLibrary.onchange=()=>{saveFilters();if(window.traktRows&&window.traktRows.length)loadShows();};
[traktYearFrom,traktYearTo].forEach(i=>i.addEventListener('keydown',e=>{if(e.key==='Enter')loadShows()}));
traktClearFilters.onclick=()=>{traktHideLibrary.checked=false;traktYearFrom.value='';traktYearTo.value='';saveFilters();if(window.traktRows&&window.traktRows.length)loadShows();};
saveTrakt.onclick=saveSettings;loadTrakt.onclick=()=>loadShows();traktSearch.addEventListener('keydown',e=>{if(e.key==='Enter')loadShows()});
loadStatus();

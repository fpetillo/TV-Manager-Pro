const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
let sort='downloads',direction='desc',offset=0,total=0,ignoreS00=false;
const numericDefaultDesc=new Set(['downloads','missing','download_percent','size','active']);
function fmtDate(v){
  if(!v)return '';
  const s=String(v).trim();
  let y,m,d;
  const iso=s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if(iso){y=iso[1];m=iso[2];d=iso[3];return `${Number(m)}/${Number(d)}/${y}`;}
  const compact=s.match(/^(\d{4})(\d{2})(\d{2})$/);
  if(compact){y=compact[1];m=compact[2];d=compact[3];return `${Number(m)}/${Number(d)}/${y}`;}
  const us=s.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})$/);
  if(us)return `${Number(us[1])}/${Number(us[2])}/${us[3]}`;
  return s;
}
function fmtSize(bytes){bytes=Number(bytes||0); if(bytes<=0)return '0.00 B'; const u=['B','KB','MB','GB','TB']; let i=0; while(bytes>=1024&&i<u.length-1){bytes/=1024;i++;} return `${bytes.toFixed(i?2:0)} ${u[i]}`;}
function pct(d,t){d=Number(d||0);t=Number(t||0);return t?Math.round((d/t)*100):0}
function showQueueNavigationLoading(name){let box=document.getElementById('queueNavigationLoading');if(!box){box=document.createElement('div');box.id='queueNavigationLoading';box.className='show-page-loading';document.body.appendChild(box)}box.hidden=false;box.innerHTML=`<div class="import-progress show-loading-progress"><div class="progress-head"><strong>Loading show</strong><span>Working</span></div><div class="progress-track indeterminate"><div class="progress-fill" style="width:45%"></div></div><p class="muted">Opening ${esc(name||'show')} and loading episode counts…</p></div>`;}
function setSortIndicators(){
  document.querySelectorAll('.show-queue-table th[data-sort]').forEach(th=>{
    const label=th.dataset.label||th.textContent.replace(/[▲▼]/g,'').trim();
    th.dataset.label=label;
    th.classList.toggle('sorted', th.dataset.sort===sort);
    th.setAttribute('aria-sort', th.dataset.sort===sort ? (direction==='desc'?'descending':'ascending') : 'none');
    th.textContent=label + (th.dataset.sort===sort ? (direction==='desc'?' ▼':' ▲') : '');
  });
}
async function jsonFetch(url){const r=await fetch(url);const ct=r.headers.get('content-type')||'';const d=ct.includes('application/json')?await r.json():{error:await r.text()};if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
async function load(){
  showQueueSummary.textContent='Loading…';
  showQueueMessage.textContent='';
  setSortIndicators();
  try{
    const p=new URLSearchParams({q:showQueueSearch.value.trim(),status:showQueueStatus.value,active:showQueueActive.value,limit:showQueueLimit.value,offset:String(offset),sort,direction});
    const d=await jsonFetch('/api/show-queue?'+p);
    total=d.total||0;
    const rows=d.results||[];
    ignoreS00=!!d.ignore_season_zero_counts; showQueueSummary.textContent=total?`Showing ${offset+1}-${offset+rows.length} of ${Number(total).toLocaleString()} shows · sorted by ${sort} ${direction}${ignoreS00?' · S00 ignored':''}`:'0 shows';
    showQueueBody.innerHTML=rows.length?rows.map(r=>{
      const pp=Number(r.download_percent??pct(r.downloaded_count,r.episode_count));
      const downloaded=Number(r.downloaded_count||0);
      const totalEpisodes=Number(r.episode_count||0);
      const missing=Number(r.missing_count||Math.max(totalEpisodes-downloaded,0));
      const meterClass=totalEpisodes===0?'empty':(downloaded>=totalEpisodes?'complete':(downloaded>0?'partial':'empty'));
      const missingText=esc(r.missing_display||r.missing_episode_numbers||(missing?`${missing} missing`:'Complete'));
      return `<tr data-show-id="${esc(r.id)}"><td>${esc(fmtDate(r.next_ep))}</td><td>${esc(fmtDate(r.prev_ep))}</td><td><a class="show-open-link" data-show-name="${esc(r.name)}" href="/show/${r.id}"><strong>${esc(r.name)}</strong></a><div class="muted tiny">Missing: ${missingText}</div></td><td>${esc(r.network||'')}</td><td><span class="quality-badge">${esc(r.quality||'HD')}</span></td><td class="downloads-cell" title="${downloaded} downloaded, ${missing} missing, ${totalEpisodes} total${ignoreS00?' (S00 ignored)':''}"><div class="download-meter ${meterClass}"><span style="width:${Math.max(0,Math.min(100,pp))}%"></span><strong>${downloaded}/${totalEpisodes}</strong></div><small>${missing} missing${ignoreS00?' · no S00':''}</small></td><td class="num-cell">${esc(fmtSize(r.size_bytes))}</td><td class="center-cell">${r.active_flag?'✓':'—'}</td><td><span class="status-pill ${esc(r.status)}">${esc(r.status)}</span></td></tr>`
    }).join(''):'<tr><td colspan="9">No shows match this filter.</td></tr>';
    showQueuePrev.disabled=offset<=0;
    showQueueNext.disabled=!d.has_more;
  }catch(e){
    showQueueSummary.textContent='Show queue load error';
    showQueueBody.innerHTML='<tr><td colspan="9">Could not load show queue.</td></tr>';
    showQueueMessage.className='message error';
    showQueueMessage.textContent=e.message;
  }
}
document.querySelectorAll('.show-queue-table th[data-sort]').forEach(th=>{th.onclick=()=>{const ns=th.dataset.sort;if(sort===ns){direction=direction==='asc'?'desc':'asc'}else{sort=ns;direction=numericDefaultDesc.has(ns)?'desc':'asc'};offset=0;load();}});
let timer=null;showQueueSearch.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{offset=0;load()},250)};showQueueStatus.onchange=()=>{offset=0;load()};showQueueActive.onchange=()=>{offset=0;load()};showQueueLimit.onchange=()=>{offset=0;load()};showQueueRefresh.onclick=()=>load();showQueuePrev.onclick=()=>{offset=Math.max(0,offset-Number(showQueueLimit.value||100));load()};showQueueNext.onclick=()=>{offset+=Number(showQueueLimit.value||100);load()};
load();

document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('.show-open-link');if(a){showQueueNavigationLoading(a.dataset.showName||a.textContent||'show');}});

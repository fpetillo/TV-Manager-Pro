const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
function stat(label,value){return `<div class="kpi premium-kpi"><span>${esc(label)}</span><strong>${esc(value??0)}</strong></div>`}
function actionCard(a){return `<article class="next-action ${esc(a.priority)}"><div><span>${esc(a.priority)}</span><h3>${esc(a.title)}</h3><p>${esc(a.detail)}</p></div><a class="btn ${a.priority==='critical'?'blue':'secondary'}" href="${esc(a.href)}">${esc(a.label)}</a></article>`}
async function loadLaunchpad(){
  const actions=document.getElementById('nextActions'), stats=document.getElementById('launchStats');
  try{
    const r=await fetch('/api/launchpad/summary');
    const text=await r.text();
    let d; try{ d=JSON.parse(text); }catch(e){ throw new Error(`Launchpad API returned ${r.status}: ${text.slice(0,160)}`); }
    if(!r.ok || d.ok===false) throw new Error(d.error||r.statusText);
    document.getElementById('readyScore').textContent=(d.readiness_score||0)+'%';
    document.getElementById('readyLabel').textContent=d.readiness_label || (d.readiness||'unknown').replaceAll('_',' ');
    const explain=document.getElementById('readinessExplain');
    if(explain){explain.className='notice info';explain.textContent=d.readiness_explanation || 'Replacement readiness summarizes import, health, metadata, downloader setup, and cutover status.';}
    const c=d.counts||{};
    stats.innerHTML=[stat('Shows',c.shows),stat('Episodes',c.episodes),stat('Imports',c.import_runs),stat('Missing files',c.missing_files),stat('Duplicate groups',c.duplicate_groups),stat('Folder gaps',c.shows_without_location),stat('Metadata gaps',c.metadata_gaps),stat('Version',d.version)].join('');
    actions.innerHTML=(d.actions||[]).map(actionCard).join('') || '<div class="empty-list">No recommended actions right now.</div>';
  }catch(e){
    document.getElementById('readyLabel').textContent='Not loaded';
    document.getElementById('readyScore').textContent='!';
    const explain=document.getElementById('readinessExplain');
    if(explain){explain.className='notice error';explain.textContent='Replacement readiness could not load. Open /api/launchpad/summary or Logs to see the server-side issue.';}
    actions.innerHTML=`<div class="notice error">Launchpad failed: ${esc(e.message||e)}</div>`;
  }
}
document.addEventListener('DOMContentLoaded',()=>{loadLaunchpad();document.getElementById('refreshLaunchpad')?.addEventListener('click',loadLaunchpad)});

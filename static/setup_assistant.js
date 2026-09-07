const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
function stat(label,value){return `<div class="kpi premium-kpi"><span>${esc(label)}</span><strong>${esc(value??0)}</strong></div>`}
function stageCard(s,i){return `<article class="setup-stage ${esc(s.status)}"><div class="setup-step-number">${i+1}</div><div><div class="setup-stage-top"><h3>${esc(s.title)}</h3><span>${esc(s.status)}</span></div><p>${esc(s.detail)}</p><a class="btn ${s.status==='next'||s.status==='attention'?'blue':'secondary'}" href="${esc(s.href)}">${esc(s.action)}</a></div></article>`}
async function loadSetupAssistant(){
  const stages=document.getElementById('setupStages'), stats=document.getElementById('setupStats'), blockers=document.getElementById('setupBlockers');
  try{
    const r=await fetch('/api/setup/summary');
    const text=await r.text();
    let d; try{d=JSON.parse(text)}catch(e){throw new Error(`Setup API returned ${r.status}: ${text.slice(0,180)}`)}
    if(!r.ok||d.ok===false) throw new Error(d.error||r.statusText);
    const c=d.counts||{};
    const score=d.ready_for_cutover?100:(c.shows?65:25);
    document.getElementById('setupReadyScore').textContent=score+'%';
    document.getElementById('setupReadyLabel').textContent=d.ready_for_cutover?'ready for cutover':(c.shows?'needs operator review':'import required');
    stats.innerHTML=[stat('Shows',c.shows),stat('Episodes',c.episodes),stat('Imports',c.imports),stat('Missing files',c.missing_files),stat('Duplicate groups',c.duplicate_groups),stat('Folder gaps',c.folder_gaps),stat('Metadata gaps',c.metadata_gaps),stat('Version',d.version)].join('');
    stages.innerHTML=(d.stages||[]).map(stageCard).join('');
    blockers.innerHTML=(d.blockers||[]).length?`<ul class="blocker-list">${d.blockers.map(b=>`<li>${esc(b)}</li>`).join('')}</ul>`:'<div class="notice good">No major cutover blockers are currently reported.</div>';
  }catch(e){
    stages.innerHTML=`<div class="notice error">Setup Assistant failed: ${esc(e.message||e)}</div>`;
    blockers.innerHTML='<div class="notice warn">Unable to load blocker details.</div>';
  }
}
document.addEventListener('DOMContentLoaded',()=>{loadSetupAssistant();document.getElementById('refreshSetup')?.addEventListener('click',loadSetupAssistant)});

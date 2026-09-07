const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
function badge(status){return `<span class="workflow-status ${esc(status)}">${esc(status)}</span>`}
function stepCard(s,i){return `<article class="workflow-step ${esc(s.status)}"><div class="workflow-number">${i+1}</div><div><h3>${esc(s.label)} ${badge(s.status)}</h3><p>${esc(s.detail)}</p></div></article>`}
async function loadWorkflow(){
  const stages=document.getElementById('workflowStages'), rec=document.getElementById('workflowRecommendations'), snap=document.getElementById('readinessSnapshot');
  try{
    const r=await fetch('/api/workflow/summary');
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||r.statusText);
    stages.innerHTML=(d.steps||[]).map(stepCard).join('');
    const recommendations=d.recommendations&&d.recommendations.length?d.recommendations:['Run a SickChill import preview, then validate Library Health before cutover.'];
    rec.innerHTML=recommendations.map(x=>`<div class="action-row"><span>Next</span><strong>${esc(x)}</strong></div>`).join('');
    const stats=d.stats||{}, hc=d.health_counts||{};
    snap.innerHTML=`<div><span>Shows</span><strong>${esc(stats.shows||0)}</strong></div><div><span>Episodes</span><strong>${esc(stats.episodes||0)}</strong></div><div><span>Missing Files</span><strong>${esc(hc.missing_files||0)}</strong></div><div><span>Duplicate Groups</span><strong>${esc(hc.duplicate_groups||0)}</strong></div>`;
  }catch(e){
    stages.innerHTML=`<div class="notice error">Workflow summary failed: ${esc(e.message||e)}</div>`;
  }
}
document.addEventListener('DOMContentLoaded',()=>{loadWorkflow();document.getElementById('refreshWorkflow')?.addEventListener('click',loadWorkflow)});

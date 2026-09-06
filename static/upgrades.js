
const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
async function load(){refreshUpgrades.disabled=true;const r=await fetch("/api/upgrades"),d=await r.json();upgradeSummary.innerHTML=`<div class="notice ${d.count?"warn":"good"}">${d.count} downloaded episode(s) are below their assigned quality cutoff.</div>`;upgradeList.innerHTML=d.results.length?d.results.map(x=>`<div class="result-card"><div class="result-top"><strong>${esc(x.show_name)} S${String(x.season).padStart(2,"0")}E${String(x.episode).padStart(2,"0")}</strong><span class="status-pill Wanted">${esc(x.current_quality||"Unknown")} → ${esc(x.target_quality)}</span></div><p>${esc(x.reason)}</p><div class="actions"><a class="btn secondary" href="/manager?show=${x.show_id||""}">Open Show</a></div></div>`).join(""):'<div class="notice good">No upgrade candidates.</div>';refreshUpgrades.disabled=false}
refreshUpgrades.onclick=load;load();

loadPropers.onclick=async()=>{const r=await fetch("/api/upgrades/propers"),d=await r.json();properList.innerHTML=d.results.length?d.results.map(x=>`<div class="result-card"><strong>${esc(x.show)} S${String(x.season).padStart(2,"0")}E${String(x.episode).padStart(2,"0")}</strong><p>${esc(x.reason)}</p><small>${esc(x.current_release||"Unknown current release")}</small><div class="actions"><button class="secondary action-btn" onclick="searchProper(${x.episode_id},this)">Search Proper/Repack</button></div></div>`).join(""):'<div class="notice good">No obvious Proper/Repack review candidates.</div>'};

window.searchProper=async(id,b)=>{b.disabled=true;b.textContent="Searching…";const r=await fetch(`/api/upgrades/propers/${id}/search`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({grab:false})}),d=await r.json();b.disabled=false;b.textContent="Search Proper/Repack";if(!r.ok)return alert(d.error||"Search failed");if(!d.candidates.length)return alert("No acceptable Proper/Repack results found.");const best=d.candidates[0];if(confirm(`Best candidate:\n${best.title}\nScore ${Math.round(best.score)}\n\nGrab this release?`)){const g=await fetch(`/api/upgrades/propers/${id}/search`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({grab:true})}),gd=await g.json();alert(g.ok?`Queued in ${gd.grabbed.client}.`:(gd.error||"Grab failed"))}}

loadReplacementHistory.onclick=async()=>{
  const r=await fetch("/api/upgrades/replacements"),d=await r.json();
  replacementHistory.innerHTML=d.results?.length?d.results.map(x=>`<div class="service-card"><div class="result-top"><strong>${esc(x.show_name)} S${String(x.season).padStart(2,"0")}E${String(x.episode).padStart(2,"0")}</strong><span class="status-pill">${esc(x.status)}</span></div><p>${esc(x.old_release||"Original")} → ${esc(x.new_release||"Replacement")}</p><small>${esc(x.created_at||"")}</small>${x.status==="Completed"?`<div class="actions"><button class="secondary action-btn" onclick="rollbackReplacement(${x.id})">Rollback</button></div>`:""}</div>`).join(""):'<p class="muted">No upgrade replacements recorded yet.</p>';
}
window.rollbackReplacement=async id=>{
  if(!confirm("Restore the previous episode file from managed trash?"))return;
  const r=await fetch(`/api/upgrades/replacements/${id}/rollback`,{method:"POST"}),d=await r.json();
  alert(r.ok?`Restored ${d.restored}`:(d.error||"Rollback failed"));loadReplacementHistory.onclick();
}

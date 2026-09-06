const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const epLabel=x=>(x.episodes||[]).map(e=>`E${String(e).padStart(2,"0")}`).join("")||"";
function render(d){
  summary.innerHTML=`<div class="dashboard-grid">
    <div class="dash-card"><span>Files scanned</span><strong>${d.files||0}</strong></div>
    <div class="dash-card"><span>Episodes matched</span><strong>${d.matched||0}</strong></div>
    <div class="dash-card"><span>Blocked</span><strong>${d.blocked||0}</strong></div>
    <div class="dash-card"><span>Upgrades</span><strong>${d.upgrades||0}</strong></div>
    <div class="dash-card"><span>Unmatched</span><strong>${d.unmatched||0}</strong></div>
    <div class="dash-card"><span>Mode</span><strong>${d.dry_run?"Preview":"Processed"}</strong></div>
  </div>${d.message?`<div class="notice warn">${esc(d.message)}</div>`:""}`;
  actions.innerHTML=d.actions?.length?`<table class="compact-table"><tr>
    <th>Show / Episode</th><th>Quality</th><th>Source</th><th>Final library path</th><th>Decision</th>
  </tr>${d.actions.map(x=>`<tr>
    <td><strong>${esc(x.show)}</strong><br>S${String(x.season).padStart(2,"0")}${epLabel(x)}</td>
    <td>${esc(x.quality||"Unknown")}</td>
    <td>${esc(x.source)}</td>
    <td>${x.renamed?'<span class="status-pill Downloaded">Renamed</span> ':''}${esc(x.destination)}</td>
    <td>${x.blocked?`<span class="status-pill Failed">Blocked</span><br>${esc(x.blocked)}`:`<span class="status-pill Downloaded">Approved</span>${x.naming_pattern?`<br><small>${esc(x.naming_pattern)}</small>`:""}`}</td>
  </tr>`).join("")}</table>`:'<p class="muted">No matched files.</p>';
}
scan.onclick=async()=>{message.textContent="Scanning and calculating final names…";const r=await fetch("/api/postprocess/scan"),d=await r.json();message.textContent="";render(d)}
run.onclick=async()=>{if(!confirm("Process all approved files using the imported naming and post-processing settings? Blocked upgrades will be left untouched."))return;run.disabled=true;message.textContent="Processing…";const r=await fetch("/api/postprocess/run",{method:"POST"}),d=await r.json();message.className=r.ok?"message success":"message error";message.textContent=r.ok?"Processing complete.":(d.error||"Processing failed");if(r.ok)render(d);run.disabled=false}

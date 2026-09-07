const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const $=id=>document.getElementById(id);
const epLabel=x=>(x.episodes||[]).map(e=>`E${String(e).padStart(2,"0")}`).join("")||"";
let lastPreview=[];

async function readJsonResponse(resp){
  const text=await resp.text();
  try{return JSON.parse(text||"{}");}
  catch(e){throw new Error(`HTTP ${resp.status}: ${text.slice(0,260)}`);}
}
function activeRoot(){return ($("overrideDir")?.value||"").trim() || ($("defaultDir")?.value||"").trim();}
function selectedSources(){return [...document.querySelectorAll(".pp-select:checked")].map(x=>x.value);}
function setMessage(text,kind=""){$("message").className=`message ${kind}`.trim();$("message").textContent=text||"";}
function progressHtml(job){const pct=Math.max(0,Math.min(100,Number(job?.percent||0)));return `<div class="import-progress"><div class="progress-head"><strong>${esc(job?.stage||job?.status||"Working")}</strong><span>${pct}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><p class="muted">${esc(job?.message||"Working in the background…")}</p></div>`}
async function pollPostprocessJob(jobId){for(;;){const r=await fetch(`/api/jobs/${encodeURIComponent(jobId)}`),d=await readJsonResponse(r),j=d.job||{};$("message").className="message info";$("message").innerHTML=progressHtml(j);if(["complete","error","cancelled"].includes(String(j.status||"")))return j;await new Promise(x=>setTimeout(x,900));}}

async function loadConfig(){
  try{
    const r=await fetch("/api/postprocess/config");
    const d=await readJsonResponse(r);
    $("defaultDir").value=d.tv_download_dir||"";
    $("method").value=d.process_method||"move";
  }catch(e){setMessage(`Could not load post-processing settings: ${e.message}`,"error");}
}

function render(d){
  lastPreview=d.actions||[];
  $("summary").innerHTML=`<div class="dashboard-grid">
    <div class="dash-card"><span>Folder</span><strong title="${esc(d.root||"")}">${esc(d.root?"Ready":"Missing")}</strong></div>
    <div class="dash-card"><span>Files scanned</span><strong>${d.files||0}</strong></div>
    <div class="dash-card"><span>Episodes matched</span><strong>${d.matched||0}</strong></div>
    <div class="dash-card"><span>Blocked</span><strong>${d.blocked||0}</strong></div>
    <div class="dash-card"><span>Upgrades</span><strong>${d.upgrades||0}</strong></div>
    <div class="dash-card"><span>Unmatched</span><strong>${d.unmatched||0}</strong></div>
  </div>${d.message?`<div class="notice warn">${esc(d.message)}</div>`:""}`;
  $("actions").innerHTML=lastPreview.length?`<table class="compact-table postprocess-table"><tr>
    <th><input id="selectAll" type="checkbox" checked title="Select all approved"></th><th>Show / Episode</th><th>Quality</th><th>Source</th><th>Final library path</th><th>Decision</th>
  </tr>${lastPreview.map((x,i)=>`<tr class="${x.blocked?"blocked-row":""}">
    <td>${x.blocked?"":`<input class="pp-select" type="checkbox" value="${esc(x.source)}" checked>`}</td>
    <td><strong>${esc(x.show)}</strong><br>S${String(x.season).padStart(2,"0")}${epLabel(x)}</td>
    <td>${esc(x.quality||"Unknown")}</td>
    <td><code>${esc(x.source)}</code></td>
    <td>${x.renamed?'<span class="status-pill Downloaded">Renamed</span> ':''}<code>${esc(x.destination)}</code></td>
    <td>${x.blocked?`<span class="status-pill Failed">Blocked</span><br>${esc(x.blocked)}`:`<span class="status-pill Downloaded">Approved</span>${x.naming_pattern?`<br><small>${esc(x.naming_pattern)}</small>`:""}`}</td>
  </tr>`).join("")}</table>`:'<div class="empty-state compact"><p>No matched files yet. Confirm the folder path and click Preview Folder.</p></div>';
  const all=$("selectAll");
  if(all) all.onchange=()=>document.querySelectorAll(".pp-select").forEach(cb=>cb.checked=all.checked);
}

async function scanFolder(){
  const root=activeRoot();
  if(!root){setMessage("Enter a completed TV downloads folder first.","error");return;}
  ["scan","runSelected","runAll"].forEach(id=>$(id).disabled=true);
  $("message").className="message info";
  $("message").innerHTML=progressHtml({stage:"Queued",percent:0,message:"Post-processing folder preview queued. You can switch screens and monitor it from Active Jobs."});
  try{
    const body={root,limit:$("limit").value||300};
    const r=await fetch("/api/postprocess/scan/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await readJsonResponse(r);
    if(!r.ok)throw new Error(d.error||"Preview failed");
    const job=await pollPostprocessJob(d.job.job_id);
    if(job.status==="complete"){setMessage("Preview complete.","success"); if(job.result)render(job.result);}
    else setMessage(job.message||"Preview failed","error");
  }catch(e){setMessage(e.message,"error");}
  finally{["scan","runSelected","runAll"].forEach(id=>$(id).disabled=false);}
}

async function saveConfig(){
  try{
    const r=await fetch("/api/postprocess/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tv_download_dir:$("defaultDir").value,process_method:$("method").value})});
    const d=await readJsonResponse(r);
    setMessage(r.ok?"Default post-processing folder saved.":(d.error||"Save failed"),r.ok?"success":"error");
  }catch(e){setMessage(e.message,"error");}
}

async function processFiles(mode){
  const root=activeRoot();
  const selected=mode==="selected"?selectedSources():[];
  if(!root){setMessage("Enter a completed TV downloads folder first.","error");return;}
  if(mode==="selected" && !selected.length){setMessage("Select at least one approved file to process.","error");return;}
  const count=mode==="selected"?selected.length:"all approved preview matches";
  if(!confirm(`Process ${count} using ${$("method").value}? Existing replacements stay protected by the safe upgrade rules.`))return;
  setMessage("Processing approved files…");
  ["runSelected","runAll"].forEach(id=>$(id).disabled=true);
  try{
    const body={root,limit:$("limit").value||300,process_method:$("method").value};
    if(mode==="selected") body.selected_sources=selected;
    const r=await fetch("/api/postprocess/run/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await readJsonResponse(r);
    if(!r.ok)throw new Error(d.error||"Processing failed");
    const job=await pollPostprocessJob(d.job.job_id);
    if(job.status==="complete"){setMessage("Processing complete.","success"); if(job.result)render(job.result);}
    else setMessage(job.message||"Processing failed","error");
  }catch(e){setMessage(e.message,"error");}
  finally{["runSelected","runAll"].forEach(id=>$(id).disabled=false);}
}

window.addEventListener("DOMContentLoaded",()=>{
  loadConfig();
  $("saveConfig").onclick=saveConfig;
  $("scan").onclick=scanFolder;
  $("runSelected").onclick=()=>processFiles("selected");
  $("runAll").onclick=()=>processFiles("all");
});

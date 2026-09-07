const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const $=id=>document.getElementById(id);
const epLabel=x=>(x.episodes||[]).map(e=>`E${String(e).padStart(2,"0")}`).join("")||"";
let lastPreview=[];
let previewRoot="";
let busy=false;
function updateSelection(){
  const approved=lastPreview.filter(x=>!x.blocked).length;
  const selected=selectedSources().length;
  const valid=previewRoot && previewRoot===activeRoot();
  $("runSelected").disabled=busy||!valid||!selected;
  $("runAll").disabled=busy||!valid||!approved;
  $("scan").disabled=busy;
  $("selectionSummary").textContent=valid
    ? approved ? selected+" of "+approved+" approved files selected. Review the show, episode and final path, then confirm processing." : "Nothing can be approved yet. Review the blocked and unmatched reasons below."
    : "Preview a folder to review and confirm episode matches.";
}

async function readJsonResponse(resp){
  const text=await resp.text();
  try{return JSON.parse(text||"{}");}
  catch(e){throw new Error(`HTTP ${resp.status}: ${text.slice(0,260)}`);}
}
function activeRoot(){return ($("overrideDir")?.value||"").trim() || ($("defaultDir")?.value||"").trim();}
function selectedSources(){return [...document.querySelectorAll(".pp-select:checked")].map(x=>x.value);}
function setMessage(text,kind=""){$("message").className=`message ${kind}`.trim();$("message").textContent=text||"";}
function progressHtml(job){const pct=Math.max(0,Math.min(100,Number(job?.percent||0)));return `<div class="import-progress"><div class="progress-head"><strong>${esc(job?.stage||job?.status||"Working")}</strong><span>${pct}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><p class="muted">${esc(job?.message||"Working in the background…")}</p></div>`}
async function pollPostprocessJob(jobId){for(;;){const r=await fetch(`/api/jobs/${encodeURIComponent(jobId)}`),d=await readJsonResponse(r),j=d.job||{};if(!r.ok||!j.status)throw new Error(d.error||"Could not read job progress. Check Active Jobs before retrying.");$("message").className="message info";$("message").innerHTML=progressHtml(j);if(["complete","error","cancelled"].includes(String(j.status||"")))return j;await new Promise(x=>setTimeout(x,900));}}

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
    <td>${x.blocked?`<span class="status-pill Failed">Blocked</span><br>${esc(x.blocked)}`:`<span class="status-pill Downloaded">Approved</span>${x.match_confidence?`<br><small>Match: ${esc(x.match_confidence)} — ${esc(x.match_reason||"")}</small>`:""}${x.review_note?`<br><span class="notice warn inline-note">${esc(x.review_note)}</span>`:""}${x.naming_pattern?`<br><small>${esc(x.naming_pattern)}</small>`:""}`}</td>
  </tr>`).join("")}</table>`:'<div class="empty-state compact"><p>No approvable episodes. Review the unmatched files below.</p></div>';
  if(d.unmatched) $("actions").innerHTML+=`<h3>Unmatched files — ${Number(d.unmatched)}</h3><table class="compact-table postprocess-table"><tr><th>Source file</th><th>Why it cannot be approved</th></tr>${(d.unmatched_details||[]).map(x=>`<tr><td><code>${esc(x.source)}</code></td><td>${esc(x.reason)}</td></tr>`).join("")}</table>${(d.unmatched_details||[]).length<d.unmatched?'<p>Some reasons were not returned by this server. Restart TV Manager with the updated code and preview again.</p>':''}`;
  const all=$("selectAll");
  if(all) all.onchange=()=>{document.querySelectorAll(".pp-select").forEach(cb=>cb.checked=all.checked);updateSelection();};
  document.querySelectorAll(".pp-select").forEach(cb=>cb.onchange=updateSelection);
  updateSelection();
}

async function scanFolder(){
  const root=activeRoot();
  if(!root){setMessage("Enter a completed TV downloads folder first.","error");return;}
  busy=true;previewRoot="";lastPreview=[];updateSelection();
  $("message").className="message info";
  $("message").innerHTML=progressHtml({stage:"Queued",percent:0,message:"Post-processing folder preview queued. You can switch screens and monitor it from Active Jobs."});
  try{
    const body={root,limit:$("limit").value||300};
    const r=await fetch("/api/postprocess/scan/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await readJsonResponse(r);
    if(!r.ok)throw new Error(d.error||"Preview failed");
    const job=await pollPostprocessJob(d.job.job_id);
    if(job.status==="complete"){if(!job.result)throw new Error("Preview results are unavailable. Preview the folder again."); previewRoot=root;render(job.result);setMessage(lastPreview.some(x=>!x.blocked)?"Preview complete. Review the matches below and confirm processing.":"Preview complete: no files can be approved yet. Review the reasons below.",lastPreview.some(x=>!x.blocked)?"success":"error");$("selectionSummary").scrollIntoView({block:"center",behavior:"smooth"});}
    else setMessage(job.message||"Preview failed","error");
  }catch(e){setMessage(e.message,"error");}
  finally{busy=false;updateSelection();}
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
  if(busy)return;
  if(!previewRoot || previewRoot!==root){setMessage("Preview this folder before processing.","error");return;}
  const selected=mode==="selected"?selectedSources():lastPreview.filter(x=>!x.blocked).map(x=>x.source);
  if(!root){setMessage("Enter a completed TV downloads folder first.","error");return;}
  if(!selected.length){setMessage("Select at least one approved file to process.","error");return;}
  const count=selected.length+" confirmed files";
  if(!confirm(`Process ${count} using ${$("method").value}? Existing replacements stay protected by the safe upgrade rules.`))return;
  setMessage("Processing approved files…");
  busy=true;updateSelection();
  try{
    const body={root,limit:$("limit").value||300,process_method:$("method").value};
    body.selected_sources=selected;
    const r=await fetch("/api/postprocess/run/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await readJsonResponse(r);
    if(!r.ok)throw new Error(d.error||"Processing failed");
    const job=await pollPostprocessJob(d.job.job_id);
    if(job.status==="complete"){previewRoot="";setMessage("Processing complete. Preview the folder again before another run.","success"); if(job.result)render(job.result);}
    else setMessage(job.message||"Processing failed","error");
  }catch(e){setMessage(e.message,"error");}
  finally{busy=false;updateSelection();}
}

window.addEventListener("DOMContentLoaded",()=>{
  loadConfig();
  ["defaultDir","overrideDir","limit"].forEach(id=>$(id).addEventListener("input",()=>{previewRoot="";updateSelection();}));
  updateSelection();
  $("saveConfig").onclick=saveConfig;
  $("scan").onclick=scanFolder;
  $("runSelected").onclick=()=>processFiles("selected");
  $("runAll").onclick=()=>processFiles("all");
});

const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const fileInput=document.getElementById("database"),msg=document.getElementById("message"),stats=document.getElementById("stats"),schema=document.getElementById("schema"),details=document.getElementById("details");
let lastPreview=null;
function formData(){const file=fileInput.files[0];if(!file)throw new Error("Choose the SickChill database first.");const fd=new FormData();fd.append("database",file);return fd}

async function expectJson(response, context){
  const contentType=(response.headers.get("content-type")||"").toLowerCase();
  const text=await response.text();
  let data=null;
  if(text){
    try{data=JSON.parse(text)}
    catch(e){
      const clean=text.replace(/<[^>]*>/g," ").replace(/\s+/g," ").trim().slice(0,500);
      throw new Error(`${context||"Request"} returned HTML/text instead of JSON. HTTP ${response.status}. ${clean||text.slice(0,300)}`);
    }
  }
  if(!data)data={};
  if(!response.ok){
    throw new Error(data.error||data.message||`${context||"Request"} failed with HTTP ${response.status}`);
  }
  return data;
}

const progressBox=document.getElementById("importProgress"),progressStage=document.getElementById("progressStage"),progressPercent=document.getElementById("progressPercent"),progressFill=document.getElementById("progressFill"),progressMessage=document.getElementById("progressMessage"),progressCounters=document.getElementById("progressCounters");
function resetProgress(){if(!progressBox)return;progressBox.hidden=false;updateProgress({stage:"queued",percent:0,message:"Queued…",counters:{}})}
function updateProgress(job){if(!progressBox)return;progressBox.hidden=false;const pct=Math.max(0,Math.min(100,Number(job.percent||0)));progressStage.textContent=String(job.stage||job.status||"running").replaceAll("_"," ").toUpperCase();progressPercent.textContent=pct+"%";progressFill.style.width=pct+"%";progressMessage.textContent=job.message||"Working…";const c=job.counters||{};const keys=[["shows_found","Shows found"],["shows_processed","Shows processed"],["shows_imported","Shows imported"],["shows_skipped","Shows skipped"],["episodes_found","Episodes found"],["episodes_processed","Episodes processed"],["episodes_imported","Episodes imported"],["episodes_skipped","Episodes skipped"]];progressCounters.innerHTML=keys.filter(([k])=>c[k]!==undefined&&c[k]!==null).map(([k,label])=>`<div class="progress-counter"><strong>${esc(c[k])}</strong><span>${esc(label)}</span></div>`).join("");}
async function pollImportJob(jobId){for(;;){const r=await fetch(`/api/import/sickchill/jobs/${jobId}`,{cache:"no-store"});const job=await expectJson(r,"Import job status");updateProgress(job);if(job.status==="complete")return job.result||job;if(job.status==="error")throw new Error(job.error||job.message||"Import failed");await new Promise(resolve=>setTimeout(resolve,700));}}
async function startImportJob(){msg.className="message";msg.textContent="Starting background import job…";details.innerHTML="";stats.innerHTML="";resetProgress();const r=await fetch("/api/import/sickchill/jobs",{method:"POST",body:formData()});const d=await expectJson(r,"Start import job");msg.textContent=`Import job started: ${d.job_id}`;return pollImportJob(d.job_id);}
function statCards(d){return `<div class="stats">${[["Shows found",d.shows_found],["Shows imported",d.shows_imported],["Shows skipped",d.shows_skipped],["Episodes found",d.episodes_found],["Episodes imported",d.episodes_imported],["Episodes skipped",d.episodes_skipped]].map(x=>`<div class="stat"><strong>${esc(x[1])}</strong><span>${esc(x[0])}</span></div>`).join("")}</div>`}

function verificationCard(d){
  const v=d.active_database_verification;
  if(!v)return "";
  return `<div class="panel compact-panel"><h3>Active TV Manager database after import</h3><div class="stats"><div class="stat"><strong>${esc(v.shows)}</strong><span>Shows in active DB</span></div><div class="stat"><strong>${esc(v.episodes)}</strong><span>Episodes in active DB</span></div><div class="stat"><strong>${esc(v.import_runs)}</strong><span>Import runs</span></div><div class="stat"><strong>${esc(v.recovery?.created||0)}</strong><span>Recovered shows</span></div></div><p class="muted">Database: ${esc(v.database||"")}</p></div>`;
}
async function verifyImport(){
  const r=await fetch('/api/import/verify?recover=1'),d=await expectJson(r,'Import verification');
  details.innerHTML=verificationCard({active_database_verification:d})+details.innerHTML;
  return d;
}
function showSchema(d){schema.style.display="block";schema.textContent=`Show table: ${d.schema?.show_table||"(none)"}\nEpisode table: ${d.schema?.episode_table||"(none)"}\nWarnings: ${(d.schema?.warnings||[]).join("; ")||"None"}`}
async function callImport(endpoint,label){msg.className="message";msg.textContent=label;details.innerHTML="";const r=await fetch(endpoint,{method:"POST",body:formData()});try{return await expectJson(r,label)}catch(ex){msg.className="message error";msg.textContent=ex.message;return null}}
document.getElementById("analyzeBtn").addEventListener("click",async()=>{try{const d=await callImport("/api/import/sickchill/analyze","Analyzing database without writing changes…");if(!d)return;msg.className=d.ready?"message success":"message error";msg.textContent=d.ready?"Analysis complete. Database is ready for preview.":"Analysis complete, but this database is not ready to import.";stats.innerHTML=`<div class="stats"><div class="stat"><strong>${esc(d.shows_found)}</strong><span>Shows found</span></div><div class="stat"><strong>${esc(d.episodes_found)}</strong><span>Episodes found</span></div><div class="stat"><strong>${esc(d.shows_matching_existing)}</strong><span>Existing matches</span></div><div class="stat"><strong>${esc(d.shows_ready_to_import)}</strong><span>Ready to import</span></div></div>`;showSchema(d);details.innerHTML=d.sample_shows?.length?`<h3>Sample shows</h3><table><tr><th>Name</th><th>IMDb</th><th>TVDb</th></tr>${d.sample_shows.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.imdb_id||"")}</td><td>${esc(x.tvdb_id||"")}</td></tr>`).join("")}</table>`:""}catch(ex){msg.className="message error";msg.textContent=ex.message}});
document.getElementById("previewBtn").addEventListener("click",async()=>{try{const d=await callImport("/api/import/sickchill/preview","Building dry-run import preview…");if(!d)return;lastPreview=d;msg.className="message success";msg.textContent="Preview complete. No TV Manager records were written.";stats.innerHTML=statCards(d);showSchema(d);details.innerHTML=`<h3>Import detail sample</h3>${(d.details||[]).length?`<table><tr><th>Type</th><th>Action</th><th>Message</th></tr>${d.details.slice(0,50).map(x=>`<tr><td>${esc(x.item_type)}</td><td>${esc(x.action)}</td><td>${esc(x.message)}</td></tr>`).join("")}</table>`:'<p class="muted">No detail rows returned.</p>'}`}catch(ex){msg.className="message error";msg.textContent=ex.message}});
document.getElementById("importBtn").addEventListener("click",async()=>{try{const ok=confirm("Import this SickChill database now? Analyze/Preview first is strongly recommended.");if(!ok)return;const d=await startImportJob();if(!d)return;msg.className="message success";msg.textContent=`Database import complete. Backup: ${esc(d.backup||"")}`;stats.innerHTML=statCards(d)+verificationCard(d);showSchema(d);details.innerHTML=`<a class="btn secondary" href="/manager">Open Shows</a> <a class="btn secondary" href="/library-health">Open post-import health report</a>`;await verifyImport();history()}catch(ex){msg.className="message error";msg.textContent=ex.message}});

document.getElementById("configForm").addEventListener("submit",async e=>{e.preventDefault();const file=document.getElementById("configFile").files[0];const fd=new FormData();fd.append("config",file);const m=document.getElementById("configMessage");m.textContent="Importing configuration…";const r=await fetch("/api/import/config",{method:"POST",body:fd});let d;try{d=await expectJson(r,"Configuration import")}catch(ex){m.className="message error";m.textContent=ex.message;return}m.className="message success";m.textContent=`Configuration imported. Backup: ${d.backup}`;document.getElementById("configSummary").innerHTML=`<div class="stats"><div class="stat"><strong>${d.sections}</strong><span>Sections</span></div><div class="stat"><strong>${d.settings}</strong><span>Settings</span></div><div class="stat"><strong>${d.secret_settings}</strong><span>Protected values</span></div></div><div class="schema">${esc(JSON.stringify(d.mapped,null,2))}</div>`;loadSettings()});
async function loadSettings(){const r=await fetch("/api/settings"),d=await expectJson(r,"Load settings"),v=document.getElementById("settingsView");const secs=Object.keys(d.results);if(!secs.length){v.innerHTML='<p class="muted">No settings imported yet.</p>';return}v.innerHTML=secs.map(sec=>`<details><summary><strong>${esc(sec)}</strong> (${d.results[sec].length})</summary><table><tr><th>Setting</th><th>Value</th></tr>${d.results[sec].map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.value??"")}</td></tr>`).join("")}</table></details>`).join("")}
async function history(){const r=await fetch("/api/import/history"),d=await expectJson(r,"Load import history");document.getElementById("history").innerHTML=d.results.length?'<table><tr><th>Date</th><th>Source</th><th>Shows</th><th>Episodes</th></tr>'+d.results.map(x=>`<tr><td>${esc(x.imported_at)}</td><td>${esc(x.source_name)}</td><td>${esc(x.shows_imported)}/${esc(x.shows_found)}</td><td>${esc(x.episodes_imported)}/${esc(x.episodes_found)}</td></tr>`).join("")+"</table>":'<p class="muted">No imports yet.</p>'}
history();loadSettings();

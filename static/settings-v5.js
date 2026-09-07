
const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));

async function pollSchedulerJob(jobId){for(;;){const r=await fetch(`/api/jobs/${encodeURIComponent(jobId)}`),d=await r.json(),j=d.job||{};const pct=Math.max(0,Math.min(100,Number(j.percent||0)));schedulerJobProgress.innerHTML=`<div class="import-progress"><div class="progress-head"><strong>${esc(j.stage||j.status||"Working")}</strong><span>${pct}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><p class="muted">${esc(j.message||"")}</p></div>`;if(["complete","error","cancelled"].includes(String(j.status||"")))return j;await new Promise(x=>setTimeout(x,900));}}
document.querySelectorAll(".settings-tab").forEach(b=>b.onclick=()=>{
document.querySelectorAll(".settings-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll(".settings-view").forEach(v=>v.hidden=true);document.getElementById("view-"+b.dataset.view).hidden=false});
async function loadScheduler(){const [r,c]=await Promise.all([fetch("/api/scheduler"),fetch("/api/tvmanager/config")]),d=await r.json(),cfg=await c.json();automation.checked=d.automation_enabled;autoGrab.checked=cfg.auto_grab;recentDays.value=cfg.recent_days;maxSearches.value=cfg.max_searches_per_run;if(window.metadataMissingLimit)metadataMissingLimit.value=cfg.metadata_missing_limit||200;if(window.artworkRefreshLimit)artworkRefreshLimit.value=cfg.artwork_refresh_limit||200;automationNotice.className=d.automation_enabled?"notice good":"notice warn";automationNotice.textContent=d.automation_enabled?"Automation is armed. Scheduled jobs may search and process automatically.":"Automation is paused. Manual actions remain available.";jobs.innerHTML=d.jobs.map(j=>`<div class="scheduler-row"><div><strong>${esc(j.name.replaceAll("_"," "))}</strong><div class="muted">${esc(j.last_status||"Never run")}${j.last_run?" • "+esc(j.last_run):""}</div></div><label class="switchline"><input class="checkbox jobtoggle" data-name="${esc(j.name)}" type="checkbox" ${j.enabled?"checked":""}> Enabled</label><input class="jobinterval" data-name="${esc(j.name)}" type="number" min="1" value="${j.interval_minutes}"><button class="secondary runjob" data-name="${esc(j.name)}">Run now</button></div>`).join("");document.querySelectorAll(".jobtoggle").forEach(x=>x.onchange=()=>saveJob(x.dataset.name,{enabled:x.checked}));document.querySelectorAll(".jobinterval").forEach(x=>x.onchange=()=>saveJob(x.dataset.name,{interval:+x.value}));document.querySelectorAll(".runjob").forEach(x=>x.onclick=async()=>{x.disabled=true;x.textContent="Running…";const r=await fetch(`/api/scheduler/jobs/${x.dataset.name}/run`,{method:"POST"});let d={};try{d=await r.json()}catch{};if(d.job?.job_id)await pollSchedulerJob(d.job.job_id);x.disabled=false;x.textContent="Run now";loadScheduler()})}
async function saveJob(name,body){await fetch(`/api/scheduler/jobs/${name}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})}
automation.onchange=async()=>{await fetch("/api/scheduler/automation",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:automation.checked})});loadScheduler()}
saveDefaults.onclick=async()=>{await fetch("/api/settings/tvmanager",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({recent_days:+recentDays.value,max_searches_per_run:+maxSearches.value,auto_grab:autoGrab.checked?"1":"0",refresh_media_servers_after_process:refreshMedia.checked?"1":"0",simulation_mode:simulationMode.checked?"1":"0",metadata_missing_limit:window.metadataMissingLimit?metadataMissingLimit.value:"200",artwork_refresh_limit:window.artworkRefreshLimit?artworkRefreshLimit.value:"200"})});saveDefaults.textContent="Saved";setTimeout(()=>saveDefaults.textContent="Save defaults",900)}
async function loadClients(){const r=await fetch("/api/downloaders"),d=await r.json(),c=d.config;clients.innerHTML=`<div class="client-grid"><div class="service-card"><h3>SABnzbd</h3><span class="status-pill ${c.sabnzbd.configured?"Downloaded":""}">${c.sabnzbd.configured?"Configured":"Not configured"}</span><p>${esc(c.sabnzbd.host||"")}</p><small>Category: ${esc(c.sabnzbd.category||"")}</small></div><div class="service-card"><h3>${esc(c.torrent_method||"Torrent Client")}</h3><span class="status-pill ${c.torrent.configured?"Downloaded":""}">${c.torrent.configured?"Configured":"Not configured"}</span><p>${esc(c.torrent.host||"")}</p><small>Label: ${esc(c.torrent.label||"")}</small></div></div>`}

pollClients.onclick=async()=>{pollClients.disabled=true;clientTest.innerHTML='<p class="muted">Polling downloader status…</p>';const r=await fetch("/api/downloaders/poll",{method:"POST"}),d=await r.json();clientTest.innerHTML=r.ok?d.results.map(x=>`<div class="notice ${x.error?"warn":"good"}">${esc(x.client)}: ${x.error?esc(x.error):`${x.checked||0} checked • ${x.updated||0} updated${x.active!=null?` • ${x.active} active • ${x.complete} complete`:""}`}</div>`).join(""):`<div class="notice warn">${esc(d.error||"Polling failed")}</div>`;pollClients.disabled=false}

testClients.onclick=async()=>{testClients.disabled=true;clientTest.innerHTML='<p class="muted">Testing connections…</p>';const r=await fetch("/api/downloaders/test",{method:"POST"}),d=await r.json();clientTest.innerHTML=d.results.map(x=>`<div class="notice ${x.ok?"good":"warn"}">${esc(x.client)}: ${x.ok?"Connected "+esc(x.version||""):"Failed — "+esc(x.error)}</div>`).join("");testClients.disabled=false}
async function loadProviders(){const r=await fetch("/api/providers"),d=await r.json();providers.innerHTML=d.results.length?`<div class="provider-grid">${d.results.map(p=>`<div class="service-card ${p.enabled?"":"disabled-card"}"><div class="result-top"><h3>${esc(p.name)}</h3><span class="status-pill">${p.enabled?"Enabled":"Disabled"}</span></div><p>${esc(p.url)}</p><small>Categories ${esc(p.categories||"all")} • API ${p.has_api_key?"configured":"missing"} • priority ${p.priority}</small></div>`).join("")}</div>`:'<p class="muted">No Newznab providers imported.</p>'}
async function loadNotifications(){const r=await fetch("/api/notifications"),d=await r.json();notifications.innerHTML=d.results.length?`<div class="provider-grid">${d.results.map(n=>`<div class="service-card"><div class="result-top"><h3>${esc(n.section)}</h3><span class="status-pill ${n.enabled?"Downloaded":""}">${n.enabled?"Enabled":"Configured"}</span></div><small>${n.settings} imported settings</small></div>`).join("")}</div>`:'<p class="muted">No notification sections found.</p>'}
testEmail.onclick=async()=>{testEmail.disabled=true;const r=await fetch("/api/notifications/email/test",{method:"POST"}),d=await r.json();notificationMsg.className=r.ok?"notice good":"notice warn";notificationMsg.textContent=r.ok?"Test email sent.":d.error;testEmail.disabled=false}
let sectionData=[];async function loadSections(){const r=await fetch("/api/settings/sections"),d=await r.json();sectionData=d.results;renderSections()}
function renderSections(){const q=sectionSearch.value.toLowerCase();sections.innerHTML=sectionData.filter(x=>x.section.toLowerCase().includes(q)).map(s=>`<button onclick="openSection('${esc(s.section).replace(/'/g,"&#039;")}')"><strong>${esc(s.section)}</strong><span>${s.setting_count} settings${s.secret_count?" • "+s.secret_count+" protected":""}</span></button>`).join("")}
sectionSearch.oninput=renderSections;
window.openSection=async sec=>{const r=await fetch("/api/settings/section/"+encodeURIComponent(sec)),d=await r.json();sectionEditor.innerHTML=`<div class="toolbar"><h3>${esc(sec)}</h3><div class="spacer"></div><span class="status-pill">${d.results.length} settings</span></div><div class="setting-rows">${d.results.map(x=>`<label class="setting-row"><span><strong>${esc(x.name)}</strong><small>${esc(x.source)}</small></span><input data-sec="${esc(sec)}" data-name="${esc(x.name)}" value="${esc(x.value||"")}"></label>`).join("")}</div><button id="saveSection" class="blue">Save Changes</button><div id="sectionMsg" class="message"></div>`;saveSection.onclick=async()=>{const inputs=sectionEditor.querySelectorAll("input[data-name]");for(const i of inputs){await fetch(`/api/settings/section/${encodeURIComponent(i.dataset.sec)}/${encodeURIComponent(i.dataset.name)}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:i.value})})}sectionMsg.className="message success";sectionMsg.textContent="Settings saved."}}
loadScheduler();loadClients();loadProviders();loadNotifications();loadSections();

fetch("/api/settings/section/TVManager").then(r=>r.json()).then(d=>{const x=d.results.find(i=>i.name==="refresh_media_servers_after_process");refreshMedia.checked=!x||["1","true","yes","on"].includes(String(x.value).toLowerCase())});
makeBackup.onclick=async()=>{makeBackup.disabled=true;const r=await fetch("/api/backup",{method:"POST"}),d=await r.json();backupMsg.className=r.ok?"notice good":"notice warn";backupMsg.innerHTML=r.ok?`Backup created: ${d.filename} — <a href="/api/backup/download/${encodeURIComponent(d.filename)}">download</a>`:(d.error||"Backup failed");makeBackup.disabled=false}

fetch("/api/settings/section/TVManager").then(r=>r.json()).then(d=>{const x=d.results.find(i=>i.name==="simulation_mode");simulationMode.checked=!!x&&["1","true","yes","on"].includes(String(x.value).toLowerCase())});



async function loadNaming(){
  const r=await fetch("/api/naming/config"),d=await r.json();
  namingPattern.value=d.pattern||"";
  renameEpisodes.checked=!!d.rename_episodes;
  moveAssociated.checked=!!d.move_associated_files;
  namingPreview.textContent=d.preview||"";
  namingPreset.innerHTML=`<option value="">Custom</option>${(d.presets||[]).map(x=>`<option value="${esc(x.pattern)}">${esc(x.name)}</option>`).join("")}`;
  const found=(d.presets||[]).find(x=>x.pattern===d.pattern);if(found)namingPreset.value=found.pattern;
}
namingPreset.onchange=()=>{if(namingPreset.value){namingPattern.value=namingPreset.value;previewNaming.click()}};
previewNaming.onclick=async()=>{
  const r=await fetch("/api/naming/preview-sample",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pattern:namingPattern.value})}),d=await r.json();
  namingPreview.textContent=r.ok?d.preview:(d.error||"Preview failed");
}
saveNaming.onclick=async()=>{
  const r=await fetch("/api/naming/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
    pattern:namingPattern.value,rename_episodes:renameEpisodes.checked,move_associated_files:moveAssociated.checked
  })}),d=await r.json();
  namingMsg.className=r.ok?"notice good":"notice warn";
  namingMsg.textContent=r.ok?`Naming saved. Preview: ${d.preview}`:(d.error||"Could not save naming settings");
  if(r.ok)loadNaming();
}

async function loadSecurity(){
  const r=await fetch("/api/security/status"),d=await r.json();
  browserAuthEnabled.checked=!!d.browser_auth_enabled;
  if(d.admin?.username)securityUsername.value=d.admin.username;
  securityStatus.innerHTML=`<div class="notice ${d.browser_auth_enabled?"good":"warn"}">${d.browser_auth_enabled?"Browser authentication is ON.":"Browser authentication is OFF."} ${d.admin_configured?"Administrator credentials are configured.":"No administrator password is configured yet."}${d.is_loopback?" You are connected locally.":""}</div>`;
}
saveAdminPassword.onclick=async()=>{
  if(!securityPassword.value)return alert("Enter a new administrator password of at least 12 characters.");
  const r=await fetch("/api/security/password",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:securityUsername.value,password:securityPassword.value})}),d=await r.json();
  securityMsg.className=r.ok?"notice good":"notice warn";securityMsg.textContent=r.ok?"Administrator password saved.":(d.error||"Password update failed");
  if(r.ok){securityPassword.value="";loadSecurity()}
}
browserAuthEnabled.onchange=async()=>{
  const desired=browserAuthEnabled.checked;
  const r=await fetch("/api/security/browser-auth",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:desired})}),d=await r.json();
  if(!r.ok){browserAuthEnabled.checked=!desired;alert(d.error||"Could not change browser authentication");return}
  if(desired&&!document.cookie.includes("tvmanager_csrf=")){location.href="/login";return}
  loadSecurity();
}
loadSecurityEvents.onclick=async()=>{
  const r=await fetch("/api/security/events"),d=await r.json();
  securityEvents.innerHTML=(d.results||[]).length?`<table class="compact-table"><tr><th>When</th><th>Event</th><th>User</th><th>Address</th><th>Detail</th></tr>${d.results.map(x=>`<tr><td>${esc(x.created_at||"")}</td><td>${esc(x.event_type)}</td><td>${esc(x.username||"")}</td><td>${esc(x.remote_addr||"")}</td><td>${esc(x.detail||"")}</td></tr>`).join("")}</table>`:'<p class="muted">No security events yet.</p>';
}
loadNaming();loadSecurity();


const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));

async function pollSchedulerJob(jobId){for(;;){const r=await fetch(`/api/jobs/${encodeURIComponent(jobId)}`),d=await r.json(),j=d.job||{};const pct=Math.max(0,Math.min(100,Number(j.percent||0)));schedulerJobProgress.innerHTML=`<div class="import-progress"><div class="progress-head"><strong>${esc(j.stage||j.status||"Working")}</strong><span>${pct}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><p class="muted">${esc(j.message||"")}</p></div>`;if(["complete","error","cancelled"].includes(String(j.status||"")))return j;await new Promise(x=>setTimeout(x,900));}}
document.querySelectorAll(".settings-tab").forEach(b=>b.onclick=()=>{
document.querySelectorAll(".settings-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll(".settings-view").forEach(v=>v.hidden=true);document.getElementById("view-"+b.dataset.view).hidden=false});
async function loadScheduler(){const [r,c]=await Promise.all([fetch("/api/scheduler"),fetch("/api/tvmanager/config")]),d=await r.json(),cfg=await c.json();automation.checked=d.automation_enabled;autoGrab.checked=cfg.auto_grab;recentDays.value=cfg.recent_days;maxSearches.value=cfg.max_searches_per_run;if(window.ignoreSeasonZeroCounts)ignoreSeasonZeroCounts.checked=!!cfg.ignore_season_zero_counts;if(window.metadataMissingLimit)metadataMissingLimit.value=cfg.metadata_missing_limit||200;if(window.artworkRefreshLimit)artworkRefreshLimit.value=cfg.artwork_refresh_limit||200;automationNotice.className=d.automation_enabled?"notice good":"notice warn";automationNotice.textContent=d.automation_enabled?"Automation is armed. Only jobs marked Enabled below run automatically.":"Automation is paused. Individual job choices are saved; manual actions remain available.";jobs.innerHTML=d.jobs.map(j=>`<div class="scheduler-row"><div><strong>${esc(j.name.replaceAll("_"," "))}</strong><div class="muted">${esc(j.last_status||"Never run")}${j.last_run?" • "+esc(j.last_run):""}</div></div><label class="switchline"><input class="checkbox jobtoggle" data-name="${esc(j.name)}" type="checkbox" ${j.enabled?"checked":""}> Enabled</label><input class="jobinterval" data-name="${esc(j.name)}" type="number" min="1" value="${j.interval_minutes}"><button class="secondary runjob" data-name="${esc(j.name)}">Run now</button></div>`).join("");document.querySelectorAll(".jobtoggle").forEach(x=>x.onchange=()=>saveJob(x.dataset.name,{enabled:x.checked}));document.querySelectorAll(".jobinterval").forEach(x=>x.onchange=()=>saveJob(x.dataset.name,{interval:+x.value}));document.querySelectorAll(".runjob").forEach(x=>x.onclick=async()=>{x.disabled=true;x.textContent="Running…";const r=await fetch(`/api/scheduler/jobs/${x.dataset.name}/run`,{method:"POST"});let d={};try{d=await r.json()}catch{};if(d.job?.job_id)await pollSchedulerJob(d.job.job_id);x.disabled=false;x.textContent="Run now";loadScheduler()})}
async function saveJob(name,body){await fetch(`/api/scheduler/jobs/${name}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})}
automation.onchange=async()=>{await fetch("/api/scheduler/automation",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:automation.checked})});loadScheduler()}
saveDefaults.onclick=async()=>{const response=await fetch("/api/settings/tvmanager",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({recent_days:+recentDays.value,max_searches_per_run:+maxSearches.value,auto_grab:autoGrab.checked?"1":"0",refresh_media_servers_after_process:refreshMedia.checked?"1":"0",simulation_mode:simulationMode.checked?"1":"0",metadata_missing_limit:window.metadataMissingLimit?metadataMissingLimit.value:"200",artwork_refresh_limit:window.artworkRefreshLimit?artworkRefreshLimit.value:"200",ignore_season_zero_counts:window.ignoreSeasonZeroCounts?(ignoreSeasonZeroCounts.checked?"1":"0"):"0"})});if(!response.ok){const result=await response.json();alert(result.error||"Could not save defaults");return;}saveDefaults.textContent="Saved";setTimeout(()=>saveDefaults.textContent="Save defaults",900)}
async function loadClients(){const r=await fetch("/api/downloaders"),d=await r.json(),c=d.config;clients.innerHTML=`<div class="client-grid"><div class="service-card"><h3>SABnzbd</h3><span class="status-pill ${c.sabnzbd.configured?"Downloaded":""}">${c.sabnzbd.configured?"Configured":"Not configured"}</span><p>${esc(c.sabnzbd.host||"")}</p><small>Category: ${esc(c.sabnzbd.category||"")}</small></div><div class="service-card"><h3>${esc(c.torrent_method||"Torrent Client")}</h3><span class="status-pill ${c.torrent.configured?"Downloaded":""}">${c.torrent.configured?"Configured":"Not configured"}</span><p>${esc(c.torrent.host||"")}</p><small>Label: ${esc(c.torrent.label||"")}</small></div></div>`}

pollClients.onclick=async()=>{pollClients.disabled=true;clientTest.innerHTML='<p class="muted">Polling downloader status…</p>';const r=await fetch("/api/downloaders/poll",{method:"POST"}),d=await r.json();clientTest.innerHTML=r.ok?d.results.map(x=>`<div class="notice ${x.error?"warn":"good"}">${esc(x.client)}: ${x.error?esc(x.error):`${x.checked||0} checked • ${x.updated||0} updated${x.active!=null?` • ${x.active} active • ${x.complete} complete`:""}`}</div>`).join(""):`<div class="notice warn">${esc(d.error||"Polling failed")}</div>`;pollClients.disabled=false}

testClients.onclick=async()=>{testClients.disabled=true;clientTest.innerHTML='<p class="muted">Testing connections…</p>';const r=await fetch("/api/downloaders/test",{method:"POST"}),d=await r.json();clientTest.innerHTML=d.results.map(x=>`<div class="notice ${x.ok?"good":"warn"}">${esc(x.client)}: ${x.ok?"Connected "+esc(x.version||""):"Failed — "+esc(x.error)}</div>`).join("");testClients.disabled=false}
let searchProviderRows=[];
async function providerRequest(url,method='GET',body){
  const r=await fetch(url,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
  const d=await r.json();if(!r.ok)throw new Error(d.error||'Provider request failed');return d;
}
async function loadProviders(){
  try{
    const d=await providerRequest('/api/providers/manage');searchProviderRows=d.results;
    providers.innerHTML=d.results.length?`<div class="provider-grid">${d.results.map(p=>{
      const h=p.health||{};
      return `<div class="service-card ${p.enabled?'':'disabled-card'}"><div class="result-top"><h3>${esc(p.name)}</h3><span class="status-pill">${p.enabled?'Enabled':'Disabled'}</span></div><p>${esc(p.url)}</p><small>${esc(p.origin)} • API key ${p.has_api_key?'saved':'empty'} • Daily ${p.enable_daily?'on':'off'} • Backlog ${p.enable_backlog?'on':'off'}</small>${p.configuration_issue?`<p class="notice warn">${esc(p.configuration_issue)}</p>`:''}${h.last_error?`<p class="notice warn">${esc(h.last_error)}${!h.available?` Next automatic retry: ${esc(h.suspended_until)}.`:''}</p>`:h.last_success?`<p class="muted">Last successful check: ${esc(h.last_success)}</p>`:''}<div class="actions"><button data-provider-edit="${esc(p.id)}" class="secondary">Edit Provider</button><button data-provider-test="${esc(p.id)}" class="secondary">Test Connection</button></div></div>`;
    }).join('')}</div>`:'<p class="muted">No search providers configured. Add a Newznab or Torznab indexer.</p>';
    providers.querySelectorAll('[data-provider-edit]').forEach(b=>b.onclick=()=>editSearchProvider(searchProviderRows.find(p=>p.id===b.dataset.providerEdit)));
    providers.querySelectorAll('[data-provider-test]').forEach(b=>b.onclick=async()=>{
      b.disabled=true;providerMessage.textContent='Checking indexer capabilities and authenticated search…';
      try{const result=await providerRequest(`/api/providers/manage/${b.dataset.providerTest}/test`,'POST');providerMessage.textContent=result.message;}catch(e){providerMessage.textContent=e.message;}finally{b.disabled=false;await loadProviders();}
    });
  }catch(e){providerMessage.textContent=e.message;}
}
function editSearchProvider(p={}){
  const imported=String(p.id||'').startsWith('imported-');
  providerEdit.innerHTML=`<form id="searchProviderForm" class="result-card"><h3>${p.id?'Edit':'Add'} Search Provider</h3><div class="form-grid"><label>Name<input name="name" required value="${esc(p.name||'')}"></label><label>Protocol<select name="protocol" ${imported?'disabled':''}><option value="newznab">Newznab (NZB)</option><option value="torznab" ${p.protocol==='torznab'?'selected':''}>Torznab (torrent)</option></select></label><label class="span2">Indexer URL<input name="url" required value="${esc(p.url||'')}" placeholder="https://indexer.example/api"></label><label>API key<input name="api_key" type="password" autocomplete="off" value="${p.has_api_key?'••••••••':''}"></label><label>Category IDs<input name="categories" value="${esc(p.categories||'')}" placeholder="5000"></label>${imported?'':`<label>Priority<input type="number" min="0" max="100000" name="priority" value="${p.priority??100}"></label><label>Minimum seeders<input type="number" min="0" max="100000" name="minimum_seeders" value="${p.minimum_seeders??0}"></label>`}<label class="checkline"><input type="checkbox" name="enabled" ${p.enabled!==false&&p.enabled!==0?'checked':''}>Enabled</label><label class="checkline"><input type="checkbox" name="enable_daily" ${p.enable_daily!==false&&p.enable_daily!==0?'checked':''}>Daily searches</label><label class="checkline"><input type="checkbox" name="enable_backlog" ${p.enable_backlog!==false&&p.enable_backlog!==0?'checked':''}>Backlog searches</label></div><div class="actions"><button type="submit" class="blue">Save Provider</button><button type="button" id="cancelProviderEdit" class="secondary">Cancel</button>${p.id?'<button type="button" id="removeSearchProvider" class="danger">Remove Provider…</button>':''}</div><div id="providerFormMessage" role="status"></div></form>`;
  const form=document.getElementById('searchProviderForm');
  form.onsubmit=async event=>{
    event.preventDefault();const button=form.querySelector('[type="submit"]');button.disabled=true;
    const data=Object.fromEntries(new FormData(form));for(const key of ['enabled','enable_daily','enable_backlog'])data[key]=form.elements[key].checked;
    data.revision=p.revision;if(imported)data.protocol='nzb';
    try{await providerRequest(p.id?`/api/providers/manage/${p.id}`:'/api/providers/custom',p.id?'PATCH':'POST',data);providerEdit.innerHTML='';providerMessage.textContent='Provider settings saved.';await loadProviders();}catch(e){document.getElementById('providerFormMessage').textContent=e.message;}finally{button.disabled=false;}
  };
  document.getElementById('cancelProviderEdit').onclick=()=>{providerEdit.innerHTML='';};
  const remove=document.getElementById('removeSearchProvider');if(remove)remove.onclick=()=>{
    document.getElementById('providerFormMessage').innerHTML=`<p>Remove ${esc(p.name)} from search providers?</p><button type="button" id="confirmProviderRemoval" class="danger">Confirm Removal</button>`;
    document.getElementById('confirmProviderRemoval').onclick=async function(){this.disabled=true;try{await providerRequest(`/api/providers/manage/${p.id}`,'DELETE',{revision:p.revision});providerEdit.innerHTML='';providerMessage.textContent='Provider removed.';await loadProviders();}catch(e){document.getElementById('providerFormMessage').textContent=e.message;}};
  };
  form.elements.name.focus();providerEdit.scrollIntoView({block:'nearest'});
}
addSearchProvider.onclick=()=>editSearchProvider();
if(location.hash==='#providers')document.querySelector('[data-view="providers"]').click();

async function loadNotifications(){const r=await fetch("/api/notifications"),d=await r.json();notifications.innerHTML=d.results.length?`<div class="provider-grid">${d.results.map(n=>`<div class="service-card"><div class="result-top"><h3>${esc(n.section)}</h3><span class="status-pill ${n.enabled?"Downloaded":""}">${n.enabled?"Enabled":"Configured"}</span></div><small>${n.settings} imported settings</small></div>`).join("")}</div>`:'<p class="muted">No notification sections found.</p>'}
testEmail.onclick=async()=>{testEmail.disabled=true;const r=await fetch("/api/notifications/email/test",{method:"POST"}),d=await r.json();notificationMsg.className=r.ok?"notice good":"notice warn";notificationMsg.textContent=r.ok?"Test email sent.":d.error;testEmail.disabled=false}
let sectionData=[];async function loadSections(){const r=await fetch("/api/settings/sections"),d=await r.json();sectionData=d.results;renderSections()}
function renderSections(){const q=sectionSearch.value.toLowerCase();sections.innerHTML=sectionData.filter(x=>x.section.toLowerCase().includes(q)).map(s=>`<button onclick="openSection('${esc(s.section).replace(/'/g,"&#039;")}')"><strong>${esc(s.section)}</strong><span>${s.setting_count} settings${s.secret_count?" • "+s.secret_count+" protected":""}</span></button>`).join("")}
sectionSearch.oninput=renderSections;
window.openSection=async sec=>{
  document.querySelector('[data-view="legacy"]').click();
  try{
    const r=await fetch('/api/settings/section/'+encodeURIComponent(sec)),d=await r.json();
    if(!r.ok)throw new Error(d.error||'Could not load settings');
    sectionEditor.innerHTML=`<h3>${esc(sec)}</h3><input id="settingNameFilter" placeholder="Find a setting in this section"><p class="muted">Change values and save. Protected values stay unchanged unless replaced. Application defaults are shown even before they are saved.</p><div class="setting-rows">${d.results.map(x=>{
      const name=esc(x.name),value=String(x.value??'');let editor;
      if(x.control==='editor')editor=`<a href="${esc(x.editor)}">${esc(x.editor_label)}</a>`;
      else if(x.control==='choice'||x.control==='boolean'){
        const choices=x.control==='boolean'?['0','1']:x.choices;
        const normalized=x.control==='boolean'?(['1','true','yes','on'].includes(value.toLowerCase())?'1':'0'):value;
        editor=`<select data-name="${name}">${(!choices.includes(normalized)?`<option selected value="${esc(value)}">${esc(value)} (imported; choose a supported option)</option>`:'')+choices.map(c=>`<option value="${esc(c)}" ${c===normalized?'selected':''}>${x.control==='boolean'?(c==='1'?'On':'Off'):esc(c||'Disabled')}</option>`).join('')}</select>`;
      }else editor=`<input autocomplete="off" type="${x.is_secret?'password':x.control==='number'?'number':'text'}" ${x.control==='number'?`min="${x.minimum}" max="${x.maximum}" step="1"`:''} data-name="${name}" value="${esc(value)}">`;
      return `<label class="setting-row"><span><strong>${name}</strong><small>${esc(x.source)} · ${esc(x.support||'')}</small></span>${editor}</label>`;
    }).join('')}</div><button id="saveSection" class="blue">Save Changes</button><div id="sectionMsg" class="message" role="status"></div>`;
    const inputs=Array.from(sectionEditor.querySelectorAll('[data-name]'));
    inputs.forEach(i=>i.dataset.original=i.value);
    document.getElementById('settingNameFilter').oninput=function(){sectionEditor.querySelectorAll('.setting-row').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(this.value.toLowerCase()));};
    document.getElementById('saveSection').onclick=async function(){
      this.disabled=true;const msg=document.getElementById('sectionMsg');let saved=0;
      try{
        for(const i of inputs.filter(i=>i.value!==i.dataset.original)){
          const response=await fetch(`/api/settings/section/${encodeURIComponent(sec)}/${encodeURIComponent(i.dataset.name)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:i.value})});
          const result=await response.json();if(!response.ok)throw new Error(`${i.dataset.name}: ${result.error||'Save failed'}`);
          i.dataset.original=i.value;saved++;
        }
        msg.textContent=saved?`${saved} setting(s) saved. Restart TV Manager if the setting controls startup behavior.`:'No changes to save.';
      }catch(e){msg.textContent=`${saved} setting(s) saved. ${e.message}`;}finally{this.disabled=false;}
    };
  }catch(e){sectionEditor.textContent=e.message;}
};
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

fetch("/api/settings/section/TVManager").then(r=>r.json()).then(d=>{const x=d.results.find(i=>i.name==="ignore_season_zero_counts");if(window.ignoreSeasonZeroCounts)ignoreSeasonZeroCounts.checked=!!x&&["1","true","yes","on"].includes(String(x.value).toLowerCase())});

;(()=>{
  const sidebar=document.querySelector('.settings-sidebar');
  const links=[['Library Locations','/library-storage'],['Quality Profiles','/quality'],['Metadata Sources','/metadata-sources'],['Native Notifications','/notifications'],['Providers, Media Servers & Webhooks','/advanced'],['Post-Processing','/postprocess'],['New Show Defaults','/'],['Database Protection','/database-safety']];
  for(const [label,url] of links){const a=document.createElement('a');a.className='btn secondary';a.href=url;a.textContent=label;sidebar.append(a);}
  for(const [view,sections] of [['providers',['Newznab']],['notifications',['Email']]]){
    const box=document.getElementById('view-'+view);const actions=document.createElement('div');actions.className='actions';
    for(const sec of sections){const b=document.createElement('button');b.className='secondary';b.textContent='Edit '+sec;b.onclick=()=>openSection(sec);actions.append(b);}box.prepend(actions);
  }
})();

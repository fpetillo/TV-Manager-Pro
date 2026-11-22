/* v18.24.0 — Missing Episode Autopilot page. */
(()=>{
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
  const num=n=>Number(n||0).toLocaleString();
  const code=(s,e)=>`S${String(s).padStart(2,"0")}E${String(e).padStart(2,"0")}`;
  let state=null, busy=false;

  function say(text, kind){const m=$("apMessage");m.textContent=text||"";m.className="message"+(kind?" "+kind:"");}

  async function api(path, body){
    const r=await fetch(path, body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok||d.ok===false)throw new Error(d.error||("HTTP "+r.status));
    return d;
  }

  function renderState(d){
    const on=!!d.settings.enabled;
    $("apToggle").textContent=on?"Turn off":"Turn on";
    $("apToggle").className=on?"secondary":"blue";
    $("apToggle").disabled=false;
    $("apRunNow").disabled=false;
    $("apState").textContent=on?(d.running?"Autopilot is on":"Autopilot is on, waiting for automation"):"Autopilot is off";
    const job=d.job||{};
    const bits=[];
    if(on)bits.push(`Runs every ${num(d.settings.interval_minutes)} minutes`);
    if(job.last_run)bits.push(`last run ${job.last_run.replace("T"," ")}${job.last_status?" ("+job.last_status+")":""}`);
    if(on&&job.next_run)bits.push(`next run ${job.next_run.replace("T"," ")}`);
    if(d.simulation)bits.push("Simulation mode is on: searches run but nothing is sent to the downloader");
    if(on&&!d.automation_armed)bits.push("Automation is paused in Settings, so scheduled runs are on hold");
    $("apStateDetail").textContent=bits.join(" · ")||"Turn it on to search for missing episodes automatically.";
    const problems=(d.readiness&&d.readiness.problems)||[];
    $("apReadiness").hidden=!problems.length;
    $("apReadiness").innerHTML=problems.map(p=>`<div>${esc(p)}</div>`).join("");
  }

  function renderCounts(c){
    const tiles=[["missing","Missing (aired)","Aired episodes with no file"],["due_now","Due for a search","Not searched in the last retry period"],
      ["downloading","In the downloader","Queued or downloading"],["not_aired","Not aired yet","Not searched until they air"],
      ["set_aside","Set aside","Every release tried failed"],["blocked_releases","Blocked releases","Failed or stalled, never grabbed again"]];
    $("apCounts").innerHTML=tiles.map(([k,label,hint])=>`<div class="dash-card"><span>${label}</span><strong>${num(c[k])}</strong><small>${hint}</small></div>`).join("");
  }

  function renderSettings(s){
    const f=$("apSettings");
    for(const el of f.elements){
      if(!el.name)continue;
      if(el.type==="checkbox")el.checked=!!Number(s[el.name]);else el.value=s[el.name];
    }
  }

  function renderSetAside(rows){
    $("apRetryAll").disabled=!rows.length;
    $("apSetAside").innerHTML=rows.length?`<table class="compact-table"><tr><th>Show</th><th>Episode</th><th>Releases tried</th><th>Last failure</th><th></th></tr>${rows.map(r=>`<tr><td><a href="/show/${r.show_id}">${esc(r.show_name)}</a></td><td>${code(r.season,r.episode)} ${esc(r.name||"")}</td><td>${num(r.attempts)}</td><td>${esc(r.last_failure||"")}</td><td><button class="secondary" data-retry="${r.episode_id}">Retry</button></td></tr>`).join("")}</table>`:'<p class="muted">Nothing set aside.</p>';
  }

  function renderHistory(rows){
    $("apHistory").innerHTML=rows.length?`<table class="compact-table"><tr><th>Started</th><th>Result</th><th>Searched</th><th>Sent to downloader</th><th>Failed / stalled</th><th>Time</th></tr>${rows.map(r=>{const s=r.search||{},f=r.failures||{};return `<tr><td>${esc(r.started_at)}</td><td>${esc(r.status)}${(r.errors||[]).length?`<small class="error">${esc(r.errors.join("; "))}</small>`:""}${(s.errors||[]).length?`<small class="muted">${esc(s.errors.join("; "))}</small>`:""}</td><td>${num(s.searched)}</td><td>${num(s.sent_to_downloader)}</td><td>${num(f.failed)} / ${num(f.stalled)}</td><td>${r.seconds!=null?esc(r.seconds)+" s":""}</td></tr>`}).join("")}</table>`:'<p class="muted">No runs yet.</p>';
  }

  async function load(){
    try{
      state=await api("/api/autopilot/status");
      renderState(state);renderCounts(state.counts);renderSettings(state.settings);renderSetAside(state.set_aside);renderHistory(state.history);
    }catch(err){say("Could not load Autopilot status: "+err.message,"error");}
  }

  async function waitForJob(id){
    for(let i=0;i<3600;i++){
      await new Promise(r=>setTimeout(r,2000));
      const d=await api("/api/jobs/"+encodeURIComponent(id));
      const j=d.job||{};
      if(["complete","error","cancelled"].includes(String(j.status).toLowerCase()))return j;
      say("Running… "+(j.message||""));
    }
  }

  $("apToggle").addEventListener("click",async()=>{
    if(busy||!state)return;busy=true;
    try{
      const on=!state.settings.enabled;
      state=await api("/api/autopilot/settings",{enabled:on?1:0});
      renderState(state);
      say(on?"Autopilot is on. It runs at the interval below; use Run now to start the first run immediately.":"Autopilot is off.","success");
    }catch(err){say(err.message,"error");}finally{busy=false;}
  });

  $("apRunNow").addEventListener("click",async()=>{
    if(busy)return;busy=true;$("apRunNow").disabled=true;
    try{
      const d=await api("/api/scheduler/jobs/missing_autopilot/run",{});
      say("Running…");
      const j=await waitForJob(d.job.job_id);
      const ok=j&&String(j.status).toLowerCase()==="complete";
      say(ok?"Run finished.":"Run ended: "+((j&&j.message)||"unknown result"), ok?"success":"error");
      await load();
    }catch(err){say(err.message,"error");}finally{busy=false;$("apRunNow").disabled=false;}
  });

  $("apSettings").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const body={};
    for(const el of ev.target.elements){if(!el.name)continue;body[el.name]=el.type==="checkbox"?(el.checked?1:0):el.value;}
    try{state=await api("/api/autopilot/settings",body);renderState(state);renderCounts(state.counts);say("Settings saved.","success");}
    catch(err){say(err.message,"error");}
  });

  document.addEventListener("click",async ev=>{
    const b=ev.target.closest("[data-retry],#apRetryAll");
    if(!b)return;
    try{
      const body=b.id==="apRetryAll"?{all:true}:{episode_ids:[Number(b.dataset.retry)]};
      const d=await api("/api/autopilot/retry",body);
      say(`${d.retried} episode(s) back in the search rotation.`,"success");await load();
    }catch(err){say(err.message,"error");}
  });

  load();
})();

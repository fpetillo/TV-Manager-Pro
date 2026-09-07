const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const byId=id=>document.getElementById(id);
let cleanupActions=[];
let fullMetaTimer=null;
let healthTimer=null;
function setHtml(id,html){const el=byId(id); if(el) el.innerHTML=html;}
function table(rows,cols){if(!rows?.length)return '<p class="muted">Nothing to show.</p>';return `<div class="auto-table-wrap"><table><tr>${cols.map(c=>`<th>${esc(c[0])}</th>`).join("")}</tr>${rows.map(r=>`<tr>${cols.map(c=>`<td>${esc(typeof c[1]==="function"?c[1](r):r[c[1]])}</td>`).join("")}</tr>`).join("")}</table></div>`}
function message(type,text){return `<div class="message ${type}">${esc(text)}</div>`}
async function jsonFetch(url,opts){const r=await fetch(url,opts); let d={}; try{d=await r.json()}catch{} if(!r.ok) throw new Error(d.error||`Request failed: ${r.status}`); return d;}
function progressHtml(job,label='Working'){const pct=Math.max(0,Math.min(100,Number(job?.percent||0)));return `<div class="import-progress"><div class="progress-head"><strong>${esc(job?.stage||label)}</strong><span>${pct}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><p class="muted">${esc(job?.message||'Working…')}</p>${job?.errors?.length?table(job.errors.slice(0,6),[['Error','error']]):''}</div>`;}
function statCard(label,value){return `<div class="dash-card"><span>${esc(label)}</span><strong>${Number(value||0).toLocaleString()}</strong></div>`;}
function renderHealth(d){
  const c=d.counts||{};
  setHtml('healthStatus', message(d.ok===false?'error':'success','Library health scan complete.') + (d.protection?.newest_usable_backup?`<div class="notice good">Verified backup available: <code>${esc(d.protection.newest_usable_backup.path)}</code></div>`:'<div class="notice warn">No verified backup found yet. Open Database Safety Center and click Protect Now.</div>'));
  setHtml('healthStats',[
    statCard('Shows',c.shows),statCard('Episodes',c.episodes),statCard('Downloaded',c.downloaded_episodes),statCard('Wanted',c.wanted_episodes),
    statCard('Missing files',c.missing_episode_files),statCard('No location',c.episodes_without_file_location),statCard('Metadata gaps',c.metadata_stale_or_missing),statCard('Duplicate groups',c.duplicate_groups)
  ].join(''));
  const rec=d.recommendations||[];
  setHtml('recommendations',rec.map((x,i)=>`<div class="insight-card ${i?'':'warn'}"><strong>${i?'Recommendation':'Priority'}</strong><span>${esc(x)}</span></div>`).join(''));
  setHtml('missingFiles', table(d.samples?.missing_episode_files||[],[['Show','show_name'],['S/E',r=>`S${r.season}E${r.episode}`],['Episode','name'],['Path','location']]));
  setHtml('episodesWithoutFiles', table(d.samples?.episodes_without_file_location||[],[['Show','show_name'],['S/E',r=>`S${r.season}E${r.episode}`],['Episode','name'],['Status','status']]));
  setHtml('metadataGaps', table([...(d.samples?.shows_missing_external_ids||[]),...(d.samples?.metadata_stale_or_missing||[])].slice(0,25),[['Show','name'],['IMDb','imdb_id'],['TMDb','tmdb_id'],['TVDb','tvdb_id'],['Last Status','last_status']]));
  setHtml('showsWithoutLocations', table(d.samples?.shows_without_location||[],[['Show','name'],['Location','location']]));
  setHtml('duplicates',(d.samples?.duplicates||[]).length?d.samples.duplicates.map((g,i)=>`<div class="result-card"><div class="result-top"><strong>Duplicate group ${i+1}</strong><span class="status-pill">${esc(g.duplicate_count)} files</span></div><div class="result-meta">${esc(g.fingerprint)} • ${esc(g.file_size)} bytes</div><ul>${(g.paths||[]).map(p=>`<li><code>${esc(p)}</code></li>`).join('')}</ul></div>`).join(''):'<p class="muted">No duplicate candidates found.</p>');
}
async function startHealthScan(){
  clearTimeout(healthTimer);
  try{
    setHtml('healthStatus', progressHtml({stage:'Queued',percent:0,message:'Starting Library Health scan…'},'Queued'));
    const d=await jsonFetch('/api/library/health-scan/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({duplicate_limit:25,sample_limit:25})});
    pollHealthScan(d.job.job_id);
  }catch(ex){
    setHtml('healthStatus', message('error', `Library Health could not load/start: ${ex.message}`));
  }
}
async function pollHealthScan(jobId){
  try{
    const d=await jsonFetch('/api/library/health-scan/jobs/'+encodeURIComponent(jobId));
    setHtml('healthStatus', progressHtml(d.job,'Library Health'));
    if(d.job.status==='complete'){
      renderHealth(d.job.result||{});
    }else if(d.job.status==='error'){
      setHtml('healthStatus', message('error', d.job.message||'Library Health scan failed.'));
    }else{
      healthTimer=setTimeout(()=>pollHealthScan(jobId),900);
    }
  }catch(ex){setHtml('healthStatus', message('error', ex.message));}
}
async function previewDuplicates(){
  try{const d=await jsonFetch('/api/library/duplicates/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:100})});cleanupActions=d.actions||[];const apply=byId('applyDupes'); if(apply) apply.disabled=!cleanupActions.length;setHtml('cleanupPlan',`<h3>Cleanup preview</h3><p class="muted">${cleanupActions.length} files would be moved to managed trash.</p>`+table(cleanupActions,[["Action","action"],["Move file","source_path"],["Keep file","keep_path"]]));}
  catch(ex){setHtml('cleanupPlan',message('error',ex.message));}
}
async function applyDuplicates(){
  if(!cleanupActions.length)return;
  if(!confirm(`Move ${cleanupActions.length} duplicate files to managed trash?`))return;
  try{const d=await jsonFetch('/api/library/duplicates/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actions:cleanupActions})});setHtml('cleanupPlan',message('success',`Moved ${d.moved} files. Trash batch: ${d.trash_batch}`));cleanupActions=[];const apply=byId('applyDupes'); if(apply) apply.disabled=true;startHealthScan();}
  catch(ex){setHtml('cleanupPlan',message('error',ex.message));}
}
async function pollGenericJob(jobId,targetId,doneMessage){
  try{
    const d=await jsonFetch('/api/jobs/'+encodeURIComponent(jobId));
    setHtml(targetId,progressHtml(d.job,'Working'));
    if(d.job.status==='complete'){
      setHtml(targetId,progressHtml(d.job,'Complete')+message('success',doneMessage||'Background job complete.'));
      startHealthScan();
    }else if(d.job.status==='error'){
      setHtml(targetId,message('error',d.job.message||'Background job failed.'));
    }else{
      setTimeout(()=>pollGenericJob(jobId,targetId,doneMessage),1000);
    }
  }catch(ex){setHtml(targetId,message('error',ex.message));}
}
async function startMissingMetadata(){
  try{setHtml('missingMetaStatus',progressHtml({stage:'Queued',percent:0,message:'Starting missing metadata refresh…'}));const d=await jsonFetch('/api/metadata/refresh/missing/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:200})});pollGenericJob(d.job.job_id,'missingMetaStatus','Missing metadata refresh complete.')}catch(ex){setHtml('missingMetaStatus',message('error',ex.message));}
}
async function startArtworkRefresh(){
  try{setHtml('artworkStatus',progressHtml({stage:'Queued',percent:0,message:'Starting show and episode artwork refresh…'}));const d=await jsonFetch('/api/metadata/artwork/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:200,include_episodes:true})});pollGenericJob(d.job.job_id,'artworkStatus','Artwork refresh complete.')}catch(ex){setHtml('artworkStatus',message('error',ex.message));}
}
async function runMetadataBatch(){
  try{await jsonFetch('/api/metadata/refresh/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch_size:5})});byId('metadataGaps')?.insertAdjacentHTML('afterbegin',message('success','Metadata batch complete.'));startHealthScan();}
  catch(ex){byId('metadataGaps')?.insertAdjacentHTML('afterbegin',message('error',ex.message));}
}
function fullMetaOptions(){return {batch_size:Number(byId('fullMetaBatch')?.value||10),stale_only:!!byId('fullMetaStaleOnly')?.checked};}
async function previewFullMetadata(){
  try{const d=await jsonFetch('/api/metadata/refresh/full/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fullMetaOptions())});setHtml('fullMetaStatus',message('info',`Full refresh would scan ${Number(d.total||0).toLocaleString()} shows. TMDb configured: ${d.tmdb?.configured?'yes':'no'}.`));}
  catch(ex){setHtml('fullMetaStatus',message('error',ex.message));}
}
async function startFullMetadata(){
  if(!confirm('Start full-library metadata refresh? This can take a while on large libraries.'))return;
  try{const d=await jsonFetch('/api/metadata/refresh/full/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fullMetaOptions())});renderFullMetaJob(d.job);pollFullMeta(d.job.job_id);}
  catch(ex){setHtml('fullMetaStatus',message('error',ex.message));}
}
function renderFullMetaJob(job){
  if(!job)return;const pct=Math.max(0,Math.min(100,Number(job.percent||0)));
  setHtml('fullMetaStatus',`<div class="message info"><strong>${esc(job.stage||job.status)}</strong> ${esc(job.message||'')}</div><div class="progress"><span style="width:${pct}%"></span></div><p class="muted">${pct}% • ${esc(job.processed||0)}/${esc(job.total||0)} processed • ${esc(job.succeeded||0)} ok • ${esc(job.failed||0)} failed ${job.current_show?'• '+esc(job.current_show):''}</p>${(job.errors||[]).length?table(job.errors.slice(0,10),[['Show','name'],['Error','error']]):''}`);
}
async function pollFullMeta(jobId){
  clearTimeout(fullMetaTimer);
  try{const d=await jsonFetch('/api/metadata/refresh/full/jobs/'+encodeURIComponent(jobId));renderFullMetaJob(d.job);if(!['complete','error'].includes(String(d.job.status||'')))fullMetaTimer=setTimeout(()=>pollFullMeta(jobId),2000);else startHealthScan();}
  catch(ex){setHtml('fullMetaStatus',message('error',ex.message));}
}
document.addEventListener('DOMContentLoaded',()=>{byId('previewDupes')?.addEventListener('click',previewDuplicates);byId('applyDupes')?.addEventListener('click',applyDuplicates);byId('refreshMeta')?.addEventListener('click',runMetadataBatch);byId('startMissingMeta')?.addEventListener('click',startMissingMetadata);byId('startArtworkRefresh')?.addEventListener('click',startArtworkRefresh);byId('previewFullMeta')?.addEventListener('click',previewFullMetadata);byId('startFullMeta')?.addEventListener('click',startFullMetadata);byId('refreshHealth')?.addEventListener('click',startHealthScan);startHealthScan();});

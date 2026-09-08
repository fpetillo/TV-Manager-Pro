const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
const $=id=>document.getElementById(id);
async function jsonFetch(url){const r=await fetch(url);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
function bar(job){const pct=Math.max(0,Math.min(100,Number(job.percent||0)));return `<div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>`;}
function row(job){return `<div class="result-card job-card"><div class="result-top"><div><strong>${esc((job.kind||'job').replaceAll('_',' '))}</strong><div class="muted">${esc(job.stage||job.status)} • ${esc(job.message||'')}</div></div><span class="status-pill ${esc(job.status||'')}">${esc(job.status||'queued')}</span></div>${bar(job)}<div class="result-meta">${Number(job.percent||0)}% • ${Number(job.processed||0).toLocaleString()} / ${Number(job.total||0).toLocaleString()} processed • ${Number(job.succeeded||0).toLocaleString()} ok • ${Number(job.failed||0).toLocaleString()} failed • updated ${esc(job.updated_at||'')}</div>${job.current_show?`<p class="muted">Current: ${esc(job.current_show)}</p>`:''}${(job.errors||[]).length?`<details><summary>${job.errors.length} recent errors</summary><pre>${esc(JSON.stringify(job.errors.slice(0,10),null,2))}</pre></details>`:''}</div>`;}
let jobs=[],selectedStatus='all',jobsLoading=false,lastFiltersHtml='';
const statusLabels={queued:'Queued',running:'Running',complete:'Completed',error:'Failed',cancelled:'Cancelled'};
function jobStatus(job){return String(job.status||'queued').toLowerCase();}
function matchingJobs(items,status){return items.filter(job=>status==='all'||(status==='active'?['queued','running'].includes(jobStatus(job)):jobStatus(job)===status));}
function ensureJobFilters(){
  if($('jobStatusFilters'))return;
  const filters=document.createElement('div');filters.id='jobStatusFilters';filters.className='toolbar wrap job-status-filters';filters.setAttribute('role','group');filters.setAttribute('aria-label','Filter jobs by status');
  const summary=document.createElement('p');summary.id='jobFilterSummary';summary.className='muted';summary.setAttribute('role','status');
  $('jobsList').before(filters,summary);
}
function renderJobs(){
  ensureJobFilters();
  const statuses=['all','active',...Object.keys(statusLabels),...new Set(jobs.map(jobStatus).filter(s=>!Object.hasOwn(statusLabels,s)&&!['all','active'].includes(s)))];
  if(!statuses.includes(selectedStatus))statuses.push(selectedStatus);
  const filters=$('jobStatusFilters');
  const html=statuses.map(status=>{
    const label=status==='all'?'All':status==='active'?'Active':statusLabels[status]||status.replaceAll('_',' ');
    return `<button type="button" class="${selectedStatus===status?'blue':'secondary'}" data-status="${esc(status)}" aria-pressed="${selectedStatus===status}">${esc(label)} (${matchingJobs(jobs,status).length})</button>`;
  }).join('');
  if(lastFiltersHtml!==html){
    lastFiltersHtml=html;
    const focused=filters.contains(document.activeElement)?document.activeElement.dataset.status:null;
    filters.innerHTML=html;
    filters.querySelectorAll('button').forEach(button=>{
      button.onclick=()=>{selectedStatus=button.dataset.status;renderJobs();};
      if(button.dataset.status===focused)button.focus();
    });
  }
  const visible=matchingJobs(jobs,selectedStatus);
  $('jobFilterSummary').textContent=`Showing ${visible.length} of ${jobs.length} recent jobs`;
  $('jobsList').innerHTML=visible.length?visible.map(row).join(''):`<p class="muted">${jobs.length?'No jobs match this status.':'No background jobs have run in this process yet.'}</p>`;
}
async function loadJobs(){
  if(jobsLoading)return;
  jobsLoading=true;
  try{const d=await jsonFetch('/api/jobs');jobs=d.jobs||[];renderJobs();}
  catch(e){$('jobsList').innerHTML=`<div class="notice warn">${esc(e.message)}</div>`;}
  finally{jobsLoading=false;}
}
window.addEventListener('DOMContentLoaded',()=>{$('refreshJobs').onclick=loadJobs;renderJobs();loadJobs();setInterval(loadJobs,2500);});

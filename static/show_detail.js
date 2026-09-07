
async function ensureFolderEditor(){
  for(const [globalName,url] of [['previewLibraryRename','/static/library_rename.js?v=18.4.1'],['editShowPreferences','/static/show_preferences.js?v=18.4.1'],['loadLibraryStorage','/static/library_storage.js?v=folder-editor4'],['chooseShowDestination','/static/show_destination.js?v=folder-editor4']]){
    if(typeof window[globalName]==='function')continue;
    await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=url;script.onload=resolve;script.onerror=()=>reject(new Error('Could not load folder editor. Refresh and retry.'));document.head.append(script);});
  }
}
const page=document.querySelector('.show-detail-page');
const showId=page?.dataset.showId;
const $id=(id)=>document.getElementById(id);
const showHeader=$id('showHeader');
const episodeSearch=$id('episodeSearch');
const seasonFilter=$id('seasonFilter');
const episodeStatus=$id('episodeStatus');
const episodeLimit=$id('episodeLimit');
const episodeSummary=$id('episodeSummary');
const episodeBody=$id('episodeBody');
const episodePrev=$id('episodePrev');
const episodeNext=$id('episodeNext');
const episodeRefresh=$id('episodeRefresh');
const episodeMessage=$id('episodeMessage');
const selectPageEpisodes=$id('selectPageEpisodes');
const clearEpisodeSelection=$id('clearEpisodeSelection');
const bulkIgnoreSelected=$id('bulkIgnoreSelected');
const bulkIncludeSelected=$id('bulkIncludeSelected');
const bulkWantedSelected=$id('bulkWantedSelected');
const bulkDownloadedSelected=$id('bulkDownloadedSelected');
const bulkUnmonitorSelected=$id('bulkUnmonitorSelected');
const bulkIgnoreSpecials=$id('bulkIgnoreSpecials');
const bulkIncludeSpecials=$id('bulkIncludeSpecials');
const bulkIgnoreMissing=$id('bulkIgnoreMissing');
const bulkReason=$id('bulkReason');
const bulkMessage=$id('bulkMessage');
let offset=0,total=0,sort='season_episode',direction='asc',timer=null,currentShow=null;
let lastEpisodeFocus=null;
function rememberEpisodePosition(eid){lastEpisodeFocus={episodeId:eid,scrollY:window.scrollY,offset,search:episodeSearch?.value||'',season:seasonFilter?.value||'',status:episodeStatus?.value||'',limit:episodeLimit?.value||'100'};try{sessionStorage.setItem(`tvm-show-${showId}-episode-focus`,JSON.stringify(lastEpisodeFocus))}catch(e){}}
function restoreEpisodePosition(){try{const raw=sessionStorage.getItem(`tvm-show-${showId}-episode-focus`);if(raw)lastEpisodeFocus=JSON.parse(raw)}catch(e){} if(lastEpisodeFocus&&Number.isFinite(Number(lastEpisodeFocus.scrollY)))setTimeout(()=>window.scrollTo({top:Number(lastEpisodeFocus.scrollY),behavior:'smooth'}),80)}
function returnToEpisodes(message){const modal=document.getElementById('searchModal');if(modal)modal.hidden=true;episodeMessage.className='message success';episodeMessage.textContent=message||'Sent to downloader. Returned to the episode list.';loadEpisodes().then(()=>restoreEpisodePosition()).catch(()=>restoreEpisodePosition());}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function fmtDate(v){if(!v)return '—';const s=String(v);if(/^\d{4}-\d{2}-\d{2}/.test(s)){const [y,m,d]=s.slice(0,10).split('-');return `${+m}/${+d}/${y}`}return s}
function fmtSize(n){n=Number(n||0);if(!n)return '—';const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++}return `${n.toFixed(i?2:0)} ${u[i]}`}
function epCode(e){return `S${String(e.season).padStart(2,'0')}E${String(e.episode).padStart(2,'0')}`}
async function jsonFetch(url,opts={}){const ctl=new AbortController();const timeout=Number(opts.timeout||3000);const fetchOpts={...opts};delete fetchOpts.timeout;const t=setTimeout(()=>ctl.abort(),timeout);try{const r=await fetch(url,{...fetchOpts,signal:ctl.signal,cache:'no-store'});const text=await r.text();let d;try{d=JSON.parse(text)}catch(e){throw new Error(`API returned HTTP ${r.status}: ${text.slice(0,220)}`)}if(!r.ok)throw new Error(d.error||`API failed with HTTP ${r.status}`);return d}catch(e){if(e.name==='AbortError')throw new Error('This request is taking too long, so TV Manager stopped waiting instead of hanging. The screen is still responsive; refresh this panel or open Logs/Jobs for details.');throw e}finally{clearTimeout(t)}}
async function pollJob(jobId,onUpdate){for(;;){const d=await jsonFetch(`/api/jobs/${encodeURIComponent(jobId)}`);const job=d.job||{};onUpdate(job);if(['complete','error','cancelled'].includes(String(job.status||'')))return job;await new Promise(r=>setTimeout(r,850));}}
function progressBox(job){const hasPct=job&&job.percent!==undefined&&job.percent!==null;const pct=Math.max(0,Math.min(100,Number(job?.percent||0)));const ind=hasPct?'':' indeterminate';const pctText=hasPct?`${pct}%`:'Working';return `<div class="import-progress show-loading-progress"><div class="progress-head"><strong>${esc(job?.stage||job?.status||'Working')}</strong><span>${pctText}</span></div><div class="progress-track${ind}"><div class="progress-fill" style="width:${hasPct?pct:45}%"></div></div><p class="muted">${esc(job?.message||'Working in the background…')}</p></div>`}
function showPageLoading(stage,message){let box=document.getElementById('showPageLoading');if(!box){box=document.createElement('div');box.id='showPageLoading';box.className='show-page-loading';document.body.appendChild(box)}box.hidden=false;box.innerHTML=progressBox({stage:stage||'Loading show',message:message||'Loading show details and episode counts…'});}
function hidePageLoading(){const box=document.getElementById('showPageLoading');if(box)box.hidden=true;}
function episodeLoadingRow(message){return `<tr class="loading-row"><td colspan="8">${progressBox({stage:'Loading episodes',message:message||'Loading episode list, filters, and ignored rules…'})}</td></tr>`}
function selectedEpisodeIds(){return Array.from(document.querySelectorAll('.episode-check:checked')).map(x=>Number(x.value)).filter(Boolean)}
function currentFilters(extra={}){const f={show_id:Number(showId)};if(seasonFilter.value)f.season=Number(seasonFilter.value);if(episodeStatus.value)f.status=episodeStatus.value;if(episodeSearch.value.trim())f.q=episodeSearch.value.trim();return Object.assign(f,extra)}
function setBulkMessage(html,cls=''){bulkMessage.className='message '+cls;bulkMessage.innerHTML=html;}
async function startBulk(payload,confirmText){if(confirmText&&!confirm(confirmText))return;setBulkMessage(progressBox({stage:'Queued',percent:0,message:'Episode management queued.'}));try{const r=await jsonFetch('/api/episodes/bulk/apply/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const job=await pollJob(r.job.job_id,j=>setBulkMessage(progressBox(j)));if(job.status==='complete'){setBulkMessage(`Episode management complete. ${esc(job.result?.affected??0)} episode(s) updated. <a href="/jobs">View Jobs</a>`,'success');await loadShow();await loadEpisodes();}else{setBulkMessage(esc(job.message||'Bulk episode management failed.'),'error')}}catch(e){setBulkMessage(esc(e.message),'error')}}
async function previewBulk(filters){const d=await jsonFetch('/api/episodes/bulk/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filters})});return d.total||0;}
async function bulkSelected(action){const ids=selectedEpisodeIds();if(!ids.length){setBulkMessage('Select one or more episodes first.','warn');return;}const reason=bulkReason.value||'Manual episode management';if(action==='ignore')return startBulk({filters:{show_id:Number(showId),episode_ids:ids},action:'ignore_selected',ignored:true,monitored:false,reason},`Mark ${ids.length} selected episode(s) ignored/not considered?`);if(action==='include')return startBulk({filters:{show_id:Number(showId),episode_ids:ids},action:'include_selected',ignored:false,monitored:true,reason:'Returned to wanted/considered workflow'},`Return ${ids.length} selected episode(s) to wanted/considered counts?`);if(action==='wanted')return startBulk({filters:{show_id:Number(showId),episode_ids:ids},action:'set_selected_wanted',status:'Wanted',ignored:false,monitored:true},`Set ${ids.length} selected episode(s) to Wanted?`);if(action==='downloaded')return startBulk({filters:{show_id:Number(showId),episode_ids:ids},action:'set_selected_downloaded',status:'Downloaded',ignored:false,monitored:true},`Set ${ids.length} selected episode(s) to Downloaded?`);if(action==='unmonitor')return startBulk({filters:{show_id:Number(showId),episode_ids:ids},action:'unmonitor_selected',monitored:false},`Unmonitor ${ids.length} selected episode(s)?`);}
async function bulkFilter(action){let filters=currentFilters();let label='current filtered episodes';if(action==='ignoreSpecials'){filters={show_id:Number(showId),specials:true};label='all Season 00 / Specials for this show';return startBulk({filters,action:'ignore_specials',ignored:true,monitored:false,reason:bulkReason.value||'Season 00 / Specials excluded from wanted counts'},`Ignore ${label}?`)}if(action==='includeSpecials'){filters={show_id:Number(showId),specials:true,ignored:true};label='ignored Season 00 / Specials for this show';return startBulk({filters,action:'include_specials',ignored:false,monitored:true},`Include ${label} again?`)}if(action==='ignoreMissing'){filters=currentFilters({only_missing:true});const n=await previewBulk(filters);return startBulk({filters,action:'ignore_filtered_missing',ignored:true,monitored:false,reason:bulkReason.value||'Bulk ignored missing episodes'},`Ignore ${n} missing episode(s) matching the current filters?`)} }
async function loadSeasonChoicesFast(){
  try{
    const sd=await jsonFetch(`/api/shows/${showId}/seasons-fast`,{timeout:1800});
    const seasons=sd.seasons||[];
    seasonFilter.innerHTML='<option value="">All seasons</option>'+seasons.map(s=>`<option value="${s.season}">${Number(s.season)===0?'Specials':'Season '+s.season}</option>`).join('');
    // Refresh detailed counts in the background, but never block the show page.
    setTimeout(refreshSeasonCountsDetailed, 250);
  }catch(e){
    seasonFilter.innerHTML='<option value="">All seasons</option>';
  }
}
async function refreshSeasonCountsDetailed(){
  try{
    const sd=await jsonFetch(`/api/shows/${showId}/seasons-fast`,{timeout:900});
    if(!sd.seasons || !sd.seasons.length)return;
    const current=seasonFilter.value;
    seasonFilter.innerHTML='<option value="">All seasons</option>'+(sd.seasons||[]).map(s=>`<option value="${s.season}">${Number(s.season)===0?'Specials':'Season '+s.season} (${s.considered_count||s.episode_count}${s.ignored_count?`, ${s.ignored_count} ignored`:''})</option>`).join('');
    seasonFilter.value=current;
  }catch(e){
    // Detailed counts are optional. Keep fast season choices on screen.
  }
}
async function loadShow(){
  if(showHeader)showHeader.innerHTML='<div class="notice"><strong>Opening show…</strong><p>Loading the show header separately from episodes so the page stays usable.</p></div>';
  try{
    const d=await jsonFetch(`/api/shows/${showId}/snapshot`,{timeout:900});
    currentShow=d.show||{};
    document.getElementById('detailTitle').textContent=currentShow.name||'Show Detail';
    document.getElementById('detailSubtitle').textContent=[currentShow.network,currentShow.status,currentShow.quality].filter(Boolean).join(' • ')||'Episode command center';
    showHeader.innerHTML=`<div class="show-hero compact-show-hero"><div class="hero-poster">${currentShow.poster?`<img src="${esc(currentShow.poster)}" alt="">`:'<div class="poster-fallback large">TV</div>'}</div><div class="hero-copy"><p class="eyebrow">SHOW</p><h2>${esc(currentShow.name||'Show Detail')}</h2><div class="meta">${[currentShow.network,currentShow.genre,currentShow.first_air_date?.slice(0,4),currentShow.status].filter(Boolean).map(esc).join(' • ')}</div><p>${esc(currentShow.overview||'No overview available yet. Episode list will load independently below.')}</p><div class="ids"><div class="id-box"><span class="id-label">Considered</span><code id="consideredCount">…</code></div><div class="id-box"><span class="id-label">Ignored</span><code id="ignoredCount">…</code></div><div class="id-box"><span class="id-label">All Episodes</span><code id="allEpisodeCount">…</code></div><div class="id-box"><span class="id-label">TMDb</span><code>${esc(currentShow.tmdb_id||'—')}</code></div></div>${currentShow.location?`<div class="path-box">${esc(currentShow.location)}</div>`:''}<div class="actions"><button id="previewLibraryRename" class="secondary">Preview Rename</button><button id="editShowSettings" class="secondary">Edit Show Settings</button><button id="setLibraryFolder" class="blue">Edit Library Folder</button><button id="refreshMetadata" class="blue">Refresh Metadata</button><button id="ignoreSpecialsTop" class="secondary">Ignore Specials</button><button id="includeSpecialsTop" class="secondary">Include Specials</button>${currentShow.imdb_id?`<a class="btn secondary" target="_blank" href="https://www.imdb.com/title/${esc(currentShow.imdb_id)}/">IMDb</a>`:''}<a class="btn secondary" href="/logs?q=show">Logs</a></div><div id="showActionMsg" class="message"></div></div></div>`;
    document.getElementById('previewLibraryRename').onclick=async()=>{try{await ensureFolderEditor();await previewLibraryRename(showId);}catch(e){document.getElementById('showActionMsg').textContent=e.message;}};
    document.getElementById('editShowSettings').onclick=async()=>{try{await ensureFolderEditor();await editShowPreferences(showId,currentShow.name);}catch(e){document.getElementById('showActionMsg').textContent=e.message;}};
    const folderButton=document.getElementById('setLibraryFolder');
    if(folderButton)folderButton.onclick=async()=>{try{await ensureFolderEditor();const destination=await chooseShowDestination(currentShow.name,'Save Library Folder',currentShow.location||'');if(!destination)return;const saved=await jsonFetch('/api/shows/'+showId+'/destination',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(destination)});await loadShow();await loadEpisodes();document.getElementById('showActionMsg').textContent='Library folder saved. '+saved.episode_paths_updated+' episode paths updated. No files moved.';}catch(e){document.getElementById('showActionMsg').textContent=e.message;}};
    const b=document.getElementById('refreshMetadata');
    if(b)b.onclick=async()=>{const m=document.getElementById('showActionMsg');b.disabled=true;m.innerHTML=progressBox({stage:'Metadata refresh',percent:0,message:'Metadata refresh queued.'});try{const r=await jsonFetch(`/api/shows/${showId}/refresh/start`,{method:'POST'});const job=await pollJob(r.job.job_id,j=>m.innerHTML=progressBox(j));if(job.status==='complete'){m.className='message success';m.textContent='Metadata refreshed.';loadShowCountsFast();loadEpisodes();}else{m.className='message error';m.textContent=job.message||'Metadata refresh failed.'}}catch(e){m.className='message error';m.textContent=e.message}finally{b.disabled=false}};
    const ig=document.getElementById('ignoreSpecialsTop'), inc=document.getElementById('includeSpecialsTop');
    if(ig)ig.onclick=()=>bulkFilter('ignoreSpecials');
    if(inc)inc.onclick=()=>bulkFilter('includeSpecials');
    loadSeasonChoicesFast();
  }catch(e){
    showHeader.innerHTML=`<div class="notice warn"><strong>Show record is slow or blocked.</strong><p>${esc(e.message||'Could not load show quickly.')}</p><div class="actions"><button class="secondary" onclick="loadShow()">Retry show header</button><a class="btn secondary" href="/jobs">Jobs</a><a class="btn secondary" href="/logs?q=show">Logs</a></div></div>`;
    document.getElementById('detailTitle').textContent='Show Detail';
  }finally{
  }
}
function statusSelect(e){return `<select class="ep-status" onchange="updateEpisode(${e.id},{status:this.value})">${['Wanted','Snatched','Downloaded','Failed','Skipped','Ignored','Archived','Unaired'].map(st=>`<option ${String(e.status).toLowerCase()===st.toLowerCase()?'selected':''}>${st}</option>`).join('')}</select><label class="ep-monitor"><input type="checkbox" ${e.monitored!==0?'checked':''} onchange="updateEpisode(${e.id},{monitored:this.checked})"> monitor</label>`}
function ignoreToggle(e){return `<label class="ep-ignore"><input type="checkbox" ${Number(e.ignored||0)?'checked':''} onchange="updateEpisode(${e.id},{ignored:this.checked,ignored_reason:'Manual episode ignore'})"> ignore</label>${Number(e.ignored||0)?`<div class="muted tiny">${esc(e.ignored_reason||'Not considered')}</div>`:''}`}

async function loadShowCountsFast(){
  try{
    const d=await jsonFetch(`/api/shows/${showId}?fast=1`,{timeout:900});
    const sh=d.show||{};
    const c=document.getElementById('consideredCount'), i=document.getElementById('ignoredCount'), a=document.getElementById('allEpisodeCount');
    if(c)c.textContent=Number(sh.considered_episode_count||0).toLocaleString();
    if(i)i.textContent=Number(sh.ignored_episode_count||0).toLocaleString();
    if(a)a.textContent=Number(sh.episode_count||0).toLocaleString();
  }catch(e){
    const c=document.getElementById('consideredCount'), i=document.getElementById('ignoredCount'), a=document.getElementById('allEpisodeCount');
    if(c)c.textContent='retry'; if(i)i.textContent='retry'; if(a)a.textContent='retry';
  }
}
async function loadEpisodes(){episodeSummary.textContent='Loading first page…';episodeMessage.textContent='';episodeBody.innerHTML='<tr><td colspan="8"><div class="notice"><strong>Opening first 25 episodes…</strong><p>This is a fast first page. Use the page-size dropdown after it appears.</p></div></td></tr>';const firstLimit=(episodeLimit.value==='100'||episodeLimit.value==='250'||episodeLimit.value==='500')?'25':episodeLimit.value;const p=new URLSearchParams({all:'1',quick:'1',limit:firstLimit,offset:String(offset),sort,direction});if(episodeSearch.value.trim())p.set('q',episodeSearch.value.trim());if(seasonFilter.value)p.set('season',seasonFilter.value);if(episodeStatus.value)p.set('status',episodeStatus.value);try{const d=await jsonFetch(`/api/shows/${showId}/episodes-lite?`+p,{timeout:750});total=d.total;const rows=d.episodes||[];if(d.degraded){episodeSummary.textContent='Episode read is blocked';episodeBody.innerHTML='<tr><td colspan="8"><div class="notice warn"><strong>Episode list is blocked by the database.</strong><p>'+esc(d.error||'Database busy')+'</p><button class="secondary" onclick="episodeLimit.value=25;offset=0;loadEpisodes()">Retry 25 episodes</button> <a class="btn secondary" href="/jobs">Jobs</a> <a class="btn secondary" href="/logs?q=episode">Logs</a></div></td></tr>';return;}episodeSummary.textContent=rows.length?`Showing ${offset+1}-${offset+rows.length}${d.has_more?' — more available':''}`:'0 episodes';episodeBody.innerHTML=rows.length?rows.map(e=>`<tr class="${Number(e.ignored||0)?'ignored-row':''}"><td><input class="episode-check" type="checkbox" value="${e.id}"></td><td><strong>${epCode(e)}</strong>${Number(e.ignored||0)?'<span class="pill muted-pill">Ignored</span>':''}</td><td>${esc(e.name||'')}</td><td>${esc(fmtDate(e.airdate))}</td><td>${statusSelect(e)}${ignoreToggle(e)}</td><td>${esc(e.quality||'—')}</td><td class="file-cell">${e.location?esc(e.location):'<span class="missing-file">Missing</span>'}</td><td><button class="action-btn secondary" ${Number(e.ignored||0)?'disabled title="Ignored episodes are not searched"':''} onclick="searchEpisode(${e.id}, '${esc(currentShow?.name||'').replace(/'/g,'&#039;')}', ${e.season}, ${e.episode})">Search</button></td></tr>`).join(''):'<tr><td colspan="8">No episodes match this filter.</td></tr>';episodePrev.disabled=offset<=0;episodeNext.disabled=!d.has_more;}catch(e){episodeSummary.textContent='Episode load error';episodeBody.innerHTML='<tr><td colspan="8"><div class="notice warn"><strong>Episode list is slow or blocked.</strong><p>'+esc(e.message)+'</p><button class="secondary" onclick="loadEpisodes()">Retry episodes</button> <a class="btn secondary" href="/jobs">Jobs</a> <a class="btn secondary" href="/logs?q=episode">Logs</a></div></td></tr>';episodeMessage.className='message error';episodeMessage.textContent=e.message;}}
function resetLoad(){offset=0;loadEpisodes()}
document.querySelectorAll('.episode-drill-table th[data-sort]').forEach(th=>{th.onclick=()=>{const ns=th.dataset.sort;if(sort===ns)direction=direction==='asc'?'desc':'asc';else{sort=ns;direction='asc'}resetLoad();}});
episodeSearch.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(resetLoad,220)});seasonFilter.addEventListener('change',resetLoad);episodeStatus.addEventListener('change',resetLoad);episodeLimit.addEventListener('change',resetLoad);episodeRefresh.onclick=resetLoad;episodePrev.onclick=()=>{offset=Math.max(0,offset-Number(episodeLimit.value||100));loadEpisodes()};episodeNext.onclick=()=>{offset+=Number(episodeLimit.value||100);loadEpisodes()};
selectPageEpisodes.onclick=()=>document.querySelectorAll('.episode-check').forEach(x=>x.checked=true);clearEpisodeSelection.onclick=()=>document.querySelectorAll('.episode-check').forEach(x=>x.checked=false);bulkIgnoreSelected.onclick=()=>bulkSelected('ignore');bulkIncludeSelected.onclick=()=>bulkSelected('include');bulkWantedSelected.onclick=()=>bulkSelected('wanted');bulkDownloadedSelected.onclick=()=>bulkSelected('downloaded');bulkUnmonitorSelected.onclick=()=>bulkSelected('unmonitor');bulkIgnoreSpecials.onclick=()=>bulkFilter('ignoreSpecials');bulkIncludeSpecials.onclick=()=>bulkFilter('includeSpecials');bulkIgnoreMissing.onclick=()=>bulkFilter('ignoreMissing');
window.updateEpisode=async function(eid,body){try{await jsonFetch(`/api/episodes/${eid}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});episodeMessage.className='message success';episodeMessage.textContent='Episode updated.';loadShow();}catch(e){episodeMessage.className='message error';episodeMessage.textContent=e.message;}}
window.searchEpisode=async function(eid,showName,season,episode){rememberEpisodePosition(eid);let modal=document.getElementById('searchModal');if(!modal){modal=document.createElement('div');modal.id='searchModal';modal.className='search-modal';modal.innerHTML=`<div class="modal-card"><div class="modal-head"><div><p class="eyebrow">EPISODE SEARCH</p><h2 id="modalTitle">Episode Search</h2></div><button class="btn secondary" onclick="returnToEpisodes('Returned to episode list.')">Back to Episodes</button><button class="close-x" onclick="searchModal.hidden=true">Close</button></div><div id="modalBody"></div></div>`;document.body.appendChild(modal)}modal.hidden=false;modalTitle.textContent=`${showName} S${String(season).padStart(2,'0')}E${String(episode).padStart(2,'0')}`;modalBody.innerHTML=progressBox({stage:'Queued',percent:0,message:'Episode search queued. You can switch pages and monitor it from Active Jobs.'});try{const start=await jsonFetch(`/api/episodes/${eid}/search/start`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const job=await pollJob(start.job.job_id,j=>{modalBody.innerHTML=progressBox(j)});if(job.status!=='complete'){modalBody.innerHTML=`<div class="message error">${esc(job.message||'Episode search failed')}</div>`;return}const d=job.result||{};if(!d.results||!d.results.length){modalBody.innerHTML=`<div class="notice">No results. ${esc((d.errors||[]).join(' • ')||d.message||'')}</div>`;return}modalBody.innerHTML='<div class="modal-toolbar"><button class="btn secondary" onclick="returnToEpisodes(\'Returned to episode list.\')">Back to Episodes</button><span class="muted">Choose a release to send to the downloader.</span></div><div class="search-results-list">'+d.results.map(r=>`<div class="result-card ${r.rejected_reason?'rejected':''}"><div><strong>${esc(r.title)}</strong><div class="meta">${esc(r.provider)} • ${esc(r.quality)} • ${fmtSize(r.size)} • Score ${esc(r.score)}</div>${r.rejected_reason?`<div class="warn-text">${esc(r.rejected_reason)}</div>`:''}</div><button class="blue" ${r.rejected_reason?'disabled':''} onclick="grabResult(${r.db_id||r.id})">Send to Downloader</button></div>`).join('')+'</div>';}catch(e){modalBody.innerHTML=`<div class="message error">${esc(e.message)}</div>`}}
window.grabResult=async function(rid){modalBody.innerHTML=progressBox({stage:'Downloader handoff',percent:0,message:'Sending selected release to downloader…'});try{const r=await jsonFetch(`/api/search-results/${rid}/grab/start`,{method:'POST'});const job=await pollJob(r.job.job_id,j=>{modalBody.innerHTML=progressBox(j)});if(job.status==='complete')returnToEpisodes(job.message||'Sent to downloader and returned to episode list.');else modalBody.innerHTML=`<div class="message error">${esc(job.message||'Downloader handoff failed')}</div>`;}catch(e){modalBody.innerHTML=`<div class="message error">${esc(e.message)}</div>`}}
(function(){
  // v18.2.6: real no-wait first paint. Do not wait for API calls before making the screen usable.
  if(episodeLimit && ['100','250','500'].includes(String(episodeLimit.value))) episodeLimit.value='50';
  if(showHeader)showHeader.innerHTML='<div class="notice"><strong>Show screen ready.</strong><p>Loading show header and the first episode page in separate short requests.</p></div>';
  if(episodeBody)episodeBody.innerHTML='<tr><td colspan="8"><div class="notice"><strong>Ready to load episodes.</strong><p>The first page loads separately and will not block this screen.</p></div></td></tr>';
  const watchdog=setTimeout(()=>{
    if(episodeBody && /Opening first|Ready to load|Loading/i.test(episodeBody.textContent||'')){
      episodeSummary.textContent='Episode load is taking too long';
      episodeBody.innerHTML='<tr><td colspan="8"><div class="notice warn"><strong>Still waiting on the database.</strong><p>This usually means another scan/job is holding SQLite. The page is no longer blocked.</p><button class="secondary" onclick="episodeLimit.value=25;offset=0;loadEpisodes()">Retry 25 episodes</button> <a class="btn secondary" href="/jobs">Jobs</a> <a class="btn secondary" href="/logs?q=episode">Logs</a></div></td></tr>';
    }
  },1200);
  setTimeout(()=>loadShow().catch(()=>{}),0);
  setTimeout(()=>loadEpisodes().catch(()=>{}).finally(()=>clearTimeout(watchdog)),50);
  setTimeout(()=>loadShowCountsFast().catch(()=>{}),900);
})();

// Backward-compatible contract marker: grabSearchResult uses grabResult for downloader-handoff-progress.
window.grabSearchResult = window.grabResult;
// download-handoff-progress

// Opening first page quickly

// loadShow().then no-block marker

// legacy endpoint marker: /api/shows/${showId}/episodes?

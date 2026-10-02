/* In-place recovery for missing destinations and deliberately repeated downloads. */
(() => {
  // Keep show titles out of executable HTML attributes (apostrophes, quotes, etc.).
  window.bindEpisodeSearch=(host,showName,episodes)=>{
    const rows=new Map(episodes.map(episode=>[String(episode.id),episode]));
    host.querySelectorAll('[data-search-episode]').forEach(button=>{
      const episode=rows.get(button.dataset.searchEpisode);
      if(episode)button.onclick=()=>window.searchEpisode(episode.id,showName,episode.season,episode.episode);
    });
  };
  async function request(url,body={}) {
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await r.json();return {ok:r.ok,data};
  }
  function text(host,value){host.replaceChildren();const p=document.createElement('p');p.textContent=value;host.append(p);}
  function progress(host,job){
    text(host,job.message||'Working…');const track=document.createElement('div');track.className='progress-track download-handoff-progress';track.setAttribute('role','progressbar');track.setAttribute('aria-label',job.stage||'Progress');const value=Math.max(0,Math.min(100,Number(job.percent)||0));track.setAttribute('aria-valuenow',value);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax','100');const fill=document.createElement('div');fill.className='progress-fill';fill.style.width=value+'%';track.append(fill);host.append(track);
  }
  function button(host,label,action){const b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=label;b.onclick=action;host.append(b);return b;}
  async function poll(start,host){
    let job=start;
    while(!['complete','error','cancelled'].includes(job.status)){
      progress(host,job);await new Promise(resolve=>setTimeout(resolve,700));
      const response=await fetch('/api/jobs/'+encodeURIComponent(job.job_id));const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not read job progress. Check Active Jobs before retrying.');job=data.job||data;
    }
    return job;
  }
  async function folderScripts(){
    const version=new URL(document.querySelector('script[src*="/static/workflow_recovery.js"]')?.src||location.href).searchParams.get('v')||Date.now();
    for(const [name,path] of [['loadLibraryStorage','library_storage'],['chooseShowDestination','show_destination']]){
      if(typeof window[name]==='function')continue;
      await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/static/'+path+'.js?v='+encodeURIComponent(version);script.onload=resolve;script.onerror=()=>reject(new Error('Could not load folder controls. Refresh the page and retry.'));document.head.append(script);});
    }
  }
  window.showFolderIssues=(host,issues=[])=>{
    if(!host||!issues.length)return;
    const box=document.createElement('details');box.className='folder-recovery-list';box.open=true;
    const summary=document.createElement('summary');summary.textContent=issues.length+' show folder(s) need attention';box.append(summary);
    for(const issue of issues){const row=document.createElement('p');row.textContent=issue.name+': '+(issue.location||'No folder configured')+' ';const link=document.createElement('a');link.href=issue.repair_url;link.target='_blank';link.rel='noopener';link.textContent='Fix Folder & Refresh';row.append(link);box.append(row);}host.append(box);
  };
  async function repairFolder(issue,host){
    await folderScripts();text(host,issue.error);
    const choice=await chooseShowDestination(issue.name,'Save Folder & Retry Metadata',issue.location||'','tmdb',issue);
    if(!choice){text(host,'Metadata refresh cancelled. Choose a library folder before retrying.');return false;}
    const r=await fetch('/api/shows/'+issue.show_id+'/destination',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(choice)});
    const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not save the folder.');
    return true;
  }
  window.refreshShowWithFolder=async(sid,host)=>{
    try{
      while(true){
        text(host,'Checking the show folder and starting metadata refresh…');
        const r=await request('/api/shows/'+sid+'/refresh/start');
        if(!r.ok){if(r.data.code==='show_folder_required'){if(await repairFolder(r.data,host))continue;return null;}throw new Error(r.data.error||'Could not start metadata refresh.');}
        const job=await poll(r.data.job,host);
        if(job.result?.recovery?.code==='show_folder_required'){if(await repairFolder(job.result.recovery,host))continue;return null;}
        if(job.status!=='complete')throw new Error(job.message||'Metadata refresh failed.');
        text(host,'Metadata refreshed.');return job.result;
      }
    }catch(error){text(host,error.message);button(host,'Retry Metadata / Fix Folder',async()=>{if(await window.refreshShowWithFolder(sid,host))location.reload();});return null;}
  };
  function showDownloadError(rid,host,data,onSuccess){
    text(host,data.error||'Could not send this release.');
    if(data.force_available)button(host,'Force Download…',()=>forceDialog(rid,host,onSuccess));
    button(host,'Try Again',()=>window.sendReviewedDownload(rid,host,onSuccess));
    const link=document.createElement('a');link.href='/download-center';link.className='btn secondary';link.textContent='Review Download Center';host.append(link);
  }
  async function forceDialog(rid,host,onSuccess){
    text(host,'Loading the current download state…');
    try{
      const r=await request('/api/search-results/'+rid+'/force-preview');if(!r.ok){showDownloadError(rid,host,r.data,onSuccess);return;}
      const dialog=document.createElement('dialog');dialog.className='destination-dialog force-download-dialog';dialog.setAttribute('aria-label','Force download review');
      const heading=document.createElement('h2');heading.textContent='Force this download?';dialog.append(heading);
      const title=document.createElement('p');title.textContent=r.data.plan.title;dialog.append(title);
      const list=document.createElement('ul');for(const conflict of r.data.plan.conflicts){const item=document.createElement('li');item.textContent=`${conflict.kind} #${conflict.id}: ${conflict.status} — ${conflict.client} — ${conflict.title}`;list.append(item);}dialog.append(list);
      const note=document.createElement('p');note.textContent='This sends the selected release again. Existing downloads and history are kept; an active download is not cancelled. You may receive duplicate files. The download client may still reject a duplicate.';dialog.append(note);
      const actions=document.createElement('div');actions.className='toolbar preference-actions';dialog.append(actions);
      const cancel=button(actions,'Cancel',()=>{dialog.close();dialog.remove();showDownloadError(rid,host,{error:'Force download cancelled.',force_available:true},onSuccess);});
      button(actions,'Confirm Force Download',()=>{dialog.close();dialog.remove();window.sendReviewedDownload(rid,host,onSuccess,r.data.token);}).className='blue';
      dialog.oncancel=event=>{event.preventDefault();cancel.click();};document.body.append(dialog);dialog.showModal();
    }catch(error){showDownloadError(rid,host,{error:error.message},onSuccess);}
  }
  window.sendReviewedDownload=async(rid,host,onSuccess,forceToken=null)=>{
    text(host,forceToken?'Sending the reviewed force download…':'Sending selected release to downloader…');
    try{
      const r=await request('/api/search-results/'+rid+'/grab/start',forceToken?{force_token:forceToken}:{});
      if(!r.ok){showDownloadError(rid,host,r.data,onSuccess);return;}
      const job=await poll(r.data.job,host);
      if(job.status!=='complete'){showDownloadError(rid,host,job.result?.recovery||{error:job.message},onSuccess);return;}
      text(host,job.message||'Release queued.');if(onSuccess)await onSuccess(job);
    }catch(error){showDownloadError(rid,host,{error:error.message},onSuccess);}
  };
})();

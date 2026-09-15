(() => {
  const id=window.metadataChangeShowId;
  const byId=id=>document.getElementById(id);
  const message=byId('migrationMessage');
  let preview=null,show=null;
  const label=ep=>`S${String(ep.season).padStart(2,'0')}E${String(ep.episode).padStart(2,'0')} · ${ep.name||'Untitled'}`;
  async function request(path,body){
    const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Metadata request failed');return d;
  }
  function invalidate(){preview=null;byId('migrationReview').hidden=true;}
  byId('migrationSource').onchange=()=>{invalidate();byId('migrationRemoteId').value=show?.[byId('migrationSource').value+'_id']||'';if(byId('migrationSource').value==='tmdb')byId('migrationOrder').value='official';};
  byId('migrationRemoteId').oninput=invalidate;byId('migrationOrder').onchange=invalidate;
  byId('migrationPreview').onsubmit=async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;invalidate();message.textContent='Fetching complete episode metadata for review…';
    try{
      preview=await request(`/api/shows/${id}/metadata-change/preview`,{provider:byId('migrationSource').value,remote_id:byId('migrationRemoteId').value,order:byId('migrationOrder').value});
      const plan=preview.plan;byId('migrationTarget').textContent=`New metadata: ${plan.target.name} · ${plan.target.provider.toUpperCase()} · ${plan.target.order==='dvd'?'DVD order':'Aired order'}`;
      byId('migrationCounts').textContent=`${plan.matches.length} existing episodes · ${plan.target.episodes.length} episodes at the source · ${plan.unmatched} need a match`;
      byId('migrationRows').replaceChildren();
      for(const row of plan.matches){
        const tr=document.createElement('tr'),current=document.createElement('td'),choice=document.createElement('td'),reason=document.createElement('td');
        current.textContent=label(row)+(row.location?' · File recorded':'');reason.textContent=row.reason;
        const select=document.createElement('select');select.dataset.episodeId=row.episode_id;select.setAttribute('aria-label','New episode for '+label(row));
        select.add(new Option('Choose matching episode…',''));
        if(row.target_index!==null)select.add(new Option(label(plan.target.episodes[row.target_index]),String(row.target_index)));
        select.onfocus=()=>{
          const value=select.value;select.replaceChildren(new Option('Choose matching episode…',''));
          plan.target.episodes.forEach((ep,index)=>select.add(new Option(label(ep),String(index))));select.value=value;
        };
        select.onblur=()=>{
          const value=select.value;select.replaceChildren(new Option('Choose matching episode…',''));
          if(value!=='')select.add(new Option(label(plan.target.episodes[Number(value)]),value));select.value=value;
        };
        select.value=row.target_index===null?'':String(row.target_index);choice.append(select);tr.append(current,choice,reason);byId('migrationRows').append(tr);
      }
      byId('migrationReview').hidden=false;byId('migrationConfirmation').value='';message.textContent='Review the show identity and every episode match before confirming.';
    }catch(error){message.textContent=error.message;}finally{button.disabled=false;}
  };
  byId('migrationApply').onsubmit=async event=>{
    event.preventDefault();if(!preview)return;const button=event.submitter;button.disabled=true;
    const choices={};for(const select of byId('migrationRows').querySelectorAll('select'))choices[select.dataset.episodeId]=select.value===''?null:Number(select.value);
    try{const result=await request(`/api/shows/${id}/metadata-change/apply`,{token:preview.token,choices,confirmation:byId('migrationConfirmation').value});message.textContent=`${result.message} ${result.updated} updated; ${result.added} added.`;invalidate();}catch(error){message.textContent=error.message;}finally{button.disabled=false;}
  };
  request(`/api/shows/${id}?fast=1`).then(data=>{show=data.show;byId('migrationShow').textContent=show.name;byId('migrationSource').value=show.metadata_provider||'tmdb';byId('migrationRemoteId').value=show[(show.metadata_provider||'tmdb')+'_id']||'';byId('migrationOrder').value=show.episode_order||'official';}).catch(error=>{message.textContent=error.message;});
})();

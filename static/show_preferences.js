window.buildShowPreferences=function(host,values,profiles){
  const section=document.createElement('fieldset');const legend=document.createElement('legend');section.className='show-preferences';legend.textContent='Show preferences';section.append(legend);
  const fields={};
  function field(key,label,choices,initial){const wrapper=document.createElement('label');wrapper.className='field';wrapper.textContent=label;const input=document.createElement(choices?'select':'input');if(choices)for(const [value,text] of choices){const o=document.createElement('option');o.value=value;o.textContent=text;input.append(o);}input.value=values[key]??initial??'';wrapper.append(input);section.append(wrapper);fields[key]=input;}
  field('quality_profile_id','Quality profile',[['','No profile'],...profiles.map(p=>[p.id,p.name])],'');
  field('metadata_language','Metadata language (for example en-US)','', 'en-US');
  for(const [key,label] of [['past_episode_status','Newly discovered aired episodes'],['future_episode_status','Newly discovered future episodes']])field(key,label,[['Wanted','Wanted'],['Skipped','Skipped'],['Ignored','Ignored']],'Wanted');
  for(const [key,label,fallback] of [['paused','Pause searching',0],['monitor_new','Monitor new episodes',1],['search_enabled','Enable searching',1],['subtitles_enabled','Automatically download subtitles',1],['season_folders','Use season folders',1],['scene_numbering','Use configured scene numbering',0],['air_by_date','Search by air date',0],['sports','Sports releases',0],['anime','Anime / absolute numbering',0]]){const labelNode=document.createElement('label');labelNode.className='preference-switch';const cb=document.createElement('input');cb.type='checkbox';cb.checked=!!Number(values[key]??fallback);labelNode.append(cb,document.createTextNode(' '+label));section.append(labelNode);fields[key]=cb;}
  const note=document.createElement('p');note.textContent='Default statuses apply only to episodes first discovered during a metadata refresh. Existing episode statuses are preserved.';section.append(note);host.append(section);
  return ()=>Object.fromEntries(Object.entries(fields).map(([k,e])=>[k,e.type==='checkbox'?e.checked:e.value]));
};
window.editShowPreferences=async function(id,name){
  const responses=await Promise.all([fetch('/api/shows/'+id+'?fast=1'),fetch('/api/quality-profiles')]);
  if(responses.some(r=>!r.ok))throw new Error('Could not load show preferences');
  const [show,profiles]=await Promise.all(responses.map(r=>r.json()));
  const dialog=document.createElement('dialog');dialog.className='destination-dialog';const form=document.createElement('form');const heading=document.createElement('h2');heading.textContent='Edit '+name;form.append(heading);dialog.append(form);
  const read=buildShowPreferences(form,show.show,profiles.results||[]);const error=document.createElement('p');error.setAttribute('role','alert');form.append(error);
  const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel';cancel.onclick=()=>{dialog.close();dialog.remove();};
  const save=document.createElement('button');save.type='submit';save.className='blue';save.textContent='Save Show Settings';const actions=document.createElement('div');actions.className='toolbar preference-actions';actions.append(cancel,save);form.append(actions);
  form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{const r=await fetch('/api/shows/'+id+'/options',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(read())}),d=await r.json();if(!r.ok)throw new Error(d.error||'Save failed');dialog.close();dialog.remove();location.reload();}catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};
  dialog.oncancel=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
};

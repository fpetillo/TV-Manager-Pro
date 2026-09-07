window.chooseShowDestination=async function(name,saveLabel='Add Show',currentLocation=null){
  const r=await fetch('/api/library/destinations'),d=await r.json();
  if(!r.ok)throw new Error(d.error||'Could not load library folders');
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');dialog.className='destination-dialog';
    dialog.innerHTML='<form><h2>Choose library folder</h2><p class="destination-name"></p><label class="field">Library root<select required></select></label><label class="field">Show folder name<input required></label><p>Episodes will be stored in:</p><p class="path-box destination-preview" role="status"></p><p class="destination-error" role="alert"></p><p>Season subfolders will be enabled. The folder is created when files are processed.</p><div class="toolbar"><button type="button" class="secondary">Cancel</button><button type="submit" class="blue" disabled></button></div></form>';
    const select=dialog.querySelector('select'),input=dialog.querySelector('input'),submit=dialog.querySelector('[type=submit]'),error=dialog.querySelector('.destination-error'),preview=dialog.querySelector('.destination-preview');
    dialog.querySelector('.destination-name').textContent=name;submit.textContent=saveLabel;
    for(const root of d.roots||[]){const o=document.createElement('option');o.value=root;o.textContent=root;select.append(o);}
    select.value=d.default||'';input.value=name.replace(/[<>:"/\\|?*\x00-\x1f]/g,' ').trim().replace(/[. ]+$/,'');
    if(currentLocation!==null){
      for(const paragraph of dialog.querySelectorAll('p'))if(paragraph.textContent.startsWith('Season subfolders'))paragraph.textContent='The existing season-folder setting is preserved.';
      const current=document.createElement('p');current.textContent='Current folder: '+(currentLocation||'Not configured');dialog.querySelector('h2').after(current);
      const norm=p=>p.replaceAll('\\','/').replace(/\/$/,'');
      for(const root of d.roots||[]){const prefix=norm(root)+'/';if(norm(currentLocation).toLowerCase().startsWith(prefix.toLowerCase())){const child=norm(currentLocation).slice(prefix.length);if(child&&!child.includes('/')){select.value=root;input.value=child;break;}}}
      const option=document.createElement('label');option.className='field';option.innerHTML='<span><input type="checkbox" id="rebaseEpisodePaths"> Update stored episode paths too (files have already been moved)</span>';dialog.querySelector('.toolbar').before(option);
      const note=document.createElement('p');note.textContent='Saving changes the destination for future processing. Existing files are not moved. Select the option above only if files already exist under the new folder; paths outside the old show folder stay unchanged.';option.after(note);
    }
    let version=0,approved=null;
    async function update(){const turn=++version;submit.disabled=true;approved=null;error.textContent='';preview.textContent='';
      if(!select.value){error.textContent='No library roots configured. Add root_dirs under General in Settings, then try again.';return;}
      const body={name,library_root:select.value,folder_name:input.value};
      try{const rr=await fetch('/api/library/destination-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),dd=await rr.json();if(turn!==version)return;if(!rr.ok)throw new Error(dd.error);preview.textContent=dd.location;approved=body;submit.disabled=false;}catch(e){if(turn===version)error.textContent=e.message;}
    }
    input.oninput=update;select.onchange=update;
    const finish=value=>{version++;dialog.close();dialog.remove();resolve(value);};
    dialog.querySelector('[type=button]').onclick=()=>finish(null);dialog.oncancel=e=>{e.preventDefault();finish(null);};
    dialog.querySelector('form').onsubmit=e=>{e.preventDefault();if(approved)finish({...approved,...(currentLocation!==null?{previous_location:currentLocation,update_episode_paths:dialog.querySelector("#rebaseEpisodePaths").checked}:{})});};
    document.body.append(dialog);dialog.showModal();update();
    const manage=document.createElement('a');manage.href='/library-storage';manage.textContent='Manage library locations';dialog.querySelector('.toolbar').before(manage);
    const storage=document.createElement('div');dialog.querySelector('.toolbar').before(storage);
    loadLibraryStorage(storage,rows=>{for(const option of select.options){const row=rows.find(x=>x.root===option.value);option.textContent=option.value+(row?.status==='ready'?' — '+storageSize(row.free)+' free':row?.status==='unavailable'?' — unavailable':' — checking space');}});
  });
};

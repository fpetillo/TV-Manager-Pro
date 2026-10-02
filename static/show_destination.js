window.chooseShowDestination=async function(name,saveLabel='Add Show',currentLocation=null,metadataProvider='tmdb',repair=null){
  const r=await fetch('/api/library/destinations'),d=await r.json();
  if(!r.ok)throw new Error(d.error||'Could not load library folders');
  let profiles=[],defaults={};
  if(currentLocation===null){
    if(typeof window.buildShowPreferences!=='function')await new Promise((resolve,reject)=>{const version=new URL(document.querySelector('script[src*="/static/show_destination.js"]')?.src||location.href).searchParams.get('v')||Date.now();const script=document.createElement('script');script.src='/static/show_preferences.js?v='+encodeURIComponent(version);script.onload=resolve;script.onerror=()=>reject(new Error('Show preferences could not load'));document.head.append(script);});
    const response=await fetch('/api/quality-profiles');if(!response.ok)throw new Error('Quality profiles could not load');profiles=(await response.json()).results||[];const dr=await fetch('/api/shows/defaults');if(!dr.ok)throw new Error('Show defaults could not load');defaults=(await dr.json()).preferences||{};
  }
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');dialog.className='destination-dialog'+(repair?' folder-repair-dialog':'');
    dialog.innerHTML='<form><h2>Choose library folder</h2><p class="destination-name"></p><label class="field">Library root<select required></select></label><label class="field">Show folder name<input required></label><p>Episodes will be stored in:</p><p class="path-box destination-preview" role="status"></p><p class="destination-error" role="alert"></p><p>Season subfolders follow the preference below. The folder is created when files are processed.</p><div class="toolbar"><button type="button" class="secondary">Cancel</button><button type="submit" class="blue" disabled></button></div></form>';
    const select=dialog.querySelector('select'),input=dialog.querySelector('input'),submit=dialog.querySelector('[type=submit]'),error=dialog.querySelector('.destination-error'),preview=dialog.querySelector('.destination-preview');
    dialog.querySelector('.destination-name').textContent=name;submit.textContent=saveLabel;
    dialog.querySelector('.toolbar').classList.add('preference-actions');
    let createDirectory=null,advanced=null;
    if(repair){
      dialog.setAttribute('aria-label','Correct show library folder');dialog.querySelector('h2').textContent='Choose folder for '+name;dialog.querySelector('.destination-name').hidden=true;
      const message=document.createElement('p');message.className='notice';message.textContent=repair.error;dialog.querySelector('h2').after(message);
      const label=document.createElement('label');label.className='preference-switch';createDirectory=document.createElement('input');createDirectory.type='checkbox';createDirectory.checked=true;label.append(createDirectory,document.createTextNode(' Create the show folder if it is missing'));dialog.querySelector('.toolbar').before(label);
      advanced=document.createElement('details');const summary=document.createElement('summary');summary.textContent='More folder options';advanced.append(summary);dialog.querySelector('.toolbar').before(advanced);
    }
    for(const root of d.roots||[]){const o=document.createElement('option');o.value=root;o.textContent=root;select.append(o);}
    select.value=d.default||'';input.value=name.replace(/[<>:"/\\|?*\x00-\x1f]/g,' ').trim().replace(/[. ]+$/,'');
    if(currentLocation!==null){
      for(const paragraph of dialog.querySelectorAll('p'))if(paragraph.textContent.startsWith('Season subfolders'))paragraph.textContent='The existing season-folder setting is preserved.';
      const current=document.createElement('p');current.textContent='Current folder: '+(currentLocation||'Not configured');dialog.querySelector('h2').after(current);
      const norm=p=>p.replaceAll('\\','/').replace(/\/$/,'');
      for(const root of d.roots||[]){const prefix=norm(root)+'/';if(norm(currentLocation).toLowerCase().startsWith(prefix.toLowerCase())){const child=norm(currentLocation).slice(prefix.length);if(child&&!child.includes('/')){select.value=root;input.value=child;break;}}}
      const option=document.createElement('label');option.className='field';option.innerHTML='<span><input type="checkbox" id="rebaseEpisodePaths"> Update stored episode paths too (files have already been moved)</span>';dialog.querySelector('.toolbar').before(option);
      const note=document.createElement('p');note.textContent='Saving changes the destination for future processing. Existing files are not moved. Select the option above only if files already exist under the new folder; paths outside the old show folder stay unchanged.';option.after(note);
      if(advanced){advanced.append(option,note);for(const paragraph of dialog.querySelectorAll('p'))if(paragraph.textContent==='The existing season-folder setting is preserved.')paragraph.hidden=true;}
    }
    let order=null;
    if(currentLocation===null&&metadataProvider==='tvdb'){const label=document.createElement('label');label.className='field';label.textContent='TVDB episode order';order=document.createElement('select');for(const [value,text] of [['official','Aired order'],['dvd','DVD order']]){const option=document.createElement('option');option.value=value;option.textContent=text;order.append(option);}label.append(order);dialog.querySelector('.toolbar').before(label);}
    let readPreferences=()=>({});
    if(currentLocation===null){const host=document.createElement('div');dialog.querySelector('.toolbar').before(host);readPreferences=buildShowPreferences(host,defaults,profiles);}
    let version=0,approved=null;
    async function update(){const turn=++version;submit.disabled=true;approved=null;error.textContent='';preview.textContent='';
      if(!select.value){error.textContent='No library roots configured. Open Library Locations to add a root, then try again.';return;}
      const body={name,library_root:select.value,folder_name:input.value};
      try{const rr=await fetch('/api/library/destination-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),dd=await rr.json();if(turn!==version)return;if(!rr.ok)throw new Error(dd.error);preview.textContent=dd.location;approved=body;submit.disabled=false;}catch(e){if(turn===version)error.textContent=e.message;}
    }
    input.oninput=update;select.onchange=update;
    const finish=value=>{version++;dialog.close();dialog.remove();resolve(value);};
    dialog.querySelector('[type=button]').onclick=()=>finish(null);dialog.oncancel=e=>{e.preventDefault();finish(null);};
    dialog.querySelector('form').onsubmit=e=>{e.preventDefault();if(approved)finish({...approved,...readPreferences(),...(order?{episode_order:order.value}:{}),...(repair?{create_directory:createDirectory.checked}:{}),...(currentLocation!==null?{previous_location:currentLocation,update_episode_paths:dialog.querySelector("#rebaseEpisodePaths").checked}:{})});};
    document.body.append(dialog);dialog.showModal();update();
    const manage=document.createElement('a');manage.href='/library-storage';manage.textContent='Manage library locations';dialog.querySelector('.toolbar').before(manage);
    if(repair){
      const label=document.createElement('label');label.className='field';label.textContent='Add another library root';const path=document.createElement('input');path.placeholder='Existing folder on this server or network share';label.append(path);
      const add=document.createElement('button');add.type='button';add.className='secondary';add.textContent='Add Library Root';label.append(add);advanced.append(label,manage);
      add.onclick=async()=>{add.disabled=true;try{const rr=await fetch('/api/library/locations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'add',new_path:path.value})}),dd=await rr.json();if(!rr.ok)throw new Error(dd.error);const fresh=dd.results||[];select.replaceChildren();for(const root of fresh){const option=document.createElement('option');option.value=root.path;option.textContent=root.path;select.append(option);}select.value=fresh[fresh.length-1].path;path.value='';await update();}catch(e){error.textContent=e.message;}finally{add.disabled=false;}};
    }
    const storage=document.createElement('div');dialog.querySelector('.toolbar').before(storage);
    if(advanced)advanced.append(storage);
    loadLibraryStorage(storage,rows=>{for(const option of select.options){const row=rows.find(x=>x.root===option.value);option.textContent=option.value+(row?.status==='ready'?' — '+storageSize(row.free)+' free':row?.status==='unavailable'?' — unavailable':' — checking space');}});
  });
};

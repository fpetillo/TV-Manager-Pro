window.previewLibraryRename=async function(id){
  const response=await fetch('/api/shows/'+id+'/rename-preview',{method:'POST'}),data=await response.json();
  if(!response.ok)throw new Error(data.error||'Preview failed');
  const dialog=document.createElement('dialog');dialog.className='destination-dialog';const title=document.createElement('h2');title.textContent='Preview Rename: '+data.plan.show_name;dialog.append(title);
  const note=document.createElement('p');note.textContent='Review the files below. Confirming renames selected files inside this show folder and updates episode locations. Existing destinations are never overwritten.';dialog.append(note);
  const choices=[];
  data.plan.items.forEach((item,index)=>{const row=document.createElement('section');row.className='rename-item';const label=document.createElement('label');label.className='preference-switch';const cb=document.createElement('input');cb.type='checkbox';cb.disabled=!!item.blocked||!item.moves.length;cb.checked=!cb.disabled;label.append(cb,document.createTextNode(item.blocked?'Blocked':item.moves.length?'Rename':'Already named'));row.append(label);
    const path=document.createElement('p');path.className='path-box';path.textContent=item.source;row.append(path);
    for(const move of item.moves){const line=document.createElement('p');line.className='path-box';line.textContent=move.source+' → '+move.destination;row.append(line);}
    if(item.blocked){const error=document.createElement('p');error.textContent=item.blocked;row.append(error);}dialog.append(row);choices.push({cb,index});
  });
  if(!choices.length){const empty=document.createElement('p');empty.textContent='No episode files are recorded. Scan Existing Files first.';dialog.append(empty);}
  const status=document.createElement('p');status.setAttribute('role','status');dialog.append(status);const actions=document.createElement('div');actions.className='toolbar preference-actions';const cancel=document.createElement('button');cancel.textContent='Cancel';cancel.onclick=()=>{dialog.close();dialog.remove();};const apply=document.createElement('button');apply.className='blue';actions.append(cancel,apply);dialog.append(actions);
  function count(){const n=choices.filter(x=>x.cb.checked).length;apply.textContent='Confirm & Rename '+n+' Files';apply.disabled=!n;}
  choices.forEach(x=>x.cb.onchange=count);count();
  apply.onclick=async()=>{apply.disabled=true;cancel.disabled=true;dialog.oncancel=e=>e.preventDefault();status.textContent='Renaming selected files…';try{const r=await fetch('/api/shows/'+id+'/rename-apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:data.token,selected:choices.filter(x=>x.cb.checked).map(x=>x.index)})}),result=await r.json();if(!r.ok)throw new Error(result.error||'Rename failed');status.textContent='Renamed '+result.renamed+' episode files ('+result.files+' files including associated files).';apply.remove();cancel.textContent='Close';cancel.onclick=()=>location.reload();}catch(ex){status.textContent=ex.message+' Close and preview again before retrying.';apply.remove();}finally{cancel.disabled=false;dialog.oncancel=()=>dialog.remove();}};
  dialog.oncancel=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
};

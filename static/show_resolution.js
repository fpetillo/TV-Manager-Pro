/* Shared selection and resolution editing for both library views. */
window.createShowResolutionControls = function(host, onSaved) {
  const selected = new Set();
  const panel = document.createElement('section');panel.className='panel resolution-toolbar';
  const heading=document.createElement('h2');heading.textContent='Download resolution';panel.append(heading);
  const note=document.createElement('p');note.textContent='Choose a resolution for selected shows, a saved group, all shows, or future shows.';panel.append(note);
  const bar=document.createElement('div');bar.className='toolbar wrap';panel.append(bar);
  const status=document.createElement('span');status.setAttribute('role','status');
  const message=document.createElement('p');message.setAttribute('role','status');
  function button(text, handler) {const b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=text;b.onclick=handler;bar.append(b);return b;}
  const edit=button('Set Resolution', open);edit.className='blue';
  button('Select Visible',()=>{document.querySelectorAll('.resolution-show-check').forEach(c=>selected.add(Number(c.value)));sync();});
  button('Clear Selection',()=>{selected.clear();sync();});
  bar.append(status);panel.append(message);host.append(panel);
  function sync(){document.querySelectorAll('.resolution-show-check').forEach(c=>c.checked=selected.has(Number(c.value)));status.textContent=`${selected.size} selected (kept across pages and filters)`;}
  function checkbox(id,name){const c=document.createElement('input');c.type='checkbox';c.className='resolution-show-check';c.value=id;c.checked=selected.has(Number(id));c.setAttribute('aria-label','Select '+name+' for resolution');c.onchange=()=>{c.checked?selected.add(Number(id)):selected.delete(Number(id));sync();};return c;}
  async function request(url,body){const response=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{cache:'no-store'});let result;try{result=await response.json();}catch{throw new Error('Could not load resolution controls. Restart TV Manager after updating, then refresh.');}if(!response.ok)throw new Error(result.error||'Resolution request failed');return result;}
  async function open(){
    edit.disabled=true;message.textContent='';
    try{
      const options=await request('/api/shows/resolution/options');
      const dialog=document.createElement('dialog');dialog.className='destination-dialog resolution-dialog';dialog.setAttribute('aria-labelledby','resolution-heading');
      const form=document.createElement('form');dialog.append(form);
      const title=document.createElement('h2');title.id='resolution-heading';title.textContent='Set download resolution';form.append(title);
      const current=document.createElement('p');current.textContent='Current default for new shows: '+options.choices[options.default];form.append(current);
      function select(label,rows){const wrap=document.createElement('label');wrap.className='field';wrap.textContent=label;const node=document.createElement('select');for(const [value,text] of rows){const o=document.createElement('option');o.value=value;o.textContent=text;node.append(o);}wrap.append(node);form.append(wrap);return node;}
      const scope=select('Apply to',[['selected',`Selected shows (${selected.size})`],['group','A saved show group'],['all',`All shows (${options.total})`],['defaults','New shows only']]);
      scope.value=selected.size?'selected':'all';
      const group=select('Show group',[['','Choose a group'],...options.groups.map(g=>[g.id,`${g.name} (${g.show_count} shows)`])]);
      const resolution=select('Resolution',['','sd','720p','1080p','2160p'].map(key=>[key,options.choices[key]]));resolution.value='1080p';
      const defaultsLabel=document.createElement('label');defaultsLabel.className='preference-switch';const defaults=document.createElement('input');defaults.type='checkbox';defaultsLabel.append(defaults,document.createTextNode(' Also use this as the default for newly added shows'));form.append(defaultsLabel);
      const help=document.createElement('p');help.textContent='A fixed resolution replaces the profile’s resolution range; other quality rules remain. This changes future searches and upgrade planning. It does not start downloads, convert files, or change episode statuses.';form.append(help);
      const review=document.createElement('div');review.className='notice';review.hidden=true;review.setAttribute('role','status');form.append(review);
      const error=document.createElement('p');error.setAttribute('role','alert');form.append(error);
      const actions=document.createElement('div');actions.className='toolbar wrap preference-actions';form.append(actions);
      const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel';cancel.onclick=()=>{dialog.close();dialog.remove();};actions.append(cancel);
      const submit=document.createElement('button');submit.type='submit';submit.className='blue';submit.textContent='Review Change';actions.append(submit);
      let token=null;
      function changed(){token=null;review.hidden=true;error.textContent='';submit.textContent='Review Change';group.parentElement.hidden=scope.value!=='group';defaultsLabel.hidden=scope.value==='defaults';}
      form.onchange=changed;changed();
      form.onsubmit=async event=>{
        event.preventDefault();submit.disabled=true;cancel.disabled=true;error.textContent='';
        // Freeze the reviewed choices while a request is in flight.
        [scope,group,resolution,defaults].forEach(x=>x.disabled=true);
        try{
          if(!token){
            const result=await request('/api/shows/resolution/preview',{scope:scope.value,show_ids:[...selected],group_id:Number(group.value),resolution:resolution.value,make_default:defaults.checked||scope.value==='defaults'});
            token=result.token;const p=result.plan;
            review.textContent=`${p.count} existing shows in scope; ${p.changed} will change to ${p.label}. ${p.selection.make_default?'New shows will also use '+p.label+'.':''}${p.sample.length?' Includes: '+p.sample.join(', ')+(p.count>p.sample.length?'…':'')+'.':''}`;
            review.hidden=false;submit.textContent=p.selection.scope==='defaults'?'Confirm New-Show Default':`Confirm for ${p.count} Shows`;
          }else{
            const result=await request('/api/shows/resolution/apply',{token});
            message.textContent=`Saved ${result.label}: ${result.changed} of ${result.count} existing shows changed.${result.default_saved?' New-show default saved.':''}`;
            dialog.close();dialog.remove();await onSaved();
          }
        }catch(ex){error.textContent=ex.message;token=null;submit.textContent='Review Change';review.hidden=true;}
        finally{submit.disabled=false;cancel.disabled=false;[scope,group,resolution,defaults].forEach(x=>x.disabled=false);}
      };
      dialog.oncancel=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
    }catch(ex){message.textContent=ex.message;}finally{edit.disabled=false;}
  }
  sync();return {checkbox,sync,selected};
};

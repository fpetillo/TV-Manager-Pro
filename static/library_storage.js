window.storageSize=value=>Number.isFinite(value)?(value/1024**(value>=1024**4?4:value>=1024**3?3:2)).toLocaleString(undefined,{maximumFractionDigits:1})+' '+(value>=1024**4?'TB':value>=1024**3?'GB':'MB'):'Unavailable';
window.loadLibraryStorage=async function(target,onRows){
  let count=0;
  while(target.isConnected&&count++<15){
    try{const r=await fetch('/api/library/storage',{signal:AbortSignal.timeout(5000)});if(!r.ok)throw new Error('Restart TV Manager to enable storage checks (HTTP '+r.status+').');const d=await r.json();
      const rows=d.results||[];
      target.replaceChildren();
      if(!rows.length)target.textContent='No TV library paths configured. Add library roots in Settings.';
      for(const row of rows){const card=document.createElement('div');card.className='service-card';const title=document.createElement('strong');title.textContent=row.root;title.style.overflowWrap='anywhere';card.append(title);const text=document.createElement('p');text.textContent=row.status==='ready'?storageSize(row.free)+' free of '+storageSize(row.total)+' · '+row.percent_used+'% used':row.status==='unavailable'?'Unavailable — '+row.message:row.status==='slow'?row.message:row.status==='queued'?'Waiting for a storage check…':'Checking space…';card.append(text);if(row.status==='ready'){const meter=document.createElement('progress');meter.max=100;meter.value=row.percent_used;meter.setAttribute('aria-label','Disk space used');card.append(meter);}if(row.checked_at){const when=document.createElement('small');when.textContent='Checked '+new Date(row.checked_at).toLocaleTimeString();card.append(when);}target.append(card);}
      if(onRows)onRows(rows);
      if(!rows.some(x=>['checking','queued','slow'].includes(x.status)))return;
      await new Promise(r=>setTimeout(r,2000));
    }catch(e){target.textContent='Disk space could not load: '+e.message;return;}
  }
};
window.addEventListener('DOMContentLoaded',()=>{const target=document.getElementById('libraryStorage');if(target){const run=async()=>{const b=document.getElementById('refreshStorage');b.disabled=true;try{await loadLibraryStorage(target);}finally{b.disabled=false;}};document.getElementById('refreshStorage').onclick=run;run();}});

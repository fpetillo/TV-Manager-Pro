/* v18.25.0 — Trash page: what's in trash, restore, empty, settings. */
(()=>{
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
  const num=n=>Number(n||0).toLocaleString();
  const size=b=>{b=Number(b||0);const u=["bytes","KB","MB","GB","TB"];let i=0;while(b>=1024&&i<u.length-1){b/=1024;i++}return (i?b.toFixed(1):b)+" "+u[i]};
  let state=null;

  function say(t,kind){const m=$("trashMessage");m.textContent=t||"";m.className="message"+(kind?" "+kind:"");}
  async function api(path,body){
    const r=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.error||("HTTP "+r.status));
    return d;
  }

  function render(d){
    state=d;
    const tiles=[["Total in trash",d.total_count,d.total_bytes,""]].concat(["upgrades","rollback_replaced","duplicates","retention"].filter(k=>d.categories[k]).map(k=>d.categories[k]).map(c=>[c.label,c.count,c.bytes,c.oldest?("oldest "+c.oldest.slice(0,10)):""]));
    $("trashCounts").innerHTML=tiles.map(([label,count,bytes,hint])=>`<div class="dash-card"><span>${esc(label)}</span><strong>${size(bytes)}</strong><small>${num(count)} file(s)${hint?" · "+esc(hint):""}</small></div>`).join("");
    const L=d.legacy||{};
    $("trashLegacy").hidden=!L.count;
    $("trashLegacy").innerHTML=L.count?`<strong>${num(L.count)} older file(s), ${size(L.bytes)}</strong>, are in the old trash folder on this server's own drive (${esc(L.path)}), from before trash moved to the media share. <button id="trashEmptyLegacy" class="secondary">Empty old server trash</button>`:"";
    const f=$("trashSettings");
    f.elements.trash_auto_empty_days.value=d.settings.trash_auto_empty_days;
    f.elements.trash_folder.value=d.settings.trash_folder||"";
    $("trashWhere").textContent=d.locations&&d.locations.length?("Trash is kept in: "+d.locations.join(" · ")):"Set your library folders in Library Locations so trash can be kept next to them on the share.";
    const rows=d.items||[];
    $("trashList").innerHTML=rows.length?`<table class="compact-table"><tr><th><input type="checkbox" id="trashAll" aria-label="Select all"></th><th>File</th><th>Episode</th><th>Why</th><th>Size</th><th>Moved</th><th></th></tr>${rows.map(r=>`<tr><td><input type="checkbox" class="trash-check" value="${r.id}"></td><td>${esc(r.original_path.split(/[\\/]/).pop())}<div class="trash-path">${esc(r.original_path)}</div></td><td>${r.show_name?esc(r.show_name)+(r.season!=null?` S${String(r.season).padStart(2,"0")}E${String(r.episode).padStart(2,"0")}`:""):"—"}</td><td>${esc(r.reason||"")}</td><td>${size(r.size)}</td><td>${esc(String(r.created_at||"").slice(0,16))}</td><td><button class="secondary" data-restore="${r.id}">Restore</button></td></tr>`).join("")}</table>`:'<p class="muted">Trash is empty.</p>';
    $("trashEmptySelected").disabled=true;
  }

  async function load(){
    try{render(await api("/api/trash?category="+encodeURIComponent($("trashCategory").value)));}
    catch(err){say("Could not load trash: "+err.message,"error");}
  }

  async function empty(body,question){
    if(!confirm(question))return;
    try{
      const d=await api("/api/trash/empty",body);
      const errs=d.errors||[];
      say(`Deleted ${num(d.deleted)} file(s), freed ${size(d.bytes)}.${d.missing?` ${num(d.missing)} were already gone.`:""}${errs.length?" Some files could not be deleted: "+errs.join("; "):""}`,errs.length?"error":"success");
      await load();
    }catch(err){say(err.message,"error");}
  }

  $("trashEmptyAll").onclick=()=>empty({mode:"all",include_legacy:true},`Delete everything in trash for good (${size((state?.total_bytes||0)+(state?.legacy?.bytes||0))})? Upgrades in trash can no longer be rolled back.`);
  $("trashEmptyOlder").onclick=()=>{const days=Number($("trashDays").value);if(!(days>=0)){say("Enter a number of days.","error");return}empty({mode:"older",days,include_legacy:true},`Delete trashed files older than ${days} day(s) for good?`)};
  $("trashEmptySelected").onclick=()=>{const ids=[...document.querySelectorAll(".trash-check:checked")].map(x=>Number(x.value));empty({mode:"selected",ids},`Delete ${ids.length} selected file(s) for good?`)};
  $("trashCategory").onchange=load;

  document.addEventListener("change",ev=>{
    if(ev.target.id==="trashAll")document.querySelectorAll(".trash-check").forEach(x=>x.checked=ev.target.checked);
    if(ev.target.id==="trashAll"||ev.target.classList.contains("trash-check"))$("trashEmptySelected").disabled=!document.querySelector(".trash-check:checked");
  });
  document.addEventListener("click",async ev=>{
    if(ev.target.closest("#trashEmptyLegacy")){empty({mode:"legacy"},`Delete the ${num(state.legacy.count)} older file(s) in ${state.legacy.path} for good?`);return}
    const b=ev.target.closest("[data-restore]");
    if(!b)return;
    b.disabled=true;
    try{const d=await api("/api/trash/restore/"+b.dataset.restore,{});say("Restored to "+d.restored,"success");await load();}
    catch(err){say(err.message,"error");b.disabled=false;}
  });
  $("trashSettings").addEventListener("submit",async ev=>{
    ev.preventDefault();
    try{render(Object.assign(await api("/api/trash/settings",{trash_auto_empty_days:ev.target.elements.trash_auto_empty_days.value,trash_folder:ev.target.elements.trash_folder.value}),{items:state.items}));say("Settings saved.","success");}
    catch(err){say(err.message,"error");}
  });
  load();
})();

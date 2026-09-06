
const showList=document.getElementById("showList");
const summary=document.getElementById("summary");
const detail=document.getElementById("detailPanel");
const search=document.getElementById("showSearch");
const statusFilter=document.getElementById("statusFilter");
let currentShowId=null;
let searchTimer=null;

function esc(v){return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}

async function loadDashboard(){
  const r=await fetch("/api/dashboard"),d=await r.json();
  dashShows.textContent=d.shows; dashEpisodes.textContent=d.episodes;
  dashDownloaded.textContent=d.downloaded; dashWanted.textContent=d.wanted;
}

async function loadShows(){
  const p=new URLSearchParams();
  if(search.value.trim())p.set("q",search.value.trim());
  if(statusFilter.value)p.set("status",statusFilter.value);
  if(groupFilter.value)p.set("group_id",groupFilter.value);
  const r=await fetch("/api/shows?"+p),d=await r.json();
  summary.textContent=`${d.results.length} show${d.results.length===1?"":"s"}`;
  showList.innerHTML="";
  if(!d.results.length){
    showList.innerHTML='<div class="empty-list">No matching shows.</div>';
    return;
  }
  for(const s of d.results){
    const item=document.createElement("button");
    item.className="show-list-item"+(s.id===currentShowId?" active":"");
    item.innerHTML=`
      <div class="show-list-poster">${s.poster?`<img src="${esc(s.poster)}" alt="">`:`<div class="poster-fallback">TV</div>`}</div>
      <div class="show-list-copy">
        <strong>${esc(s.name)}</strong>
        <span>${s.season_count||0} season${s.season_count===1?"":"s"} • ${s.episode_count||0} episode${s.episode_count===1?"":"s"}</span>
        <span>${esc(s.status||"Unknown")}${s.network?" • "+esc(s.network):""}</span>
      </div>`;
    item.onclick=()=>openShow(s.id);
    showList.appendChild(item);
  }
}

async function openShow(id){
  currentShowId=id;
  await loadShows();
  detail.innerHTML='<div class="loading-box">Loading show…</div>';
  const [sr,er]=await Promise.all([fetch(`/api/shows/${id}`),fetch(`/api/shows/${id}/episodes`)]);
  const sd=await sr.json(),ed=await er.json(),s=sd.show;
  detail.innerHTML=`
    <div class="show-hero">
      <div class="hero-poster">${s.poster?`<img src="${esc(s.poster)}" alt="">`:`<div class="poster-fallback large">TV</div>`}</div>
      <div class="hero-copy">
        <p class="eyebrow">SHOW</p>
        <h2>${esc(s.name)}</h2>
        <div class="meta">${[s.network,s.genre,s.first_air_date?.slice(0,4),s.status].filter(Boolean).map(esc).join(" • ")}</div>
        <p>${esc(s.overview||"No overview available.")}</p>
        <div class="ids">
          <div class="id-box"><span class="id-label">IMDb</span><code>${esc(s.imdb_id||"—")}</code></div>
          <div class="id-box"><span class="id-label">TVDb</span><code>${esc(s.tvdb_id||"—")}</code></div>
          <div class="id-box"><span class="id-label">TMDb</span><code>${esc(s.tmdb_id||"—")}</code></div>
        </div>
        ${s.location?`<div class="path-box">${esc(s.location)}</div>`:""}
        <div class="actions show-actions">
          <button id="refreshMetadata" class="blue">Refresh Metadata</button>
          ${s.imdb_id?`<a class="btn secondary" target="_blank" href="https://www.imdb.com/title/${esc(s.imdb_id)}/">IMDb</a>`:""}
        </div>
        <div id="refreshMessage" class="message"></div>
      </div>
    </div>
    <div class="show-options-grid">
      <label><input id="optFavorite" type="checkbox" ${s.favorite?"checked":""}> Favorite</label>
      <label><input id="optPaused" type="checkbox" ${s.paused?"checked":""}> Paused</label>
      <label><input id="optSearch" type="checkbox" ${s.search_enabled!==0?"checked":""}> Search enabled</label>
      <label><input id="optMonitor" type="checkbox" ${s.monitor_new!==0?"checked":""}> Monitor new episodes</label>
      <label><input id="optSeasonFolders" type="checkbox" ${s.season_folders!==0?"checked":""}> Season folders</label>
      <div class="field"><label>Preferred words</label><input id="optPreferred" value="${esc(s.preferred_words||"")}"></div>
      <div class="field"><label>Required words</label><input id="optRequired" value="${esc(s.required_words||"")}"></div>
      <div class="field"><label>Ignored words</label><input id="optIgnored" value="${esc(s.ignored_words||"")}"></div><div class="field"><label>Quality profile</label><select id="optQuality"><option value="">Loading…</option></select></div><div class="field"><label>Retention policy</label><select id="optRetention"><option value="">None</option></select></div>
      <div class="field span2"><label>Tags</label><div id="tagChooser" class="tag-chooser"></div></div>
      <div class="actions"><button id="saveShowOptions" class="secondary">Save Show Options</button><button id="scanLibrary" class="secondary">Scan Existing Files</button><button id="writeMetadata" class="secondary">Write NFO / Artwork</button><button id="sceneMapping" class="secondary">Scene / Anime Mapping</button></div>
      <div id="showOptionMsg" class="message"></div>
    </div>
    <div class="season-header">
      <div><h3>Seasons</h3><p class="muted">Only open the season you want to inspect.</p></div>
      <div class="badge">${s.season_count||0} seasons • ${s.episode_count||0} episodes</div>
    </div>
    <div id="seasonList" class="season-list"></div>`;



  fetch("/api/quality-profiles").then(r=>r.json()).then(d=>{
    optQuality.innerHTML='<option value="">No profile</option>'+d.results.map(p=>`<option value="${p.id}" ${String(s.quality_profile_id||"")===String(p.id)?"selected":""}>${esc(p.name)}</option>`).join("");
  });
  fetch("/api/retention-policies").then(r=>r.json()).then(d=>{optRetention.innerHTML='<option value="">None</option>'+d.results.map(p=>`<option value="${p.id}" ${String(s.retention_policy_id||"")===String(p.id)?"selected":""}>${esc(p.name)}</option>`).join("")});
  Promise.all([fetch("/api/tags").then(r=>r.json()),fetch(`/api/shows/${id}/tags`).then(r=>r.json())]).then(([all,current])=>{const have=new Set(current.results.map(x=>x.id));tagChooser.innerHTML=all.results.map(t=>`<label class="tag-pill"><input type="checkbox" value="${t.id}" ${have.has(t.id)?"checked":""}>${esc(t.name)}</label>`).join("")||'<span class="muted">Create tags in Advanced.</span>'});
  document.getElementById("saveShowOptions").onclick=async()=>{
    const body={
      favorite:optFavorite.checked,paused:optPaused.checked,search_enabled:optSearch.checked,monitor_new:optMonitor.checked,
      season_folders:optSeasonFolders.checked,preferred_words:optPreferred.value,
      required_words:optRequired.value,ignored_words:optIgnored.value,quality_profile_id:optQuality.value?+optQuality.value:null,retention_policy_id:optRetention.value?+optRetention.value:null
    };
    const r=await fetch(`/api/shows/${id}/options`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(r.ok){const tag_ids=[...document.querySelectorAll("#tagChooser input:checked")].map(x=>+x.value);await fetch(`/api/shows/${id}/tags`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tag_ids})})}
    showOptionMsg.className=r.ok?"message success":"message error";
    showOptionMsg.textContent=r.ok?"Show options saved.":"Could not save show options.";
  };


  document.getElementById("sceneMapping").onclick=async()=>{
    let modal=document.getElementById("mappingModal");
    if(!modal){modal=document.createElement("div");modal.id="mappingModal";modal.className="search-modal";document.body.appendChild(modal)}
    modal.hidden=false;modal.innerHTML=`<div class="modal-card"><div class="modal-head"><h2>Scene / Anime Mapping — ${esc(s.name)}</h2><button class="close-x" onclick="mappingModal.hidden=true">Close</button></div><div id="mappingBody">Loading…</div></div>`;
    const r=await fetch(`/api/shows/${id}/scene-mappings`),d=await r.json();
    mappingBody.innerHTML=`<div class="form-grid compact-grid"><label>Season<input id="ms" type="number"></label><label>Episode<input id="me" type="number"></label><label>Scene season<input id="mss" type="number"></label><label>Scene episode<input id="mse" type="number"></label><label>Absolute #<input id="ma" type="number"></label><label>Alias<input id="mal"></label></div><button id="addMapping" class="blue">Add Mapping / Alias</button><div class="mapping-list">${d.results.map(x=>`<div class="result-card"><strong>${x.alias?esc(x.alias)+" • ":""}${x.season!=null?`S${x.season}E${x.episode}`:""}${x.scene_season!=null?` → Scene S${x.scene_season}E${x.scene_episode}`:""}${x.absolute_number!=null?` • Absolute ${x.absolute_number}`:""}</strong></div>`).join("")||'<p class="muted">No mappings yet.</p>'}</div>`;
    addMapping.onclick=async()=>{await fetch(`/api/shows/${id}/scene-mappings`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({season:ms.value?+ms.value:null,episode:me.value?+me.value:null,scene_season:mss.value?+mss.value:null,scene_episode:mse.value?+mse.value:null,absolute_number:ma.value?+ma.value:null,alias:mal.value})});sceneMapping.click()}
  };

  document.getElementById("writeMetadata").onclick=async()=>{
    writeMetadata.disabled=true;showOptionMsg.className="message";showOptionMsg.textContent="Writing NFO files and artwork…";
    const r=await fetch(`/api/shows/${id}/write-metadata`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({artwork:true,episode_nfo:true})}),d=await r.json();
    showOptionMsg.className=r.ok?"message success":"message error";
    showOptionMsg.textContent=r.ok?`Metadata complete: ${d.nfo_files} NFO files${d.artwork_saved?" plus poster artwork":""}.`:(d.error||"Metadata generation failed");
    writeMetadata.disabled=false;
  };

  document.getElementById("scanLibrary").onclick=async()=>{
    scanLibrary.disabled=true;showOptionMsg.className="message";showOptionMsg.textContent="Scanning the configured show folder…";
    const r=await fetch(`/api/shows/${id}/scan-library`,{method:"POST"}),d=await r.json();
    showOptionMsg.className=r.ok?"message success":"message error";
    showOptionMsg.textContent=r.ok?`Scanned ${d.files} files and matched ${d.matched} episodes.`:(d.error||"Library scan failed");
    scanLibrary.disabled=false;
    if(r.ok){await loadDashboard();setTimeout(()=>openShow(id),500)}
  };

  document.getElementById("refreshMetadata").onclick=async()=>{
    const b=document.getElementById("refreshMetadata"),m=document.getElementById("refreshMessage");
    b.disabled=true;m.className="message";m.textContent="Refreshing show, season and episode metadata…";
    const r=await fetch(`/api/shows/${id}/refresh`,{method:"POST"}),d=await r.json();
    if(!r.ok){m.className="message error";m.textContent=d.error||"Refresh failed";b.disabled=false;return}
    m.className="message success";m.textContent=d.message;
    await loadDashboard();
    setTimeout(()=>openShow(id),500);
  };

  const seasonList=document.getElementById("seasonList");
  if(!ed.seasons.length){
    seasonList.innerHTML='<div class="empty-state compact"><p>No episodes are currently stored for this show.</p></div>';
    return;
  }
  for(const season of ed.seasons){
    const block=document.createElement("section");
    block.className="season-block";
    block.innerHTML=`
      <div class="season-bar">
        <button class="season-toggle">
          <div>
            <strong>${season.season===0?"Specials":"Season "+season.season}</strong>
            <span>${season.episode_count} episodes • ${season.with_files||0} with files <span class="pack-hint" data-season="${season.season}"></span></span>
          </div>
          <span class="chev">＋</span>
        </button>
        <div class="season-bulk">
          <select class="season-status"><option value="">Set status…</option><option>Wanted</option><option>Skipped</option><option>Ignored</option><option>Archived</option></select>
          <button class="secondary action-btn apply-season">Apply</button>
        </div>
      </div>
      <div class="season-episodes" hidden></div>`;
    const toggle=block.querySelector(".season-toggle");
    const body=block.querySelector(".season-episodes");
    block.querySelector(".apply-season").onclick=async(e)=>{
      e.stopPropagation();
      const status=block.querySelector(".season-status").value;
      if(!status)return;
      await fetch(`/api/shows/${id}/seasons/${season.season}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status})});
      body.dataset.loaded="";body.hidden=true;block.querySelector(".chev").textContent="＋";
    };
    toggle.onclick=async()=>{
      if(!body.hidden){body.hidden=true;block.querySelector(".chev").textContent="＋";return}
      block.querySelector(".chev").textContent="−";
      body.hidden=false;
      if(body.dataset.loaded)return;
      body.innerHTML='<div class="loading-box">Loading season…</div>';
      const r=await fetch(`/api/shows/${id}/episodes?season=${season.season}`),d=await r.json();
      body.dataset.loaded="1";
      body.innerHTML=d.episodes.length?`
        <div class="episode-table-wrap"><table class="episode-table">
          <thead><tr><th>Ep</th><th>Title</th><th>Air date</th><th>Status</th><th>File</th><th></th></tr></thead>
          <tbody>${d.episodes.map(e=>`
            <tr>
              <td>${e.episode}</td>
              <td>${esc(e.name||"")}</td>
              <td>${esc(e.airdate||"")}</td>
              <td><select class="ep-status" onchange="updateEpisode(${e.id},{status:this.value})">
                ${["Wanted","Snatched","Downloaded","Failed","Skipped","Ignored","Archived","Unaired"].map(st=>`<option ${String(e.status).toLowerCase()===st.toLowerCase()?"selected":""}>${st}</option>`).join("")}
              </select><label class="ep-monitor"><input type="checkbox" ${e.monitored!==0?"checked":""} onchange="updateEpisode(${e.id},{monitored:this.checked})"> monitor</label></td>
              <td class="file-cell">${e.location?esc(e.location):'<span class="missing-file">Missing</span>'}</td>
              <td><button class="action-btn secondary" onclick="searchEpisode(${e.id}, '${esc(s.name).replace(/'/g,"&#039;")}', ${e.season}, ${e.episode})">Search</button></td>
            </tr>`).join("")}</tbody>
        </table></div>`:'<p class="muted">No episodes in this season.</p>';
    };
    seasonList.appendChild(block);
    fetch(`/api/season-pack-plan/${id}/${season.season}`).then(r=>r.json()).then(p=>{const h=block.querySelector(".pack-hint");if(h&&p.season_pack_preferred){h.innerHTML=` • <button class="link-button" onclick="event.stopPropagation();searchSeasonPack(${id},${season.season})">Find season pack</button>`}});
  }
}

search.addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(loadShows,180)});
statusFilter.addEventListener("change",loadShows);
groupFilter.addEventListener("change",loadShows);
fetch("/api/groups").then(r=>r.json()).then(d=>{groupFilter.innerHTML='<option value="">All groups</option>'+d.results.map(g=>`<option value="${g.id}">${esc(g.name)} (${g.show_count})</option>`).join("")});
document.getElementById("clearSearch").onclick=()=>{search.value="";statusFilter.value="";groupFilter.value="";loadShows()};

loadDashboard();
loadShows();


window.searchEpisode=async function(eid,showName,season,episode){
  let modal=document.getElementById("searchModal");
  if(!modal){
    modal=document.createElement("div");modal.id="searchModal";modal.className="search-modal";
    modal.innerHTML=`<div class="modal-card"><div class="modal-head"><div><p class="eyebrow">MANUAL SEARCH</p><h2 id="modalTitle">Episode Search</h2></div><button class="close-x" onclick="document.getElementById('searchModal').hidden=true">Close</button></div><div id="modalBody"></div></div>`;
    document.body.appendChild(modal);
  }
  modal.hidden=false;
  document.getElementById("modalTitle").textContent=`${showName} S${String(season).padStart(2,"0")}E${String(episode).padStart(2,"0")}`;
  const body=document.getElementById("modalBody");
  body.innerHTML='<div class="loading-box">Searching configured providers…</div>';
  const r=await fetch(`/api/episodes/${eid}/search`,{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
  const d=await r.json();
  if(!r.ok){body.innerHTML=`<div class="message error">${esc(d.error||"Search failed")}</div>`;return}
  if(!d.results.length){body.innerHTML=`<div class="notice">No results. ${esc((d.errors||[]).join(" • "))}</div>`;return}
  body.innerHTML=d.results.map(x=>`<div class="result-card ${x.rejected_reason?"rejected":""}">
    <div class="result-top"><div class="result-title">${esc(x.title)}</div><div class="score">${Math.round(x.score)}</div></div>
    <div class="result-meta">${esc(x.provider)} • ${esc(x.quality)} • ${x.size?Math.round(x.size/1024/1024)+" MB":"size unknown"} ${x.rejected_reason?" • "+esc(x.rejected_reason):""}</div>
    ${(x.decision_reasons||[]).length?`<div class="decision-reasons">${x.decision_reasons.map(r=>`<span>${esc(r)}</span>`).join("")}</div>`:""}
    ${x.rejected_reason?"":`<div class="actions"><button class="blue action-btn" onclick="grabSearchResult(${x.id},this)">Send to Downloader</button></div>`}
  </div>`).join("");
}
window.grabSearchResult=async function(rid,btn){
  btn.disabled=true;btn.textContent="Sending…";
  const r=await fetch(`/api/search-results/${rid}/grab`,{method:"POST"}),d=await r.json();
  if(!r.ok){btn.disabled=false;btn.textContent="Send to Downloader";alert(d.error||"Unable to queue release");return}
  btn.textContent=`Queued in ${d.client}`;
  loadDashboard();
}

window.updateEpisode=async function(eid,body){
  const r=await fetch(`/api/episodes/${eid}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  if(!r.ok)alert("Could not update episode.");
  else loadDashboard();
}

const qp=new URLSearchParams(location.search);if(qp.get("show"))setTimeout(()=>openShow(+qp.get("show")),200);

window.markWatched=async eid=>{await fetch(`/api/episodes/${eid}/watched`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({percent:100,source:"manual"})})}
window.protectEpisode=async eid=>{await fetch(`/api/episodes/${eid}/lock`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({locked:true,reason:"Protected by user"})});alert("Episode protected.")}

window.searchSeasonPack=async(showId,season)=>{
  const r=await fetch(`/api/season-packs/${showId}/${season}/search`),d=await r.json();
  if(!r.ok)return alert(d.error||"Season pack search failed");
  if(!d.results.length)return alert("No suitable season packs found.");
  const best=d.results[0];
  const ok=confirm(`Best season pack:\n${best.title}\n${best.provider} • ${best.quality} • score ${Math.round(best.score)}\n\nSend this pack to the configured downloader?`);
  if(!ok)return;
  const g=await fetch(`/api/season-packs/grab/${best.id}`,{method:"POST"}),gd=await g.json();
  alert(g.ok?`Season pack queued in ${gd.client}.`:(gd.error||"Could not queue season pack"));
}

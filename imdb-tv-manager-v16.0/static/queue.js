const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
let data=[];
async function load(){const r=await fetch("/api/queue/unified"),d=await r.json();data=d.results||[];render()}
function code(x){
  if(x.acquisition_type==="season_pack") return `Season ${String(x.season).padStart(2,"0")} Pack`;
  return x.season!=null?`S${String(x.season).padStart(2,"0")}E${String(x.episode).padStart(2,"0")}`:"";
}
function render(){
  const q=queueSearch.value.toLowerCase(),st=queueStatus.value;
  const rows=data.filter(x=>(!st||x.status===st)&&(!q||[x.show_name,x.title,x.client,x.status,x.acquisition_type].join(" ").toLowerCase().includes(q)));
  queueList.innerHTML=rows.length?rows.map(x=>`<div class="queue-row">
    <div class="queue-main"><div class="result-top"><strong>${esc(x.show_name||"Unknown Show")} ${esc(code(x))}</strong>
    <span class="status-pill ${esc(x.status)}">${esc(x.status)}</span></div>
    <div class="queue-release">${esc(x.title||"")}</div>
    <div class="result-meta">${esc(x.client||"")} • ${esc(x.acquisition_type==="season_pack"?"Season pack":"Episode")} • ${esc(x.created_at||"")}</div></div>
    <div class="queue-actions"><button class="secondary action-btn" onclick="historyFor('${x.acquisition_type}',${x.id})">History</button>
    ${x.acquisition_type==="episode"&&x.status!=="Failed"?`<button class="secondary action-btn" onclick="fail(${x.id})">Fail & Retry</button>`:""}</div>
    </div>`).join(""):'<div class="notice good">Queue is clear for this filter.</div>';
}
queueSearch.oninput=render;queueStatus.onchange=render;refreshQueue.onclick=load;
window.historyFor=async(kind,id)=>{
  const r=await fetch(`/api/acquisitions/${kind}/${id}/events`),d=await r.json();
  if(!d.results?.length)return alert("No lifecycle events recorded yet.");
  alert(d.results.slice().reverse().map(x=>`${x.created_at||""}\n${x.from_state||"—"} → ${x.to_state}${x.message?"\n"+x.message:""}`).join("\n\n"));
}
window.fail=async id=>{
  const reason=prompt("Failure reason:","Incorrect or failed release")||"Failed";
  await fetch(`/api/downloads/${id}/fail`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason,retry:true})});
  load();
}
load();


const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
async function load(){
 const [r,h]=await Promise.all([fetch("/api/dashboard/full"),fetch("/api/health")]),d=await r.json(),health=await h.json();
 const items=[["Shows",d.stats.shows],["Episodes",d.stats.episodes],["Wanted",d.stats.wanted],["Snatched",d.stats.snatched],["Downloaded",d.stats.downloaded],["Unaired",d.stats.unaired],["Providers",d.stats.providers],["Failed Releases",d.stats.failed]];
 stats.innerHTML=items.map(x=>`<div class="dash-card"><span>${x[0]}</span><strong>${x[1]}</strong></div>`).join("");
 jobs.innerHTML=d.jobs.map(j=>`<div class="scheduler-row dashboard-job"><div><strong>${esc(j.name.replaceAll("_"," "))}</strong><div class="muted">${esc(j.last_status||"Never run")}</div></div><div>${j.enabled?'<span class="status-pill Downloaded">Enabled</span>':'<span class="status-pill">Paused</span>'}</div><div>${j.interval_minutes} min</div><div>${esc(j.last_run||"—")}</div></div>`).join("");
 const lh=d.library_health||{};
 document.getElementById("health").innerHTML=`<div class="notice ${health.automation?"good":"warn"}">Automation ${health.automation?"armed":"paused"}</div><div class="health-lines"><div><span>Providers</span><strong>${health.providers}</strong></div><div><span>Database</span><strong>OK</strong></div><div><span>Missing Files</span><strong>${lh.missing_episode_files??0}</strong></div><div><span>Duplicate Groups</span><strong>${lh.duplicate_groups??0}</strong></div></div><a class="btn secondary" href="/library-health">Open Library Health</a>`;
 activity.innerHTML=d.activity.length?d.activity.map(x=>`<div class="timeline-row"><span class="timeline-dot"></span><div><strong>${esc(x.message)}</strong><small>${esc(x.created_at)}</small></div></div>`).join(""):'<p class="muted">No activity yet.</p>';
 downloads.innerHTML=d.downloads.length?d.downloads.map(x=>`<div class="result-card"><div class="result-top"><strong>${esc(x.release_name)}</strong><span class="status-pill">${esc(x.status)}</span></div><div class="result-meta">${esc(x.client)} • ${esc(x.added_at)}</div></div>`).join(""):'<p class="muted">No downloads yet.</p>';
}
load(); setInterval(load,30000);

fetch("/api/insights").then(r=>r.json()).then(d=>{insights.innerHTML=d.results.map(x=>`<a class="insight-card ${x.severity}" href="${x.href}"><strong>${esc(x.title)}</strong><span>${esc(x.detail)}</span></a>`).join("")});

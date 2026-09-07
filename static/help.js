(function(){
  const $=(id)=>document.getElementById(id);
  const state={sections:[],workflows:[],parity:[],selected:null};
  function statusClass(status){return 'status-pill parity-'+String(status||'').toLowerCase().replace(/[^a-z0-9]+/g,'-');}
  function escapeHtml(v){return String(v==null?'':v).replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  async function getJson(url){const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(await r.text()); return r.json();}
  function renderParity(filter=''){
    const rows=$('parityRows'); if(!rows) return;
    const f=filter.trim().toLowerCase();
    const items=state.parity.filter(item=>!f || Object.values(item).join(' ').toLowerCase().includes(f));
    if(!items.length){rows.innerHTML='<tr><td colspan="5">No help/parity entries match that search.</td></tr>';return;}
    rows.innerHTML=items.map(item=>`<tr><td>${escapeHtml(item.area)}</td><td>${escapeHtml(item.sickchill_feature)}</td><td>${escapeHtml(item.tv_manager_location)}</td><td><span class="${statusClass(item.status)}">${escapeHtml(item.status)}</span></td><td>${escapeHtml(item.notes)}</td></tr>`).join('');
  }
  function renderSummary(summary){
    const box=$('paritySummary'); if(!box) return;
    const counts=summary.counts||{};
    box.innerHTML=['Complete','Partial','Missing'].map(k=>`<div class="dash-card"><span>${escapeHtml(k)}</span><strong>${Number(counts[k]||0)}</strong></div>`).join('')+`<div class="dash-card"><span>Total mapped</span><strong>${Number(summary.total||0)}</strong></div>`;
  }
  function renderTopics(filter=''){
    const box=$('helpTopics'); if(!box) return;
    const f=filter.trim().toLowerCase();
    const sections=state.sections.filter(s=>!f || [s.title,s.summary,s.slug].join(' ').toLowerCase().includes(f));
    if(!sections.length){box.innerHTML='<p class="muted">No help topics match.</p>';return;}
    box.innerHTML=sections.map(s=>`<button class="help-topic ${state.selected===s.slug?'active':''}" data-slug="${escapeHtml(s.slug)}"><strong>${escapeHtml(s.title)}</strong><small>${escapeHtml(s.summary)}</small></button>`).join('');
    box.querySelectorAll('[data-slug]').forEach(btn=>btn.addEventListener('click',()=>loadSection(btn.dataset.slug)));
  }
  function renderWorkflows(filter=''){
    const box=$('workflowCards'); if(!box) return;
    const f=filter.trim().toLowerCase();
    const items=state.workflows.filter(w=>!f || Object.values(w).join(' ').toLowerCase().includes(f));
    if(!items.length){box.innerHTML='<div class="loading-box">No workflows match that search.</div>';return;}
    box.innerHTML=items.map(w=>`<article class="action-card"><h3>${escapeHtml(w.goal)}</h3><p><strong>Start:</strong> ${escapeHtml(w.start)}</p><p><strong>Next:</strong> ${escapeHtml(w.next)}</p><a class="btn secondary" href="${escapeHtml(w.help)}">Open guide</a></article>`).join('');
  }
  async function loadSection(slug){
    state.selected=slug; renderTopics($('helpSearch')?.value||'');
    const panel=$('selectedHelp'); if(!panel) return;
    panel.innerHTML='<div class="loading-box">Loading help topic…</div>';
    try{
      const data=await getJson('/api/help/'+encodeURIComponent(slug));
      const s=data.section;
      panel.innerHTML=`<p class="section-kicker">HELP TOPIC</p><h2>${escapeHtml(s.title)}</h2><p class="muted">${escapeHtml(s.summary)}</p><ol class="help-steps">${(s.steps||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ol><div class="toolbar"><a class="btn blue" href="/jobs">Jobs</a><a class="btn secondary" href="/logs">Logs</a><a class="btn secondary" href="/database-safety">Database Safety</a></div>`;
      if(location.pathname!=='/help/'+slug) history.replaceState(null,'','/help/'+slug);
    }catch(e){panel.innerHTML='<div class="notice error">Help topic could not load. '+escapeHtml(e.message||e)+'</div>';}
  }
  function applyFilter(){const f=$('helpSearch')?.value||''; renderParity(f); renderTopics(f); renderWorkflows(f);}
  async function init(){
    try{
      const [idx,par]=await Promise.all([getJson('/api/help'),getJson('/api/help/sickchill-parity')]);
      state.sections=idx.sections||[]; state.workflows=idx.workflows||[]; state.parity=par.items||[];
      renderSummary(par); renderParity(); renderTopics(); renderWorkflows();
      $('helpSearch')?.addEventListener('input',applyFilter);
      const initial=window.INITIAL_HELP_SECTION || '';
      if(initial) loadSection(initial); else if(state.sections[0]) loadSection(state.sections[0].slug);
    }catch(e){
      const rows=$('parityRows'); if(rows) rows.innerHTML='<tr><td colspan="5">Help Center could not load: '+escapeHtml(e.message||e)+'</td></tr>';
    }
  }
  document.addEventListener('DOMContentLoaded',init);
})();

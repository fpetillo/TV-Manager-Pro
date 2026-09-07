
(()=>{
  const nativeFetch=window.fetch.bind(window);
  function cookie(name){
    const item=document.cookie.split("; ").find(x=>x.startsWith(name+"="));
    return item?decodeURIComponent(item.slice(name.length+1)):"";
  }
  window.fetch=(input,init={})=>{
    const opts={...init};
    const method=String(opts.method||((input&&input.method)||"GET")).toUpperCase();
    const raw=typeof input==="string"?input:(input&&input.url)||"";
    let sameOrigin=true;
    try{sameOrigin=new URL(raw,location.href).origin===location.origin}catch{}
    if(sameOrigin&&["POST","PUT","PATCH","DELETE"].includes(method)){
      const token=cookie("tvmanager_csrf");
      if(token){
        const headers=new Headers(opts.headers||((input&&input.headers)||undefined));
        if(!headers.has("X-CSRF-Token"))headers.set("X-CSRF-Token",token);
        opts.headers=headers;
      }
    }
    return nativeFetch(input,opts);
  };

  window.addEventListener("DOMContentLoaded",async()=>{
    try{
      const r=await nativeFetch("/api/security/status"),d=await r.json();
      const nav=document.querySelector(".appnav");
      if(nav&&d.browser_auth_enabled){
        const b=document.createElement("button");
        b.className="secondary";
        b.textContent="Sign out";
        b.style.marginTop="8px";
        b.onclick=async()=>{await window.fetch("/logout",{method:"POST"});location.href="/login"};
        nav.appendChild(b);
      }
    }catch{}
  });
})();


(()=>{const palette=document.getElementById("commandPalette"),trigger=document.getElementById("commandTrigger"),input=document.getElementById("commandInput"),results=document.getElementById("commandResults");if(!palette||!trigger)return;
const esc=v=>String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
function open(){palette.hidden=false;setTimeout(()=>input.focus(),30)}function close(){palette.hidden=true;input.value="";results.innerHTML=""}
trigger.onclick=open;palette.onclick=e=>{if(e.target===palette)close()};document.addEventListener("keydown",e=>{if(e.key==="/"&&!["INPUT","TEXTAREA"].includes(document.activeElement.tagName)){e.preventDefault();open()}if(e.key==="Escape")close()});
let timer;input.oninput=()=>{clearTimeout(timer);timer=setTimeout(async()=>{const q=input.value.trim();if(!q){results.innerHTML='<div class="command-empty">Type to search.</div>';return}const r=await fetch("/api/command/search?q="+encodeURIComponent(q)),d=await r.json();results.innerHTML=d.results.length?d.results.map(x=>`<a class="command-result" href="${x.href}"><span class="command-icon">${x.type==="show"?"TV":x.type==="episode"?"EP":"↗"}</span><span><strong>${esc(x.title)}</strong><small>${esc(x.subtitle)}</small></span></a>`).join(""):'<div class="command-empty">No matches.</div>'},120)}
})();


// v17.3 navigation polish and product UX helpers
(()=>{
  function normalize(path){
    if(!path) return "/";
    path=path.replace(/\/+$/,"/");
    if(path.length>1 && path.endsWith("/")) path=path.slice(0,-1);
    return path;
  }
  window.addEventListener("DOMContentLoaded",()=>{
    const here=normalize(location.pathname);
    document.querySelectorAll(".appnav a").forEach(a=>{
      const href=normalize(new URL(a.getAttribute("href"), location.href).pathname);
      if(href===here || (href==="/library-health" && ["/library_health","/health/library"].includes(here))){
        a.classList.add("active");
        a.setAttribute("aria-current","page");
      }
    });
    document.querySelectorAll(".panel > h2:first-child, .toolbar > h2:first-child").forEach(h=>{
      if(!h.previousElementSibling || !h.previousElementSibling.classList?.contains("section-kicker")){
        const kicker=document.createElement("p");
        kicker.className="section-kicker";
        kicker.textContent="TV Manager";
        h.parentNode.insertBefore(kicker,h);
      }
    });
  });
})();


// v17.10.0 responsive sidebar and page-fit helpers
(()=>{
  window.addEventListener("DOMContentLoaded",()=>{
    const nav=document.querySelector(".appnav.side-nav");
    const main=document.querySelector("main.shell");
    if(!nav||!main)return;
    main.classList.add("has-side-navigation","layout-audited");
    const toggle=document.createElement("button");
    toggle.type="button";
    toggle.className="mobile-nav-toggle";
    toggle.setAttribute("aria-expanded","false");
    toggle.setAttribute("aria-controls","tvmanagerSideNav");
    toggle.innerHTML='<span>☰</span><strong>Menu</strong>';
    nav.id=nav.id||"tvmanagerSideNav";
    document.body.insertBefore(toggle, document.body.firstChild);
    toggle.addEventListener("click",()=>{
      const open=document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click",e=>{
      if(e.target.closest("a"))document.body.classList.remove("nav-open");
    });
    document.addEventListener("keydown",e=>{
      if(e.key==="Escape")document.body.classList.remove("nav-open");
    });
    document.querySelectorAll("table").forEach(t=>{
      if(!t.closest(".table-wrap")){
        const wrap=document.createElement("div");
        wrap.className="table-wrap auto-table-wrap";
        t.parentNode.insertBefore(wrap,t);
        wrap.appendChild(t);
      }
    });
  });
})();

// v17.18.0 professional navigation center: collapsible sections, menu filter, status badges
(()=>{
  function norm(path){
    try{path=new URL(path, location.href).pathname;}catch{}
    path=String(path||"/").replace(/\/+$/,"");
    return path || "/";
  }
  function setBadge(link, value, tone){
    if(!link) return;
    const b=link.querySelector("b");
    if(!b) return;
    if(value===undefined || value===null || value==="" || value===0){
      b.hidden=true; link.classList.remove("has-badge","badge-warn","badge-live"); return;
    }
    b.hidden=false; b.textContent=String(value);
    link.classList.add("has-badge");
    if(tone) link.classList.add(tone);
  }
  async function refreshBadges(nav){
    try{
      const r=await fetch("/api/jobs?limit=50");
      const d=await r.json();
      const jobs=Array.isArray(d.jobs)?d.jobs:[];
      const active=jobs.filter(j=>!["complete","error","cancelled"].includes(String(j.status||"").toLowerCase())).length;
      setBadge(nav.querySelector('[data-nav-badge="jobs"]'), active, active?"badge-live":"");
    }catch{}
    try{
      const r=await fetch("/api/logs?limit=25&level=ERROR");
      const d=await r.json();
      const total=Number(d.total ?? (Array.isArray(d.results)?d.results.length:0));
      setBadge(nav.querySelector('[data-nav-badge="logs"]'), total>0?Math.min(total,99):0, total>0?"badge-warn":"");
    }catch{}
    try{
      const r=await fetch("/api/protection/status");
      const d=await r.json();
      const ok=!!(d && d.database && d.database.ok);
      setBadge(nav.querySelector('[data-nav-badge="safety"]'), ok?"✓":"!", ok?"badge-live":"badge-warn");
    }catch{}
  }
  window.addEventListener("DOMContentLoaded",()=>{
    const nav=document.querySelector(".appnav.nav-v18");
    if(!nav) return;
    const here=norm(location.pathname);
    const sections=[...nav.querySelectorAll(".nav-section")];
    const links=[...nav.querySelectorAll("a[href]")];

    links.forEach(a=>{
      const href=norm(a.getAttribute("href"));
      const isRoot=href==="/" && here==="/";
      if(isRoot || (href!=="/" && (href===here || here.startsWith(href+"/")))){
        a.classList.add("active"); a.setAttribute("aria-current","page");
        const sec=a.closest(".nav-section");
        if(sec){
          sec.classList.add("has-active");
          const btn=sec.querySelector(".nav-section-toggle");
          if(btn) btn.setAttribute("aria-expanded","true");
        }
      }
    });

    sections.forEach(sec=>{
      const key="tvmanager.nav.section."+(sec.dataset.section||"section");
      const btn=sec.querySelector(".nav-section-toggle");
      if(!btn) return;
      const saved=localStorage.getItem(key);
      if(saved!==null && !sec.classList.contains("has-active")) btn.setAttribute("aria-expanded", saved==="open"?"true":"false");
      sec.dataset.collapsed=btn.getAttribute("aria-expanded")==="false" ? "true" : "false";
      btn.addEventListener("click",()=>{
        const open=btn.getAttribute("aria-expanded")!=="true";
        btn.setAttribute("aria-expanded", open?"true":"false");
        sec.dataset.collapsed=open?"false":"true";
        localStorage.setItem(key, open?"open":"closed");
      });
    });

    const filter=nav.querySelector("#navFilter");
    if(filter){
      filter.addEventListener("input",()=>{
        const q=filter.value.trim().toLowerCase();
        nav.classList.toggle("nav-filtering", !!q);
        sections.forEach(sec=>{
          let matches=false;
          sec.querySelectorAll("a[href]").forEach(a=>{
            const text=a.textContent.toLowerCase();
            const show=!q || text.includes(q);
            a.hidden=!show;
            if(show) matches=true;
          });
          sec.hidden=!!q && !matches;
          if(q && matches){
            sec.dataset.collapsed="false";
            const btn=sec.querySelector(".nav-section-toggle");
            if(btn) btn.setAttribute("aria-expanded","true");
          }
        });
      });
    }
    refreshBadges(nav);
    setInterval(()=>refreshBadges(nav), 30000);
  });
})();

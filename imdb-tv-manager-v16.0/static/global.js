
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
        b.style.marginLeft="auto";
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

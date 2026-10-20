"""v18.20.0: Show Queue can hide 'not missing' details under each show name."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "show_queue.html").read_text(encoding="utf-8")

ROWS = [
    {"id": 1, "name": "Complete Show", "status": "Ended", "episode_count": 20, "downloaded_count": 20,
     "missing_count": 0, "missing_display": "Complete",
     "season_progress": [{"season": 1, "aired_count": 10, "downloaded_count": 10},
                         {"season": 2, "aired_count": 10, "downloaded_count": 10}]},
    {"id": 2, "name": "Gappy Show", "status": "Continuing", "episode_count": 20, "downloaded_count": 17,
     "missing_count": 3, "missing_display": "S02E01, S02E02, S02E03",
     "season_progress": [{"season": 1, "aired_count": 10, "downloaded_count": 10},
                         {"season": 2, "aired_count": 10, "downloaded_count": 7}]},
]

SCRIPT = r"""
const vm=require('node:vm'), fs=require('node:fs');
const rows=JSON.parse(process.argv[1]); const saved=process.argv[2];
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,{id,value:id==='showQueueLimit'?'100':'',textContent:'',innerHTML:'',className:'',
  disabled:false,hidden:false,dataset:{},after(){},append(){},querySelector(){return null;}});return nodes.get(id);};
const store=new Map(saved?[['tvm.showQueue.detailMode',saved]]:[]);
const ctx={document:{getElementById:node,querySelectorAll:()=>[],addEventListener(){},createElement:()=>node('el'+Math.random()),body:{appendChild(){}}},
  localStorage:{getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,String(v))},
  createShowResolutionControls:()=>({checkbox:()=>({}),selected:new Set()}),
  URLSearchParams, setTimeout, clearTimeout, Promise, console,
  fetch:async()=>({ok:true,headers:{get:()=>'application/json'},json:async()=>({total:rows.length,results:rows,has_more:false})})};
for(const id of ['showQueueSummary','showQueueMessage','showQueueSearch','showQueueStatus','showQueueActive','showQueueLimit',
  'showQueueRefresh','showQueuePrev','showQueueNext','showQueueBody','showQueueScanSelected'])ctx[id]=node(id);
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('static/show_queue.js','utf8'),ctx);
const wait=()=>new Promise(r=>setTimeout(r,30));
(async()=>{
  await wait();
  const out={first:node('showQueueBody').innerHTML, select:node('showQueueDetail').value};
  node('showQueueDetail').value=out.select==='all'?'missing':'all'; node('showQueueDetail').onchange(); await wait();
  out.second=node('showQueueBody').innerHTML; out.stored=store.get('tvm.showQueue.detailMode');
  process.stdout.write(JSON.stringify(out));
})().catch(e=>{console.error(e);process.exit(1);});
"""


def _run(saved=""):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    r = subprocess.run(["node", "-e", SCRIPT, json.dumps(ROWS), saved], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _show_cell(html, name):
    start = html.index(name)
    return html[start:html.index("</td>", start)]


def test_template_has_details_selector_defaulting_to_missing_only():
    assert 'id="showQueueDetail"' in HTML
    assert '<option value="missing" selected>' in HTML
    assert '<option value="all">' in HTML


def test_missing_only_is_default_and_hides_complete_seasons():
    out = _run()
    assert out["select"] == "missing"
    complete = _show_cell(out["first"], "Complete Show")
    assert "Missing:" not in complete and "aired missing" not in complete
    gappy = _show_cell(out["first"], "Gappy Show")
    assert "Missing: S02E01, S02E02, S02E03" in gappy
    assert "S02: 3/10 aired missing" in gappy
    assert "S01: 0/10" not in gappy


def test_all_seasons_restores_full_details_and_is_remembered():
    out = _run()
    assert out["stored"] == "all"
    complete = _show_cell(out["second"], "Complete Show")
    assert "Missing: Complete" in complete
    assert "S01: 0/10 aired missing · S02: 0/10 aired missing" in complete
    assert "S01: 0/10 aired missing · S02: 3/10 aired missing" in _show_cell(out["second"], "Gappy Show")


def test_saved_choice_is_used_on_next_visit():
    out = _run("all")
    assert out["select"] == "all"
    assert "S01: 0/10 aired missing" in _show_cell(out["first"], "Complete Show")

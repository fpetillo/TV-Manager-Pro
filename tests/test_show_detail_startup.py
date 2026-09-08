"""Execute the actual page script: syntax-only checks miss ASI call chaining."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_page_startup_schedules_reads_without_invoking_downloader():
    script = r"""
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const nodes = new Map();
const timers = [];
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {value: id === 'episodeLimit' ? '100' : '',
    dataset: {showId: '1'}, addEventListener() {}, textContent: '', innerHTML: ''});
  return nodes.get(id);
};
const context = {document: {querySelector: () => node('page'),
  getElementById: node, querySelectorAll: () => []},
  setTimeout: (fn, delay) => {timers.push({fn, delay}); return timers.length;},
  clearTimeout() {}, console};
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/show_detail.js', 'utf8'), context);
assert.equal(typeof context.grabResult, 'function');
assert.equal(context.grabSearchResult, context.grabResult);
assert.ok(timers.some(t => t.delay === 0), 'header startup must be scheduled');
assert.ok(timers.some(t => t.delay === 50), 'episode startup must be scheduled');
const calls = [];
context.loadShow = async () => calls.push('header');
context.loadEpisodes = async () => calls.push('episodes');
Promise.all(timers.filter(t => [0,50].includes(t.delay)).map(t => t.fn()))
  .then(() => assert.deepEqual(calls, ['header','episodes']));
"""
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_season_browser_lazy_loads_complete_season_and_ignores_stale_results():
    script = r"""
const vm=require('node:vm'), fs=require('node:fs'), assert=require('node:assert/strict');
const nodes=new Map();
const node=id=>{
 if(!nodes.has(id))nodes.set(id,{value:'',dataset:{showId:'1'},style:{},classList:{add(){}},
  textContent:'',innerHTML:'',addEventListener(){},querySelectorAll(){return [];},closest(){return node('table');}});
 return nodes.get(id);
};
const ctx={document:{querySelector:()=>node('page'),getElementById:node,querySelectorAll:()=>[],createElement:()=>({})},
 setTimeout(){},clearTimeout(){},URLSearchParams,console};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/show_detail.js','utf8'),ctx);
(async()=>{
 const calls=[];
 ctx.jsonFetch=async url=>{calls.push(url);return {seasons:[{season:0,episode_count:7,with_files:0},{season:2,episode_count:1,with_files:1},{season:1,episode_count:24,with_files:18}]};};
 await ctx.loadEpisodes();
 assert.equal(calls.length,1,'collapsed seasons must not fetch episodes');
 const html=node('episodeBody').innerHTML;
 assert.ok(html.indexOf('Season 01')<html.indexOf('Season 02'));
 assert.ok(html.indexOf('Season 02')<html.indexOf('Specials (S00)'));
 assert.ok(!html.includes(' open'), 'all seasons start collapsed');
 assert.match(html,/18 of 24 episodes downloaded/);assert.match(html,/1 of 1 episode downloaded/);assert.match(html,/0 of 7 episodes downloaded/);
 assert.ok(calls[0].endsWith('/episodes'),'load season totals without fetching episode pages');
 const body={innerHTML:''},message={textContent:'',append(){}};
 const folder={dataset:{},querySelector:s=>s==='tbody'?body:message};
 let page=0;
 node('episodeSearch').value='Pilot';node('episodeStatus').value='Wanted';
 ctx.jsonFetch=async url=>{
  const p=new URL(url,'http://localhost').searchParams;
  assert.equal(p.get('season'),'1');assert.equal(p.get('q'),'Pilot');assert.equal(p.get('status'),'Wanted');
  assert.equal(Number(p.get('offset')),page*100);
  page++;return {episodes:[{id:page,season:1,episode:page,name:'Pilot '+page}],has_more:page===1,next_offset:100};
 };
 await ctx.fillSeason(folder,1,1);
 assert.equal(page,2);assert.match(body.innerHTML,/Pilot 1/);assert.match(body.innerHTML,/Pilot 2/);
 assert.equal(folder.dataset.loaded,'yes');assert.equal(message.textContent,'2 episodes');
 await ctx.fillSeason(folder,1,1);assert.equal(page,2,'reopening cached season must not duplicate fetch');
 const stale={dataset:{},querySelector:s=>s==='tbody'?{innerHTML:''}:message};
 let resolve;
 ctx.jsonFetch=()=>new Promise(r=>resolve=r);
 const pending=ctx.fillSeason(stale,2,1);
 vm.runInContext('seasonGeneration++',ctx);
 resolve({episodes:[{id:3,season:2,episode:1}],has_more:false});
 await pending;assert.notEqual(stale.dataset.loaded,'yes');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr

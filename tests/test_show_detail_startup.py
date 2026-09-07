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

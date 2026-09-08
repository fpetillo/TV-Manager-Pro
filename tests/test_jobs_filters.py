from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def test_status_filters_counts_empty_state_and_refresh_preserve_selection():
    script=r"""
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',contains:()=>false,querySelectorAll:()=>[]});return nodes.get(id);};
const ctx={document:{getElementById:node,activeElement:null},window:{addEventListener(){}},console};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/jobs.js','utf8'),ctx);
vm.runInContext("jobs=[{status:'queued'},{status:'running'},{status:'complete'},{status:'error'},{status:'cancelled'},{status:'paused'}];selectedStatus='active';renderJobs()",ctx);
assert.match(node('jobFilterSummary').textContent,/Showing 2 of 6/);
assert.match(node('jobStatusFilters').innerHTML,/Active \(2\)/);
assert.match(node('jobStatusFilters').innerHTML,/Completed \(1\)/);
assert.match(node('jobStatusFilters').innerHTML,/Failed \(1\)/);
assert.match(node('jobStatusFilters').innerHTML,/paused \(1\)/);
vm.runInContext("jobs=[{status:'complete'},{status:'complete'}];renderJobs()",ctx);
assert.equal(vm.runInContext('selectedStatus',ctx),'active');
assert.match(node('jobFilterSummary').textContent,/Showing 0 of 2/);
assert.match(node('jobsList').innerHTML,/No jobs match/);
vm.runInContext("selectedStatus='complete';renderJobs()",ctx);
assert.match(node('jobFilterSummary').textContent,/Showing 2 of 2/);
vm.runInContext("selectedStatus='error';renderJobs()",ctx);
assert.match(node('jobFilterSummary').textContent,/Showing 0 of 2/);
"""
    result=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

"""Compare JS static-mode calculations with the SQL API for every shipped filter combination."""

import itertools
import json
import os
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from telecom_cloud.api import app

root = Path(__file__).resolve().parents[1]
data = json.loads((root / "dist/assets/demo.json").read_text())
config = data["metadata"]["release"]["config"]
cases = []
with TestClient(app) as client:
    for region, network, period, minimum in itertools.product(
        [r["id"] for r in config["regions"]], config["networks"], config["periods"], [1, 10, 30, 100]
    ):
        params = dict(region=region, network=network, period=period, minimum_tests=minimum)
        response = client.get("/api/explore", params=params)
        response.raise_for_status()
        result = response.json()
        cases.append(
            {
                "params": params,
                "summary": result["summary"],
                "comparison": result["comparison"],
                "excluded_tiles": result["excluded_tiles"],
            }
        )
script = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({document:{}, console, URLSearchParams});
let code=fs.readFileSync('web/app.js','utf8').replace(/init\(\);\s*$/, '');
vm.runInContext(code,context);
context.data=input.data;
vm.runInContext('snapshotData=data; release=data.metadata.release;',context);
for(const c of input.cases){
 context.p=c.params;
 const result=vm.runInContext('localView(p.region,p.network,p.period,p.minimum_tests)',context);
 for(const [key,value] of Object.entries(c.summary)){
   if(value===null)assert.equal(result.summary[key],null);
   else assert.ok(Math.abs(result.summary[key]-value)<1e-8, `${key} mismatch`);
 }
 assert.equal(result.excluded_tiles,c.excluded_tiles);
 assert.equal(result.tiles.length,c.summary.tiles);
 if(c.comparison){
   assert.equal(result.comparison.matched_tiles,c.comparison.matched_tiles);
   if(c.comparison.download_change_mbps===null)assert.equal(result.comparison.download_change_mbps,null);
   else assert.ok(Math.abs(result.comparison.download_change_mbps-c.comparison.download_change_mbps)<1e-8);
 }else assert.equal(result.comparison,null);
}
console.log(`Frontend/API parity verified: ${input.cases.length} filter combinations`);
"""
result = subprocess.run(
    [os.getenv("TELECOM_NODE", "node"), "-e", script],
    input=json.dumps({"data": data, "cases": cases}),
    text=True,
    cwd=root,
    capture_output=True,
    check=True,
)
print(result.stdout.strip())

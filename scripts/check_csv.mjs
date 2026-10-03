// Exercise the actual frontend export function using DOM/Blob fakes, not a browser.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const data=JSON.parse(fs.readFileSync('dist/assets/demo.json','utf8'));
let exported, filename, clicked=false;
const anchor={click(){clicked=true;},set download(v){filename=v;},href:''};
const context=vm.createContext({document:{getElementById(){return {};},createElement(){return anchor;}},URL:{createObjectURL(blob){exported=blob;return 'blob:test';},revokeObjectURL(){}},URLSearchParams,Blob,setTimeout(){},console});
vm.runInContext(fs.readFileSync('web/app.js','utf8').replace(/init\(\);\s*$/,''),context);
context.data=data;
vm.runInContext("snapshotData=data;release=data.metadata.release;view=localView('madrid','mobile','2024-Q4',30);csv();",context);
const text=await exported.text(),lines=text.trim().split('\n');
assert.equal(lines.length-1,83);
assert.equal(filename,'telecom-madrid-mobile-2024-Q4.csv');
assert.ok(clicked);
assert.equal(lines[0],'region,period,network,quadkey,longitude,latitude,download_kbps,upload_kbps,latency_ms,tests,devices');
for(const line of lines.slice(1)){assert.ok(line.startsWith('"madrid","2024-Q4","mobile",'));}
console.log('Frontend CSV export verified: 83 filtered rows, explicit units, filename and download trigger.');

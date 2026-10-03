'use strict';
const $ = id => document.getElementById(id);
let meta, release, snapshotData, view, requestVersion = 0;
const fmt = (v, n=1) => v === null || v === undefined ? '—' : Number(v).toLocaleString('en-US',{maximumFractionDigits:n});
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function weighted(rows){const tests=rows.reduce((s,r)=>s+r.tests,0);return {tiles:rows.length,tests,download_mbps:tests?rows.reduce((s,r)=>s+r.download_kbps*r.tests,0)/tests/1000:null,upload_mbps:tests?rows.reduce((s,r)=>s+r.upload_kbps*r.tests,0)/tests/1000:null,latency_ms:tests?rows.reduce((s,r)=>s+r.latency_ms*r.tests,0)/tests:null};}
function localView(region,network,period,minimum_tests){
 const selected=snapshotData.rows.filter(r=>r.region===region&&r.network===network&&r.tests>=minimum_tests), rows=selected.filter(r=>r.period===period);
 const i=release.config.periods.indexOf(period);let comparison=null;
 if(i>0){const p=release.config.periods[i-1],old=new Map(selected.filter(r=>r.period===p).map(r=>[r.quadkey,r])),common=rows.filter(r=>old.has(r.quadkey));comparison={previous_period:p,matched_tiles:common.length,download_change_mbps:common.length?common.reduce((s,r)=>s+(r.download_kbps-old.get(r.quadkey).download_kbps)/1000,0)/common.length:null};}
 return {selection:{region,network,period,minimum_tests},summary:weighted(rows),tiles:rows,trend:release.config.periods.map(p=>({period:p,...weighted(selected.filter(r=>r.period===p))})),comparison,excluded_tiles:snapshotData.rows.filter(r=>r.region===region&&r.network===network&&r.period===period).length-rows.length,review_thresholds:{download_mbps:release.config.review_download_mbps,latency_ms:release.config.review_latency_ms}};
}
async function load(){
 const version=++requestVersion; const p=new URLSearchParams({region:$('region').value,network:$('network').value,period:$('period').value,minimum_tests:$('minimum').value});
 try{let result;if(snapshotData)result=localView(p.get('region'),p.get('network'),p.get('period'),+p.get('minimum_tests'));else{const r=await fetch(`./api/explore?${p}`);if(!r.ok)throw Error(`Data API returned ${r.status}`);result=await r.json();}if(version!==requestVersion)return;view=result;$('error').hidden=true;render();}catch(e){if(version!==requestVersion)return;$('error').hidden=false;$('error').textContent='Unable to load this selection. '+e.message;}
}
function render(){
 for(const [id,key] of [['download','download_mbps'],['upload','upload_mbps'],['latency','latency_ms'],['tests','tests']])$(id).textContent=fmt(view.summary[key],id==='tests'?0:1);
 $('tiles').textContent=`${fmt(view.summary.tiles,0)} tiles · ${fmt(view.excluded_tiles,0)} excluded by test threshold`;
 const max=Math.max(1,...view.trend.map(r=>r.download_mbps||0));
 $('trend').innerHTML=view.trend.map(r=>`<div class="trend-row"><span>${esc(r.period)}</span><div class="bar-track"><div class="bar-fill" style="width:${(r.download_mbps||0)/max*100}%"></div></div><strong>${fmt(r.download_mbps)}</strong></div>`).join('');
 const c=view.comparison;$('comparison').textContent=c&&c.matched_tiles?`Matched tiles: ${fmt(c.download_change_mbps)} Mbps mean change vs ${c.previous_period}, across ${fmt(c.matched_tiles,0)} common tiles. Equal tile weights; changing samples may affect results.`:(c?'No tiles meet the test threshold in both comparison periods.':'Select a later quarter to compare the same tiles across periods.');
 const t=view.review_thresholds, flagged=view.tiles.filter(r=>r.download_kbps/1000<t.download_mbps||r.latency_ms>t.latency_ms).sort((a,b)=>a.download_kbps-b.download_kbps||b.latency_ms-a.latency_ms);
 $('threshold-note').textContent=`Download below ${t.download_mbps} Mbps or latency above ${t.latency_ms} ms.`;
 $('review-count').textContent=`${fmt(flagged.length,0)} tiles`;
 $('coverage').textContent=`${fmt(view.excluded_tiles,0)} tiles excluded for having fewer than ${view.selection.minimum_tests} tests.`;
 $('table-count').textContent=`Showing ${Math.min(30,flagged.length)} of ${fmt(flagged.length,0)}`;
 $('rows').innerHTML=flagged.slice(0,30).map(r=>`<tr><td>${esc(r.quadkey)}</td><td>${fmt(r.download_kbps/1000)}</td><td>${fmt(r.upload_kbps/1000)}</td><td>${fmt(r.latency_ms)}</td><td>${fmt(r.tests,0)}</td><td>${fmt(r.latitude,4)}, ${fmt(r.longitude,4)}</td></tr>`).join('')||'<tr><td colspan="6">No tiles meet the review criteria in this selection.</td></tr>';
 $('map-selection').textContent='Select a point to inspect its measurements.';drawMap();
}
function drawMap(){
 if(!view)return;const box=release.config.regions.find(r=>r.id===view.selection.region).bbox,metric=$('metric').value,isSpeed=metric==='download_kbps';
 const values=view.tiles.map(r=>r[metric]/(isSpeed?1000:1)),lo=values.length?Math.min(...values):0,hi=values.length?Math.max(...values):0;
 const W=760,H=410,P=42,merc=lat=>Math.log(Math.tan(Math.PI/4+lat*Math.PI/360));
 const x=lon=>P+(lon-box[0])/(box[2]-box[0])*(W-2*P), y=lat=>H-P-(merc(lat)-merc(box[1]))/(merc(box[3])-merc(box[1]))*(H-2*P);
 let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(view.selection.region)} geographic measurement map"><rect width="760" height="410" fill="#edf3f6"/>`;
 for(let i=0;i<=4;i++){const lon=box[0]+i*(box[2]-box[0])/4,lat=box[1]+i*(box[3]-box[1])/4;svg+=`<line x1="${x(lon)}" x2="${x(lon)}" y1="${P}" y2="${H-P}" stroke="#d3e0e7"/><line x1="${P}" x2="${W-P}" y1="${y(lat)}" y2="${y(lat)}" stroke="#d3e0e7"/><text x="${x(lon)}" y="${H-15}" font-size="11" fill="#6b8290" text-anchor="middle">${lon.toFixed(2)}°</text><text x="4" y="${y(lat)}" font-size="10" fill="#6b8290">${lat.toFixed(2)}°</text>`;}
 view.tiles.forEach((r,i)=>{const v=values[i],z=hi>lo?(v-lo)/(hi-lo):.5,col=`hsl(${isSpeed?201:25} 65% ${80-z*55}%)`;svg+=`<circle data-index="${i}" cx="${x(r.longitude)}" cy="${y(r.latitude)}" r="3.1" fill="${col}" stroke="white" stroke-width=".4"><title>${esc(r.quadkey)}: ${fmt(v)} ${isSpeed?'Mbps':'ms'}, ${r.tests} tests</title></circle>`;});
 if(!values.length)svg+='<text x="380" y="210" text-anchor="middle" fill="#607b8c">No measurements meet this test threshold.</text>';
 $('map').innerHTML=svg+'</svg>';
 $('legend').innerHTML=`<span>${fmt(lo)} ${isSpeed?'Mbps':'ms'}</span><div class="legend-bar" style="${isSpeed?'':'background:linear-gradient(90deg,hsl(25 65% 80%),hsl(25 65% 25%))'}"></div><span>${fmt(hi)} ${isSpeed?'Mbps':'ms'}</span><span>Range in current view</span>`;
 $('map').querySelectorAll('circle').forEach(el=>el.addEventListener('click',()=>{const r=view.tiles[+el.dataset.index];$('map-selection').textContent=`Tile ${r.quadkey} · ${fmt(r.download_kbps/1000)} Mbps down · ${fmt(r.upload_kbps/1000)} Mbps up · ${fmt(r.latency_ms)} ms · ${fmt(r.tests,0)} tests · ${fmt(r.devices,0)} devices`; }));
}
function csv(){if(!view)return;const cols=['region','period','network','quadkey','longitude','latitude','download_kbps','upload_kbps','latency_ms','tests','devices'];const text=[cols.join(','),...view.tiles.map(r=>cols.map(k=>JSON.stringify(r[k])).join(','))].join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/csv'}));a.download=`telecom-${view.selection.region}-${view.selection.network}-${view.selection.period}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
async function init(){
 try{
  // Static mode is explicit via configuration file, never a silent fallback for a failed live API.
  const settings=await fetch('./assets/mode.json').then(r=>r.ok?r.json():{mode:'api'});
  if(settings.mode==='snapshot'){snapshotData=await fetch('./assets/demo.json').then(r=>{if(!r.ok)throw Error('Snapshot missing');return r.json();});meta=snapshotData.metadata;}else{const r=await fetch('./api/metadata');if(!r.ok)throw Error('Run the pipeline to create a data release.');meta=await r.json();}
  release=meta.release;
  $('mode').textContent=snapshotData?'Static data snapshot':meta.runtime.mode==='azure'?'Azure runtime':'Local runtime';
  $('release-date').textContent=release.config.periods.join(' → ');
  $('release-info').textContent=`${fmt(release.rows,0)} tile observations · ${release.partitions} validated partitions`;
  const options=(id,items)=>{$(id).innerHTML=items.map(([v,l])=>`<option value="${esc(v)}">${esc(l)}</option>`).join('');};
  options('region',release.config.regions.map(r=>[r.id,r.name]));options('network',release.config.networks.map(n=>[n,n==='fixed'?'Fixed broadband':'Mobile']));options('period',release.config.periods.map(p=>[p,p]));$('period').value=release.config.periods.at(-1);
  $('cloud-status').textContent=`Current view: ${snapshotData?'static snapshot':meta.runtime.mode+' runtime'}. Architecture below describes the deployment design; Azure execution and cost require separate live verification.`;
  $('run-facts').innerHTML=[['Rows',fmt(release.rows,0)],['Partitions',release.partitions],['Changed partitions',release.changed_partitions],['Build duration',fmt(release.duration_seconds)+' s']].map(([k,v])=>`<div><span>${k}</span><strong>${v}</strong></div>`).join('');
  $('provenance').textContent=`Data retrieved and release generated: ${new Date(release.generated_at).toISOString()}. Release ID: ${release.run_id}.`;$('sources').textContent=JSON.stringify(release.sources,null,2);
  for(const id of ['region','network','period','minimum'])$(id).addEventListener('change',load);$('metric').addEventListener('change',drawMap);$('export').addEventListener('click',csv);
  document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(t=>t.hidden=t.id!==b.dataset.tab);document.querySelectorAll('nav button').forEach(n=>n.classList.toggle('active',n===b));}));
  await load();
 }catch(e){$('error').hidden=false;$('error').textContent=e.message;$('mode').textContent='Data unavailable';}
}
init();

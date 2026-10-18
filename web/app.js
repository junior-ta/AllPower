const portal = document.body.dataset.portal;
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('allpower-token') || '';
let selected = null;
let pending = sessionStorage.getItem('allpower-pending-run');
let polling = false;
let adviceBusy = false;
let previewUrl;

function access(message) {
  $('access-panel').classList.remove('connected');
  $('access-message').textContent = message || 'Enter your token to connect.';
  $('worker').textContent = 'Access needed';
  $('worker').classList.remove('ok');
}
async function api(path, options = {}) {
  const headers = {'X-AllPower-Token': token, ...(options.headers || {})};
  const response = await fetch('/api' + path, {...options, headers});
  let data;
  try { data = await response.json(); } catch { throw Error('API returned an unreadable response'); }
  if (response.status === 401) { access('Access token required or invalid for this portal.'); throw Error('Access token required'); }
  if (!response.ok) throw Error(data.error || 'Request failed');
  return data;
}
function view() {
  const defaultView = portal === 'hospital' ? 'overview' : 'outlook';
  const allowed = portal === 'hospital' ? ['overview','preparedness'] : ['outlook','inspection'];
  const name = allowed.includes(location.hash.slice(1)) ? location.hash.slice(1) : defaultView;
  document.querySelectorAll('[data-view]').forEach(el => { el.hidden = el.dataset.view !== name; });
  document.querySelectorAll('[data-link]').forEach(el => { el.classList.toggle('current', el.dataset.link === name); });
}
window.addEventListener('hashchange', view);
view();

function chart(data) {
  const svg = $('chart'); svg.replaceChildren();
  const ns = 'http://www.w3.org/2000/svg';
  const make = (tag, attrs, label) => {
    const el = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key,value]) => el.setAttribute(key, String(value)));
    if (label !== undefined) el.textContent = label;
    svg.append(el);
  };
  const demand = data.forecast_mw;
  const supply = data.supply_mw.map(v => v - data.reserve_mw);
  const lo = Math.floor((Math.min(...demand, ...supply) - 2500) / 5000) * 5000;
  const hi = Math.max(lo + 5000, Math.ceil((Math.max(...demand, ...supply) + 2500) / 5000) * 5000);
  const x = i => 60 + i * 132;
  const y = v => 244 - (v - lo) / (hi - lo) * 190;
  for (let i = 0; i < 4; i++) {
    const value = lo + (hi - lo) * i / 3, yy = y(value);
    make('line', {x1:60,y1:yy,x2:730,y2:yy,stroke:'#385665','stroke-width':1});
    make('text', {x:8,y:yy+4,fill:'#a3bcc3','font-size':11}, Math.round(value/1000) + 'k');
  }
  for (let i = 0; i < 6; i++) make('text', {x:x(i)-7,y:276,fill:'#a3bcc3','font-size':11}, '+' + (i+1) + 'h');
  for (const [series,color] of [[supply,'#ffc06e'],[demand,'#48e6c1']]) {
    make('polyline', {points:series.map((v,i) => `${x(i)},${y(v)}`).join(' '),fill:'none',stroke:color,'stroke-width':3,'stroke-linejoin':'round'});
    series.forEach((v,i) => make('circle', {cx:x(i),cy:y(v),r:4,fill:color}));
  }
}
function display(run) {
  if (!run || run.status !== 'done' || !run.result) return;
  selected = run;
  sessionStorage.setItem('allpower-selected-run', run.id);
  const d = run.result, b = d.backup;
  chart(d);
  $('headline').textContent = d.first_deficit_hour ? `Tight margin in hour ${d.first_deficit_hour}` : 'Reserve margin stays positive';
  $('risk-badge').textContent = d.risk === 'prepare' ? 'PREPARE' : 'NORMAL';
  $('risk-badge').className = 'badge ' + d.risk;
  $('origin').textContent = `${d.scenario_name} · Forecast origin ${d.input_timestamp} · Run ${run.id.slice(0,8)}`;
  $('provenance').textContent = `Demand: ${d.provenance.demand_history}. Supply/reserve: simulated. Model: ${d.model_version}. Regional risk does not guarantee a local hospital outage.`;
  $('hours').replaceChildren(...d.margin_mw.map((margin,i) => {
    const box = document.createElement('div');
    if (margin < 0) box.className = 'negative';
    const strong = document.createElement('strong'); strong.textContent = 'Hour ' + (i+1);
    const span = document.createElement('span'); span.textContent = `${Math.round(margin).toLocaleString()} MW margin`;
    box.append(strong,span); return box;
  }));
  if (portal === 'hospital') {
    $('advisory-title').textContent = d.risk === 'prepare' ? 'Prepare backup power now' : 'Continue routine monitoring';
    $('advisory-text').textContent = d.advisory_text;
    $('served').textContent = Math.round(b.critical_served_kwh).toLocaleString() + ' kWh';
    $('compare').textContent = `${Math.round(b.improvement_kwh)} modeled critical kWh gained against a reactive startup policy. ${b.method}.`;
    $('prepared-bar').style.width = 100 * (1 - b.critical_unmet_kwh / b.critical_demand_kwh) + '%';
    $('reactive-bar').style.width = 100 * (1 - b.reactive_unmet_kwh / b.critical_demand_kwh) + '%';
    $('ack').disabled = run.advisory?.status === 'acknowledged';
    $('ack-state').textContent = run.advisory?.status === 'acknowledged' ? `Acknowledged ${new Date(run.advisory.acknowledged_at*1000).toLocaleString()}` : 'Awaiting acknowledgment';
    $('advice-context').textContent = `${d.scenario_name} · ${d.risk === 'prepare' ? 'Preparation alert' : 'Routine monitoring'}`;
    $('advice-facts').textContent = `Forecast origin ${d.input_timestamp}. First tight-margin hour: ${d.first_deficit_hour ?? 'none'}. Modeled six-hour critical energy served: ${Math.round(b.critical_served_kwh)} kWh; unmet: ${Math.round(b.critical_unmet_kwh)} kWh.`;
    $('alert-chat').hidden = d.risk !== 'prepare';
    loadAdvice(run);
  }
}
async function loadAdvice(run) {
  try {
    const data = await api(`/hospital/runs/${run.id}/advice`);
    if (selected?.id !== run.id) return;
    showMessages(data.messages);
    if (run.result.risk === 'prepare' && !data.messages.some(m => m.role === 'assistant')) {
      await askAdvice('');
    }
  } catch (error) { $('advice-status').textContent = error.message; }
}
function showMessages(messages) {
  const wrap = $('messages'); wrap.replaceChildren();
  if (!messages.length) { const p=document.createElement('p'); p.className='muted'; p.textContent='Ask a question about this saved outlook.'; wrap.append(p); }
  for (const message of messages) {
    const el=document.createElement('div'); el.className='message ' + message.role;
    const caption=document.createElement('small'); caption.textContent=message.role === 'user' ? 'You' : (message.provider === 'demo-checklist-v1' ? 'Prepared checklist' : 'Preparation assistant · ' + message.provider);
    const body=document.createElement('div'); body.textContent=message.content;
    el.append(caption,body); wrap.append(el);
  }
  wrap.scrollTop=wrap.scrollHeight;
  const last=[...messages].reverse().find(m => m.role === 'assistant');
  if (last && $('chat-preview')) $('chat-preview').textContent=last.content.split('\n')[0];
}
async function askAdvice(question) {
  if (!selected || adviceBusy) return;
  adviceBusy=true; $('advice-status').textContent='Preparing a response…';
  const runId=selected.id;
  try {
    const result=await api('/hospital/advice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:runId,question})});
    if (selected?.id !== runId) return;
    const data=await api(`/hospital/runs/${runId}/advice`);
    showMessages(data.messages);
    $('advice-status').textContent=result.fallback ? 'Prepared checklist shown; text model unavailable.' : `Explanation generated by ${result.provider}.`;
  } catch(error) { $('advice-status').textContent=error.message; }
  finally { adviceBusy=false; }
}
async function history() {
  const data=await api('/hospital/acknowledgments');
  const list=$('ack-history'); list.replaceChildren();
  if (!data.acknowledgments.length) { list.textContent='No acknowledgments yet.'; return; }
  for (const item of data.acknowledgments) {
    const button=document.createElement('button'); button.type='button';
    button.textContent=`${item.scenario} · ${new Date(item.acknowledged_at*1000).toLocaleString()} · ${item.run_id.slice(0,8)}`;
    button.addEventListener('click',async()=>{ try { display(await api('/runs/'+item.run_id)); location.hash='overview'; } catch(error) { list.textContent=error.message; } });
    list.append(button);
  }
}
async function status() {
  const data=await api('/status');
  $('worker').textContent=data.worker_alive ? 'Worker online' : 'Worker offline · saved records available';
  $('worker').classList.toggle('ok',data.worker_alive);
}
async function poll(runId) {
  if (polling) return;
  polling=true;
  try {
    while (pending === runId) {
      const run=await api('/runs/'+runId);
      document.querySelectorAll('.run-state').forEach(el=>el.textContent=run.status === 'queued' ? 'Queued · waiting for worker' : run.status === 'running' ? 'Worker processing…' : run.status);
      if (run.status === 'done') {
        pending=null; sessionStorage.removeItem('allpower-pending-run'); display(run);
        document.querySelectorAll('.run-state').forEach(el=>el.textContent='Run complete · '+run.id.slice(0,8));
        return;
      }
      if (run.status === 'failed') { pending=null; sessionStorage.removeItem('allpower-pending-run'); return; }
      await new Promise(resolve=>setTimeout(resolve,3000));
    }
  } catch(error) { document.querySelectorAll('.run-state').forEach(el=>el.textContent=error.message); }
  finally { polling=false; }
}
async function boot() {
  try {
    await status(); $('access-panel').classList.add('connected');
    const stored=sessionStorage.getItem('allpower-selected-run');
    let run=stored ? await api('/runs/'+stored).catch(()=>null) : null;
    if (!run || run.status !== 'done') run=await api('/runs/latest');
    if (run) display(run);
    if (portal === 'hospital') await history();
    else await facilities();
    if (pending) poll(pending);
  } catch(error) { if (error.message !== 'Access token required') $('access-message').textContent=error.message; }
}
$('access-form').addEventListener('submit',event=>{ event.preventDefault(); token=$('token').value.trim(); sessionStorage.setItem('allpower-token',token); boot(); });
$('clear-token').addEventListener('click',()=>{ token=''; sessionStorage.removeItem('allpower-token'); $('token').value=''; access('Token cleared. Enter a token to reconnect.'); });
document.querySelectorAll('.scenario-form').forEach(form=>form.addEventListener('submit',async event=>{
  event.preventDefault(); const button=form.querySelector('button'); button.disabled=true;
  try {
    const scenario=form.querySelector('select').value;
    const job=await api(`/scenarios/${scenario}/run`,{method:'POST'});
    pending=job.run_id; sessionStorage.setItem('allpower-pending-run',pending);
    document.querySelectorAll('.run-state').forEach(el=>el.textContent='Queued · waiting for worker');
    poll(pending);
  } catch(error) { form.parentElement.querySelector('.run-state').textContent=error.message; }
  finally { button.disabled=false; }
}));
if (portal === 'hospital') {
  $('ack').addEventListener('click',async()=>{
    if (!selected?.advisory) return;
    try {
      const result=await api(`/advisories/${selected.advisory.id}/acknowledge`,{method:'POST'});
      selected.advisory=result;
      $('ack').disabled=true;
      $('ack-state').textContent=`Acknowledged ${new Date(result.acknowledged_at*1000).toLocaleString()}`;
      await history();
    } catch(error) { $('ack-state').textContent=error.message; }
  });
  $('advice-form').addEventListener('submit',async event=>{ event.preventDefault(); const value=$('question').value.trim(); if (!value) return; $('question').value=''; await askAdvice(value); });
}
async function facilities() {
  const data=await api('/supplier/facilities');
  const tbody=$('facility-rows'); tbody.replaceChildren();
  for (const item of data.facilities) {
    const row=document.createElement('tr');
    for (const value of [item.name,item.location,item.state,Math.round(item.confidence*100)+'%']) {
      const cell=document.createElement('td'); cell.textContent=value; row.append(cell);
    }
    const cell=document.createElement('td');
    if (item.live_demo) {
      const button=document.createElement('button'); button.textContent='View in real time';
      button.addEventListener('click',()=>liveInspection(item)); cell.append(button);
    } else { const span=document.createElement('span'); span.className='unavailable'; span.textContent='Feed not connected'; cell.append(span); }
    row.append(cell); tbody.append(row);
  }
}
async function classify(file) {
  if (!['image/png','image/jpeg'].includes(file.type) || file.size > 2_000_000) throw Error('Use a PNG or JPEG under 2 MB.');
  return api('/inspection',{method:'POST',headers:{'Content-Type':file.type},body:file});
}
function inspectionText(result) {
  const score=Number(result.defect_score);
  const confidence=result.result === 'inspection required' ? 'Uncertain score' : `Class score ${Math.round(100*(result.result === 'defect concern' ? score : 1-score))}%`;
  return `${result.result} · ${confidence} · defect score ${score.toFixed(3)} · ${result.model_version}. Human review required before an operational decision.`;
}
async function liveInspection(item) {
  $('live-panel').hidden=false; $('live-title').textContent=item.name;
  $('live-result').textContent='Running a fresh model classification…';
  $('live-detail').textContent=''; $('live-panel').scrollIntoView({behavior:'smooth',block:'nearest'});
  try {
    const image=await fetch('/demo-insulator.png'); if (!image.ok) throw Error('Example image unavailable');
    const data=await classify(await image.blob());
    $('live-result').textContent=inspectionText(data);
    $('live-detail').textContent=`Fresh response ${new Date().toLocaleString()} · ${data.provenance}. Fictional facility status above is unchanged.`;
  } catch(error) { $('live-result').textContent=error.message; }
}
if (portal === 'supplier') {
  $('image-file').addEventListener('change',()=>{
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const file=$('image-file').files[0];
    $('image-preview').hidden=!file;
    if (file) { previewUrl=URL.createObjectURL(file); $('image-preview').src=previewUrl; }
  });
  $('inspection-form').addEventListener('submit',async event=>{
    event.preventDefault(); const file=$('image-file').files[0];
    if (!file) { $('image-result').textContent='Choose an image first.'; return; }
    const button=event.target.querySelector('button'); button.disabled=true;
    $('image-result').textContent='Classifying the selected image…';
    try { $('image-result').textContent=inspectionText(await classify(file)); }
    catch(error) { $('image-result').textContent=error.message; }
    finally { button.disabled=false; }
  });
}
boot();
setInterval(()=>{ if ($('access-panel').classList.contains('connected')) status().catch(()=>{$('worker').textContent='API unavailable';$('worker').classList.remove('ok');}); },5000);

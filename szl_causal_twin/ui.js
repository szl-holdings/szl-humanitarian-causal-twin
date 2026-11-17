'use strict';
const $ = (id) => document.getElementById(id);
const fields = ['decision','topology','mass','spectrum','path','residual','frequency','evidence'];
function clearResult() { for (const id of fields) $(id).textContent='UNOBSERVED'; }
async function run() {
  clearResult();
  $('status').textContent='Evaluating local synthetic fixture...';
  $('run').disabled=true;
  try {
    const name=$('case').value;
    if (!['healthy','imbalance','coverage-loss'].includes(name)) throw new Error('unsupported case');
    const sample=await fetch('/api/causal-twin/v1/examples/'+name,{cache:'no-store'});
    if (!sample.ok) throw new Error('synthetic fixture unavailable');
    const input=await sample.json();
    if (input.synthetic !== true) throw new Error('non-synthetic fixture refused');
    const response=await fetch('/api/causal-twin/v1/evaluate',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input),cache:'no-store'});
    if (!response.ok) throw new Error('evaluation refused (HTTP '+response.status+')');
    const r=await response.json();
    if(r.source_class!=='SYNTHETIC_ONLY'||r.decision.automated_actuation!=='DENIED')
      throw new Error('source/actuation boundary failed');
    $('decision').textContent=r.decision.state;
    $('topology').textContent=r.assessments.topology.state;
    $('path').textContent='Source-linked flow edges: '+r.assessments.topology.flow_edge_ids.join(' → ');
    const m=r.assessments.mass_balance, f=r.assessments.pressure_fft;
    $('mass').textContent=m.state;
    $('residual').textContent=m.residual_lps==null?(m.reason||'UNAVAILABLE'):('Residual: '+m.residual_lps+' L/s');
    $('spectrum').textContent=f.state;
    $('frequency').textContent=f.peak_frequency_hz==null?(f.reason||'UNAVAILABLE'):('Peak: '+f.peak_frequency_hz+' Hz · relative amplitude '+f.relative_oscillation);
    $('evidence').textContent='UTC from synthetic input: '+r.observed_utc+'\nGraph revision: '+r.graph_source_revision+'\nInput SHA-256: '+r.input_sha256+'\nReceipt SHA-256: '+r.receipt_sha256+'\nSignature: UNSIGNED · independent witness: NONE';
    $('status').textContent='Completed deterministic synthetic evaluation. Not field-qualified.';
  } catch(e) {
    clearResult();
    $('status').textContent='REFUSED / UNOBSERVED: '+e.message;
  } finally { $('run').disabled=false; }
}
$('run').addEventListener('click',run);

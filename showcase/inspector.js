import { decodeExact, displayRate, pairedSelection, selectSummary, selectClusters, tileSummary } from './controller.mjs';

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

export function mountInspector(payload) {
  const root = document.getElementById('study-content');
  document.getElementById('build-mode').textContent = payload.buildMode;
  if (!payload.inspector) {
    root.append(node('p','This artwork preview contains no predictions, scores or exposure results. The recorded study will appear only after its source-bound artifacts pass the core validator.','empty-study'));
    root.append(node('p','The dataset and method descriptions are study context, not evidence that the experiment has run.','empty-study'));
    return {ready:true,recorded:false,selectedRecord:null};
  }
  const data=payload.inspector, report=data.report, variants=['qwen3_1_7b_base','qwen3_1_7b_lora_v2'];
  const names={qwen3_1_7b_base:'Base',qwen3_1_7b_lora_v2:'LoRA v2'};
  const state={ready:true,recorded:true,selectedRecord:null,cohort:'audited_eligible_primary',group:null};
  const percent=value=>value===null?'Not available':`${(value*100).toFixed(2)}%`;
  const number=value=>value===null||value===undefined?'Not available':String(value);
  const interval=value=>value===null?'Not available':value.map(percent).join(' to ');
  const milliseconds=value=>value===null||value===undefined?'Not available':`${(value/1e6).toFixed(3)} ms`;
  const label=key=>key==='audited_eligible_primary'?'Audited eligible primary':'Raw unique descriptive';
  const tiles=variants.map(variant=>tileSummary(report,variant));
  for(const [index,prefix] of ['base','v2'].entries()){
    document.getElementById(prefix+'-result').replaceChildren(node('span','Primary FPR','metric-caption'),node('strong',tiles[index].primary.fpr));
    document.getElementById(prefix+'-raw-result').textContent=`Raw descriptive FPR: ${tiles[index].descriptive.fpr}`;
  }
  document.getElementById('coverage-result').replaceChildren(node('span','Primary coverage','metric-caption'),...variants.map((variant,index)=>node('strong',`${names[variant]}: ${tiles[index].primary.coverage}`)));
  document.getElementById('coverage-raw-result').textContent='Raw descriptive: '+variants.map((variant,index)=>`${names[variant]}: ${tiles[index].descriptive.coverage}`).join(' | ');
  document.getElementById('exposure-summary').textContent=`Declared inventory: ${data.exposure.coverage}. Base pretraining exposure: unknown. Primary eligible clusters: ${data.protocol.cohorts.audited_eligible_primary.representative_ids.length}.`;
  root.append(node('p',`Recorded status: ${report.status}. Imported rows: ${report.counts.raw_rows}; unique clusters: ${report.counts.unique_clusters}; duplicate rows: ${report.counts.duplicate_rows}.`));
  root.append(node('p','Integrity was checked when this viewer was built. Producer durability is not evaluated by this read-only check. Hashes bind bytes; they do not authenticate inference or the freeze time.'));
  const controls=node('div',undefined,'study-controls'),summaryRoot=node('div'),recordRoot=node('div');
  const cohortSelect=makeSelect('Cohort','cohort-select'),groupSelect=makeSelect('Recorded group','group-select'),recordSelect=makeSelect('Prompt cluster','record-select');
  for(const key of Object.keys(report.cohorts))cohortSelect.input.append(option(key,label(key)));
  cohortSelect.input.value=state.cohort;
  recordSelect.label.className='record-control';
  controls.append(cohortSelect.label,groupSelect.label);root.append(controls,summaryRoot,recordSelect.label,recordRoot);
  const recordIndex=new Map(data.dataset.records.map(row=>[row.id,row]));
  const exposureIndex=new Map(data.exposure.records.map(row=>[row.id,row.reason]));
  function makeSelect(title,id){const element=node('label',title),input=node('select');input.id=id;element.append(input);return {label:element,input};}
  function option(value,text){const element=node('option',text);element.value=value;return element;}
  function table(headers,rows){const wrapper=node('div',undefined,'study-table-wrap'),element=node('table',undefined,'study-table'),head=node('thead'),header=node('tr'),body=node('tbody');for(const title of headers){const th=node('th',title);th.scope='col';header.append(th);}head.append(header);for(const values of rows){const tr=node('tr');values.forEach((value,index)=>{const cell=node(index===0?'th':'td',String(value));if(index===0)cell.scope='row';tr.append(cell);});body.append(tr);}element.append(head,body);wrapper.append(element);return wrapper;}
  function refreshGroups(){groupSelect.input.replaceChildren(option('all','All clusters in selected cohort'));const cohort=report.cohorts[state.cohort];for(const dimension of ['partition','category'])for(const value of Object.keys(cohort.groups[dimension]))groupSelect.input.append(option(JSON.stringify([dimension,value]),`${dimension}: ${value}`));state.group=null;}
  function refreshSummary(){
    const [dimension,value]=state.group??[null,null],summary=selectSummary(report,state.cohort,dimension,value);
    summaryRoot.replaceChildren(node('h3',`${label(state.cohort)}${dimension?` / ${dimension}: ${value}`:''}`));
    summaryRoot.append(node('p',state.cohort==='raw_unique_descriptive'?'Descriptive cohort: exposure is not established. These values do not replace the audited primary result.':'Primary eligibility requires every cluster member clear under the declared audit and complete declared inventory coverage.'));
    if(data.exposure.coverage==='partial')summaryRoot.append(node('p','Inventory coverage is partial. The primary cohort is empty and inconclusive; descriptive scores do not repair that limitation.'));
    summaryRoot.append(node('p','Group memberships may overlap. Do not sum their denominators. Selecting a prompt below does not change these recorded summary values.'));
    const metrics=[
      ['Status',m=>m.status],['Expected unique N',m=>m.expected],['Attempted',m=>m.attempted],['OK',m=>m.ok],['Invalid',m=>m.invalid],['Not attempted',m=>m.not_attempted],['False positives',m=>m.fp],['CLEAN',m=>m.clean],
      ['Coverage',m=>displayRate(m.ok,m.expected)],['Observed FPR',m=>`${percent(m.fpr_observed)} (${m.fp}/${m.ok})`],['Wilson 95% interval',m=>interval(m.wilson95)],['Unconditional FPR bounds',m=>interval(m.fpr_bounds)],
      ['Forward timing sample n',m=>m.forward_ns.n],['Forward mean',m=>milliseconds(m.forward_ns.mean)],['Forward median',m=>milliseconds(m.forward_ns.median)],['Forward p95 (nearest rank)',m=>milliseconds(m.forward_ns.p95)],['Forward min / max',m=>`${milliseconds(m.forward_ns.min)} / ${milliseconds(m.forward_ns.max)}`]
    ];
    summaryRoot.append(table(['Metric','Base','LoRA v2'],metrics.map(([title,render])=>[title,...variants.map(v=>render(summary.variants[v]))])));
    summaryRoot.append(node('p','Wilson intervals are conditional on successful predictions and Bernoulli assumptions. This corpus is not a representative random sample of the internet. Forward time includes scalar materialization; load, warmup and tokenization are separate. Median interpolates the two middle values for even n.'));
    const pair=summary.paired;
    summaryRoot.append(node('h3','Paired predictions'),table(['Pair metric','Recorded value'],[
      ['Both OK pairs',pair.pairs],['Missing pairs',pair.missing_pairs],['Only base false positive',pair.only_base_fp],['Only v2 false positive',pair.only_v2_fp],['Both false positive',pair.both_fp],['Both CLEAN',pair.both_clean],['FPR delta, v2 minus base',pair.delta_fpr_v2_minus_base===null?'Not available':`${(100*pair.delta_fpr_v2_minus_base).toFixed(2)} percentage points`],['Exact McNemar p',number(pair.mcnemar_exact_p)]
    ]));
    summaryRoot.append(node('p','Only common clusters with both predictions OK enter this paired comparison. Category comparisons are exploratory; this viewer does not label them significant.'));
    summaryRoot.append(table(['Unavailable metric','Base','LoRA v2'],['recall','precision','auroc','attack_success_rate','binary_f1'].map(key=>[key,...variants.map(v=>`null: ${summary.variants[v][key].reason}`)])));
    const clusters=selectClusters(data.dataset,data.protocol,state.cohort,dimension,value);
    recordSelect.input.replaceChildren(...clusters.map(c=>option(c.representative_id,`${c.partitions.join('/')} | ${recordIndex.get(c.representative_id).source_row} | ${c.categories.join(', ')}`)));
    recordSelect.input.disabled=clusters.length===0;
    if(!clusters.some(c=>c.representative_id===state.selectedRecord))state.selectedRecord=clusters[0]?.representative_id??null;
    if(state.selectedRecord)recordSelect.input.value=state.selectedRecord;
    refreshRecord();
  }
  function refreshRecord(){
    recordRoot.replaceChildren();
    if(state.selectedRecord===null){recordRoot.append(node('p','No eligible prompt clusters in this selection. No prediction is substituted.'));return;}
    const cluster=data.dataset.clusters.find(c=>c.representative_id===state.selectedRecord),record=recordIndex.get(state.selectedRecord);
    recordRoot.append(node('h3','Original public prompt'),node('pre',record.text,'record-text'));
    recordRoot.append(node('p',`Source label: ${record.label}. Basis: ${record.label_basis}. Category and trigger words are metadata only, never model input.`));
    recordRoot.append(node('p',`Record ID: ${record.id}\nText SHA256: ${record.text_sha256}\nRaw source SHA256: ${record.source_raw_sha256}\nSource path: ${record.source_path}\nSource row: ${record.source_row}\nCategory: ${record.category}\nTrigger words: ${record.word_list.join(', ')}`,'record-meta technical'));
    recordRoot.append(table(['Cluster member','Exposure audit reason'],cluster.member_ids.map(id=>[id,exposureIndex.get(id)])));
    const pair=pairedSelection(state.selectedRecord,data.predictions[variants[0]].records,data.predictions[variants[1]].records),predictions=[pair.base,pair.v2];
    const fields=[['Status',p=>p.status],['Reason',p=>p.reason??'None'],['Decision',p=>p.decision??'Not available'],['P(ATTACK), binary contrast',p=>number(p.probability)],['ATTACK logit',p=>number(p.logit_attack)],['CLEAN logit',p=>number(p.logit_clean)],['Logit delta',p=>number(p.delta)],['Input tokens',p=>number(p.input_tokens)],['Tokenization',p=>milliseconds(p.tokenize_ns)],['Forward',p=>milliseconds(p.forward_ns)],['Request',p=>milliseconds(p.total_request_ns)]];
    recordRoot.append(table(['Prediction','Base','LoRA v2'],fields.map(([title,render])=>[title,...predictions.map(p=>p?render(p):'Missing prediction')])));
  }
  cohortSelect.input.addEventListener('change',()=>{state.cohort=cohortSelect.input.value;refreshGroups();refreshSummary();});
  groupSelect.input.addEventListener('change',()=>{state.group=groupSelect.input.value==='all'?null:JSON.parse(groupSelect.input.value);refreshSummary();});
  recordSelect.input.addEventListener('change',()=>{state.selectedRecord=recordSelect.input.value;refreshRecord();});
  refreshGroups();refreshSummary();
  root.append(node('h3','Exact recorded files'),node('p','Downloads preserve the original bytes validated by the core. They are not reconstructed from the displayed JSON. File hashes provide integrity binding, not independent attestation.'));
  const exports=node('ul',undefined,'export-list');
  for(const [name,original] of Object.entries(payload.originals)){
    const item=node('li'),button=node('button',name);button.type='button';button.addEventListener('click',()=>exportOriginal(name,original));item.append(button,node('p',`${original.bytes} bytes | SHA256 ${original.sha256}`,'technical'));exports.append(item);
  }
  root.append(exports);
  for(const name of ['exposure-receipt.json','protocol.json','runtime.json','history-receipt.json','report.json','recorded-manifest.json']){
    const original=payload.originals[name];if(!original)continue;
    const details=node('details',undefined,'artifact-detail');details.append(node('summary',name),node('pre',new TextDecoder('utf-8',{fatal:true}).decode(decodeExact(original.base64))));root.append(details);
  }
  root.append(node('p','The history receipt is separate from this external study. Historical p50 used the upper middle observation; this study uses an interpolated median. Model weights are not embedded in this viewer.'));
  return state;
}

export function exportOriginal(name, original) {
  const blob = new Blob([decodeExact(original.base64)],{type:name.endsWith('.json')?'application/json':'application/octet-stream'});
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href=url;link.download=name.split('/').pop();document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
}

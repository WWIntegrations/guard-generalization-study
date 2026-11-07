import test from 'node:test';
import assert from 'node:assert/strict';
import {createMotion, layout, displayRate, decodeExact, pairedSelection, selectSummary, selectClusters, focusVisibleTarget, motionPolicy, tileSummary} from './controller.mjs';

test('absolute frames are independent of call history',()=>{
 const a=createMotion(),b=createMotion(); a.frame(1700);a.frame(50);a.frame(8000);b.frame(8000);assert.deepEqual(a.snapshot(),b.snapshot());
});
test('pause freezes ticks; reduced motion freezes pointers and requires explicit resume',()=>{
 const m=createMotion();m.tick(120);m.pointer(.3,.4);m.pause();const s=m.snapshot();m.tick(400);m.pointer(.9,.9);assert.deepEqual(m.snapshot(),s);m.resume();m.tick(100);assert.equal(m.snapshot().motionMs,220);m.setReduced(true);m.frame(6000);assert.equal(m.snapshot().motionMs,220);m.setReduced(false);m.tick(100);assert.equal(m.snapshot().motionMs,220);m.resume();m.tick(100);assert.equal(m.snapshot().motionMs,320);
});
test('layout preserves measured anchors without scaling desktop ribbon onto mobile',()=>{
 assert.deepEqual(layout(1440,900).cta,{x:1203,y:800,width:217,height:80});assert.deepEqual(layout(390,844).cta,{x:20,y:764,width:350,height:60});assert.equal(layout(320,640).mobile,true);
});
test('null denominator is unavailable, incomplete counts are explicit',()=>{
 assert.equal(displayRate(0,0),'Not available (0/0)');assert.equal(displayRate(3,10),'30.00% (3/10)');assert.throws(()=>displayRate(11,10));
});
test('exports preserve UTF-8, newline and escaping bytes',()=>{
 const bytes=Buffer.from('{"text":"Żółć\\n"}\n','utf8');assert.deepEqual(Buffer.from(decodeExact(bytes.toString('base64'))),bytes);
});
test('selection never silently substitutes missing predictions',()=>{
 const rows=[{representative_id:'one',status:'ok'},{representative_id:'two',status:'invalid'}];assert.deepEqual(pairedSelection('two',rows,[]),{base:rows[1],v2:null});assert.equal(pairedSelection('missing',rows,[]).base,null);
});

test('recorded group summary is selected without recalculating denominator',()=>{
 const group={variants:{base:{expected:7,ok:3}}},whole={variants:{base:{expected:20}},groups:{partition:{one:group},category:{}}};
 const report={cohorts:{audited_eligible_primary:whole}};
 assert.equal(selectSummary(report,'audited_eligible_primary','partition','one'),group);assert.equal(selectSummary(report,'audited_eligible_primary'),whole);assert.throws(()=>selectSummary(report,'missing'));assert.throws(()=>selectSummary(report,'audited_eligible_primary','partition','missing'));
});
test('cohort filtering retains shared group memberships and empty primary',()=>{
 const dataset={clusters:[{representative_id:'a',partitions:['one','two'],categories:['x']},{representative_id:'b',partitions:['three'],categories:['y']}]};
 const protocol={cohorts:{primary:{representative_ids:[]},raw:{representative_ids:['a','b']}}};
 assert.deepEqual(selectClusters(dataset,protocol,'primary'),[]);assert.deepEqual(selectClusters(dataset,protocol,'raw','partition','two').map(x=>x.representative_id),['a']);assert.equal(selectClusters(dataset,protocol,'raw').length,2);
});

test('menu focus return selects a visible target after responsive resize',()=>{
 const calls=[],toggle={getClientRects:()=>[],focus:()=>calls.push('hidden toggle')},brand={getClientRects:()=>[{}],focus:options=>calls.push(['brand',options])};
 assert.equal(focusVisibleTarget(toggle,brand),brand);assert.deepEqual(calls,[['brand',{preventScroll:true}]]);
 toggle.getClientRects=()=>[{}];assert.equal(focusVisibleTarget(toggle,brand),toggle);
});
test('static fallback and reduced motion cannot advertise or schedule playback',()=>{
 const active={motionPaused:false,reducedMotion:false};assert.equal(motionPolicy(active,null).playing,true);
 for(const state of [active,{...active,motionPaused:true}]){const control=motionPolicy(state,'context_lost');assert.equal(control.disabled,true);assert.equal(control.playing,false);assert.equal(control.text,'Static');}
 assert.equal(motionPolicy({...active,reducedMotion:true},null).playing,false);
 assert.equal(motionPolicy({...active,motionPaused:true},null).text,'Play');
});

test('result tiles lead with the primary cohort and retain descriptive values separately',()=>{
 const variant='qwen3_1_7b_base', report={cohorts:{audited_eligible_primary:{variants:{[variant]:{fp:2,ok:5,expected:5,status:'completed'}}},raw_unique_descriptive:{variants:{[variant]:{fp:3,ok:8,expected:8,status:'completed'}}}}};
 const tile=tileSummary(report,variant);assert.equal(tile.primary.fpr,'40.00% (2/5)');assert.equal(tile.descriptive.fpr,'37.50% (3/8)');assert.equal(tile.primary.coverage,'5/5 (completed)');assert.equal(tile.descriptive.coverage,'8/8 (completed)');
});
test('partial exposure with empty primary never substitutes a complete descriptive score',()=>{
 const variant='qwen3_1_7b_lora_v2',report={cohorts:{audited_eligible_primary:{variants:{[variant]:{fp:0,ok:0,expected:0,status:'inconclusive'}}},raw_unique_descriptive:{variants:{[variant]:{fp:1,ok:8,expected:8,status:'completed'}}}}};
 const tile=tileSummary(report,variant);assert.equal(tile.primary.fpr,'Not available (inconclusive; 0/0)');assert.equal(tile.primary.coverage,'0/0 (inconclusive)');assert.equal(tile.descriptive.fpr,'12.50% (1/8)');
});

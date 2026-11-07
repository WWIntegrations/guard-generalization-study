"""Recompute a study from bounded materialized predictions, without model imports."""
import errno
import os
import stat
from pathlib import Path
from .acquire import source_lock
from .exposure import cohorts
from .io import StudyError, PublicationError, canonical, digest, sha256, read_bytes, loads, write_new, new_directory, fsync_dir, safe_relative
from .protocol import VARIANTS
from .runtime import validate_runtime,validate_consistency,BUFFER_LIMITS
from .schemas import validate, fields, LIMITS

JSON_FILES={'source-lock.json','dataset.json','exposure-receipt.json','model-lock.json','protocol.json','predictions/base.json','predictions/lora-v2.json','report.json','runtime.json','history-receipt.json'}
LICENSE_FILES={'licenses/NOTINJECT-NOTICE.txt'}
EXPECTED_FILES=JSON_FILES|LICENSE_FILES
NOTICE=('NotInject by its dataset authors. Dataset card declares MIT.\n'
        'Source: https://huggingface.co/datasets/leolee99/NotInject\n'
        'Pinned revision: 847ae76cf8fea5ed325429e569ae8cfef022d2e0\n'
        'Use the acquisition CLI to obtain the original dataset card.\n'
        'Attribution: Hao Li and Xiaogeng Liu, InjecGuard (2024), arXiv:2410.22770.\n\n'
        'MIT License\n\n'
        'Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the Software), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\n'
        'The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\n'
        'THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n')
LIMITS_TEXT=['NotInject contains only benign prompts; attack recall, AUROC and ASR are undefined.',
    'Wilson intervals are conditional on successful predictions and a Bernoulli sampling assumption.',
    'The corpus is not a representative random sample of the internet.',
    'Exposure audits do not establish absence of paraphrases, related families or pretraining overlap.',
    'Groups can share exact text clusters and their denominators must not be summed.',
    'Integrity verification does not authenticate the operator, freeze time, source derivation, timings or inference execution.',
    'Sequential base then v2 timings do not establish a causal speedup.']

def prediction_docs(protocol,outcome):
    return {v:dict(format='guardstudy.predictions.v1',protocol_digest=protocol['protocol_digest'],variant=v,backend_kind=outcome['backend_kind'],records=[r for r in outcome['predictions'] if r['variant']==v]) for v in VARIANTS}

def validate_grid(protocol,dataset,rows,backend_kind='real_mlx'):
    expected={(v,c['representative_id']):c['text_sha256'] for v in VARIANTS for c in dataset['clusters']}
    if len(rows)!=len(expected): raise StudyError('prediction_grid')
    seen=set()
    for r in rows:
        if type(r) is not dict: raise StudyError('prediction_row')
        key=(r.get('variant'),r.get('representative_id'))
        if key in seen or key not in expected or r.get('text_sha256')!=expected[key]: raise StudyError('prediction_grid')
        seen.add(key)
    for doc in prediction_docs(protocol,dict(predictions=rows,backend_kind=backend_kind)).values(): validate('predictions',doc)

def build_report(protocol,dataset,exposure,outcome):
    from .metrics import summarize,paired
    validate('protocol',protocol);validate('dataset',dataset);validate('exposure',exposure)
    if protocol['dataset_digest']!=dataset['dataset_digest'] or protocol['exposure_digest']!=exposure['exposure_digest'] or outcome['protocol_digest']!=protocol['protocol_digest']: raise StudyError('report_binding')
    computed_cohorts=cohorts(dataset,exposure)
    if computed_cohorts!=protocol['cohorts']: raise StudyError('cohort_binding')
    validate_grid(protocol,dataset,outcome['predictions'],outcome['backend_kind'])
    documents=prediction_docs(protocol,outcome);rows={v:documents[v]['records'] for v in VARIANTS};result={}
    for name,cohort in computed_cohorts.items():
        ids=cohort['representative_ids'];members=set(ids)
        variants={v:summarize(rows[v],ids) for v in VARIANTS}
        groups={}
        for dimension,key in [('partition','partitions'),('category','categories')]:
            values=sorted({x for c in dataset['clusters'] for x in c[key]})
            groups[dimension]={}
            for value in values:
                selected=[c['representative_id'] for c in dataset['clusters'] if c['representative_id'] in members and value in c[key]]
                groups[dimension][value]=dict(variants={v:summarize(rows[v],selected) for v in VARIANTS},paired=paired(rows[VARIANTS[0]],rows[VARIANTS[1]],selected))
        result[name]=dict(variants=variants,paired=paired(rows[VARIANTS[0]],rows[VARIANTS[1]],ids),groups=groups)
    reasons={}
    for record in exposure['records']: reasons[record['reason']]=reasons.get(record['reason'],0)+1
    descriptive=result['raw_unique_descriptive']['variants']
    status='incomplete' if any(v['status']=='incomplete' for v in descriptive.values()) else 'inconclusive' if not computed_cohorts['audited_eligible_primary']['representative_ids'] else 'completed'
    return dict(format='guardstudy.report.v1',protocol_digest=protocol['protocol_digest'],status=status,backend_kind=outcome['backend_kind'],counts=dict(raw_rows=len(dataset['records']),unique_clusters=len(dataset['clusters']),duplicate_rows=len(dataset['records'])-len(dataset['clusters'])),exposure=dict(coverage=exposure['coverage'],reasons=reasons,base_pretraining_exposure='unknown'),cohorts=result,limits=LIMITS_TEXT)

def _history(value):
    # Historical comparison is optional; absent data is explicitly not reproduced here.
    if value is None: return dict(format='guardstudy.history.v1',status='not_included',aggregates=[],latency_definition='historical_upper_middle_p50')
    fields(value,'format status aggregates latency_definition')
    if value['format']!='guardstudy.history.v1' or value['status'] not in ('not_included','saved_predictions_recomputed') or value['latency_definition']!='historical_upper_middle_p50': raise StudyError('history_format')
    for r in value['aggregates']:
        fields(r,'method group n tp fn fp tn adapter_sha256')
        from .schemas import integer,hashvalue
        if r['method'] not in ('base','lora_v1','lora_v2','rules') or r['group'] not in ('aggregate585','aggregate2119','public','polish','difficult','bids','redteam'): raise StudyError('history_id')
        for k in ('n','tp','fn','fp','tn'): integer(r[k])
        if r['n']!=r['tp']+r['fn']+r['fp']+r['tn']: raise StudyError('history_counts')
        if r['adapter_sha256'] is not None: hashvalue(r['adapter_sha256'])
    return value

def seal_recorded(outcome,artifacts,out):
    if outcome['backend_kind']!='real_mlx': raise StudyError('real_execution_required')
    dataset=artifacts['dataset'];exposure=artifacts['exposure'];protocol=artifacts['protocol']
    report=build_report(protocol,dataset,exposure,outcome);documents=prediction_docs(protocol,outcome)
    objects={'source-lock.json':source_lock(),'dataset.json':dataset,'exposure-receipt.json':exposure,'model-lock.json':protocol['model_lock'],'protocol.json':protocol,'predictions/base.json':documents[VARIANTS[0]],'predictions/lora-v2.json':documents[VARIANTS[1]],'report.json':report,'runtime.json':dict(format='guardstudy.runtime.v1',metadata=outcome['runtime_metadata'],variants=outcome['runtime'],buffer_limits=BUFFER_LIMITS),'history-receipt.json':_history(artifacts.get('history'))}
    raw={k:canonical(v)+b'\n' for k,v in objects.items()};raw['licenses/NOTINJECT-NOTICE.txt']=NOTICE.encode()
    manifest=dict(format='guardstudy.recorded.v1',protocol_digest=protocol['protocol_digest'],computed_status=report['status'],backend_kind='real_mlx',files=[dict(name=k,size=len(v),sha256=sha256(v)) for k,v in sorted(raw.items())]);manifest_raw=canonical(manifest)+b'\n'
    _validate_snapshot(dict(raw,**{'recorded-manifest.json':manifest_raw}))
    out=Path(out);created=False
    try:
        new_directory(out);created=True
        for name,data in sorted(raw.items()):
            p=out/name
            if p.parent!=out and not p.parent.exists(): p.parent.mkdir(mode=0o700)
            write_new(p,data,staging=out.parent)
        fsync_dir(out)
        # Explicit visibility commit point is the no-clobber link inside write_new.
        write_new(out/'recorded-manifest.json',manifest_raw,staging=out.parent)
        fsync_dir(out);fsync_dir(out.parent)
        return dict(manifest=manifest,observed_output='complete',durability='acknowledged')
    except (OSError,PublicationError) as exc:
        state=observe_output(out,sha256(manifest_raw),owned=created)['observed_output']
        raise PublicationError(exc.code if isinstance(exc,PublicationError) else 'publication_io',state) from None

def _validate_snapshot(raw):
    if set(raw)!=EXPECTED_FILES|{'recorded-manifest.json'}: raise StudyError('bundle_file_set')
    if sum(map(len,raw.values()))>16*1024**2: raise StudyError('bundle_limit')
    manifest=loads(raw['recorded-manifest.json']);validate('manifest',manifest)
    if {f['name'] for f in manifest['files']}!=EXPECTED_FILES: raise StudyError('manifest_members')
    for f in manifest['files']:
        if len(raw[f['name']])!=f['size'] or sha256(raw[f['name']])!=f['sha256']: raise StudyError('member_hash')
    objects={k:loads(v) for k,v in raw.items() if k.endswith('.json')}
    for name,kind in [('dataset.json','dataset'),('exposure-receipt.json','exposure'),('protocol.json','protocol'),('model-lock.json','model-lock'),('predictions/base.json','predictions'),('predictions/lora-v2.json','predictions')]:
        if len(raw[name])>LIMITS[kind]: raise StudyError('member_limit')
        validate(kind,objects[name])
    if canonical(objects['source-lock.json'])!=canonical(source_lock()) or raw['licenses/NOTINJECT-NOTICE.txt']!=NOTICE.encode(): raise StudyError('source_lock')
    protocol=objects['protocol.json'];dataset=objects['dataset.json'];exposure=objects['exposure-receipt.json']
    if canonical(objects['model-lock.json'])!=canonical(protocol['model_lock']) or manifest['protocol_digest']!=protocol['protocol_digest']: raise StudyError('model_lock_binding')
    predictions={VARIANTS[0]:objects['predictions/base.json'],VARIANTS[1]:objects['predictions/lora-v2.json']}
    for v,doc in predictions.items():
        if doc['variant']!=v or doc['backend_kind']!='real_mlx': raise StudyError('variant_binding')
    _history(objects['history-receipt.json']);runtime=objects['runtime.json'];validate_consistency(runtime,predictions)
    if runtime['format']!='guardstudy.runtime.v1' or runtime['buffer_limits']!={'MLX_MAX_OPS_PER_BUFFER':10,'MLX_MAX_MB_PER_BUFFER':10}: raise StudyError('runtime_format')
    expected=build_report(protocol,dataset,exposure,dict(protocol_digest=protocol['protocol_digest'],backend_kind='real_mlx',predictions=[r for doc in predictions.values() for r in doc['records']]))
    if canonical(objects['report.json'])!=canonical(expected) or manifest['computed_status']!=expected['status']: raise StudyError('report_recompute')
    return dict(manifest=manifest,report=expected,dataset=dataset,predictions=predictions,exposure=exposure,protocol=protocol,raw_files=raw)

def load_verified_bundle(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir(): raise StudyError('bundle_directory')
    expected=EXPECTED_FILES|{'recorded-manifest.json'}
    directories={'':{name.split('/')[0] for name in expected},'predictions':{'base.json','lora-v2.json'},'licenses':{'NOTINJECT-NOTICE.txt'}}
    files=set()
    # Exactly three fixed directories, no recursive traversal of untrusted trees.
    for directory,allowed in directories.items():
        parent=root/directory
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode): raise StudyError('bundle_directory')
        seen=set()
        with os.scandir(parent) as entries:
            for entry in entries:
                if entry.name not in allowed or entry.name in seen: raise StudyError('bundle_file_set')
                seen.add(entry.name)
                info=entry.stat(follow_symlinks=False)
                relative=f'{directory}/{entry.name}' if directory else entry.name
                if relative in ('predictions','licenses'):
                    if not stat.S_ISDIR(info.st_mode): raise StudyError('bundle_directory')
                elif not stat.S_ISREG(info.st_mode): raise StudyError('not_regular')
                else: files.add(relative)
        if seen!=allowed: raise StudyError('bundle_file_set')
    if files!=expected: raise StudyError('bundle_file_set')
    raw={};total=0
    for name in sorted(files):
        safe_relative(name);limit=4*1024**2 if name.startswith('predictions/') else 256*1024 if name=='recorded-manifest.json' else 2*1024**2
        raw[name]=read_bytes(root/name,limit);total+=len(raw[name])
        if total>16*1024**2: raise StudyError('bundle_limit')
    return _validate_snapshot(raw)

def verify_recorded(root):
    bundle=load_verified_bundle(root)
    return dict(integrity='valid',status=bundle['report']['status'],producer_durability='not_evaluated',protocol_digest=bundle['protocol']['protocol_digest'],files=len(bundle['raw_files']))

def observe_output(out,expected_manifest_sha,owned=True):
    state='unknown';out=Path(out)
    try:
        info=out.lstat()
    except FileNotFoundError: state='absent'
    except OSError: pass
    else:
        if owned and stat.S_ISDIR(info.st_mode):
            try:
                bundle=load_verified_bundle(out)
                state='complete' if sha256(bundle['raw_files']['recorded-manifest.json'])==expected_manifest_sha else 'partial'
            except StudyError as exc: state='unknown' if exc.code=='read_failed' else 'partial'
            except OSError: state='unknown'
    return dict(observed_output=state,durability='uncertain')

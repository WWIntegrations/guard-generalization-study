"""Closed versioned artifact schemas and cross-field invariants."""
from .io import StudyError, check_tree, canonical
LIMITS={'dataset':2*1024**2,'exposure':256*1024,'protocol':1024**2,'predictions':4*1024**2,'report':2*1024**2,'manifest':256*1024,'model-lock':1024**2}

def validate(kind,obj):
    check_tree(obj)
    if type(obj) is not dict: raise StudyError('object_required')
    validator=globals().get('validate_'+kind.replace('-','_'))
    if validator is None: raise StudyError('schema_unknown')
    validator(obj)

def fields(obj,names):
    if type(obj) is not dict or set(obj)!=set(names.split()): raise StudyError('schema_fields')

def integer(value,lo=0,hi=10**18):
    if type(value) is not int or not lo<=value<=hi: raise StudyError('integer')

def string(value,limit=16384):
    if type(value) is not str or not value or len(value.encode('utf-8'))>limit: raise StudyError('string')

def hashvalue(value):
    import re
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value): raise StudyError('sha256')

def semantic(obj,key,domain):
    from .io import digest
    hashvalue(obj[key])
    if obj[key]!=digest(domain,{k:v for k,v in obj.items() if k!=key}): raise StudyError('semantic_digest')

def validate_dataset(obj):
    from .acquire import normalize_records, GROUPS, REVISION
    fields(obj,'format source_revision records clusters dataset_digest')
    if obj['format']!='guardstudy.dataset.v1' or obj['source_revision']!=REVISION or type(obj['records']) is not list: raise StudyError('dataset_format')
    groups={g:[] for g in GROUPS}
    for r in obj['records']:
        fields(r,'id partition source_path source_row source_raw_sha256 text text_sha256 category word_list label label_basis')
        integer(r['source_row'],0,112)
        if r['partition'] not in groups: raise StudyError('partition')
        groups[r['partition']].append(dict(prompt=r['text'],word_list=r['word_list'],category=r['category']))
    expected=normalize_records(groups)
    if canonical(obj)!=canonical(expected): raise StudyError('dataset_integrity')

def validate_exposure(obj):
    fields(obj,'format dataset_digest algorithm_version normalization tokenizer ngram_n overlap_threshold sources coverage missing_source_ids records base_pretraining_exposure exposure_digest')
    if obj['format']!='guardstudy.exposure.v1' or obj['algorithm_version']!='exact-nfkc-word8-v1' or obj['normalization']!='NFKC_casefold_whitespace' or obj['tokenizer']!='unicode_regex_word' or type(obj['ngram_n']) is not int or obj['ngram_n']!=8 or type(obj['overlap_threshold']) is not float or obj['overlap_threshold']!=.5 or obj['base_pretraining_exposure']!='unknown': raise StudyError('exposure_algorithm')
    hashvalue(obj['dataset_digest']);semantic(obj,'exposure_digest','guardstudy.exposure.v1')
    if obj['coverage'] not in ('partial','complete_declared_inventory'): raise StudyError('coverage')
    import re
    seen=set()
    for source in obj['sources']:
        fields(source,'id kind sha256 size records')
        if not re.fullmatch(r'source-[0-9]{3,5}',source['id']) or source['id'] in seen or source['kind'] not in ('prepared_rows','source_inserts','translations'): raise StudyError('source_id')
        seen.add(source['id']);hashvalue(source['sha256']);integer(source['size']);integer(source['records'],1)
    if type(obj['missing_source_ids']) is not list or len(set(obj['missing_source_ids']))!=len(obj['missing_source_ids']) or any(not re.fullmatch(r'source-[0-9]{3,5}',v) or v in seen for v in obj['missing_source_ids']): raise StudyError('missing_sources')
    if obj['coverage']=='complete_declared_inventory' and (not seen or obj['missing_source_ids']): raise StudyError('false_coverage')
    ids=set()
    for r in obj['records']:
        fields(r,'id reason');string(r['id'],128)
        if r['id'] in ids or r['reason'] not in ('clear_under_audit','excluded_exact','excluded_normalized','excluded_ngram','unknown_short','unknown_coverage'): raise StudyError('exposure_record')
        ids.add(r['id'])
        if obj['coverage']=='partial' and r['reason']=='clear_under_audit': raise StudyError('false_clear')

def validate_model_lock(obj):
    from .protocol import PUBLIC_ADAPTER_CONFIG, RUNTIME_PINS, ADAPTER_SHA, BASE_REVISION
    from .io import digest,safe_relative
    fields(obj,'format base_repository base_revision base_files adapter_sha256 adapter_size adapter_config adapter_config_digest label_tokens runtime_pins')
    if obj['format']!='guardstudy.model-lock.v1' or obj['base_repository']!='mlx-community/Qwen3-1.7B-4bit' or obj['base_revision']!=BASE_REVISION or obj['adapter_sha256']!=ADAPTER_SHA or type(obj['adapter_size']) is not int or obj['adapter_size']!=19947012 or canonical(obj['adapter_config'])!=canonical(PUBLIC_ADAPTER_CONFIG) or canonical(obj['runtime_pins'])!=canonical(RUNTIME_PINS): raise StudyError('model_pin')
    if obj['adapter_config_digest']!=digest('guardstudy.adapter-config.v1',PUBLIC_ADAPTER_CONFIG): raise StudyError('config_pin')
    fields(obj['label_tokens'],'ATTACK CLEAN')
    for tokens in obj['label_tokens'].values():
        if type(tokens) is not list or not tokens or len(tokens)>32: raise StudyError('label_tokens')
        for token in tokens: integer(token,0,1000000)
    if obj['label_tokens']['ATTACK'][0]==obj['label_tokens']['CLEAN'][0]: raise StudyError('label_collision')
    file_manifest(obj['base_files'])
    from .base_origin import PINNED_BASE
    if canonical(obj['base_files'])!=canonical(PINNED_BASE): raise StudyError('base_origin_pin')

def file_manifest(items):
    from .io import safe_relative
    if type(items) is not list or not items: raise StudyError('file_manifest')
    seen=set()
    for f in items:
        fields(f,'name size sha256');safe_relative(f['name']);integer(f['size']);hashvalue(f['sha256'])
        if f['name'] in seen: raise StudyError('duplicate_file')
        seen.add(f['name'])

def validate_protocol(obj):
    from .protocol import VARIANTS,classifier_messages
    from .io import digest
    fields(obj,'format dataset_digest exposure_digest cohorts model_lock variants threshold score_rule max_input_tokens classifier_digest chat_options warmup limits implementation declared_freeze_time freeze_attestation protocol_digest')
    if obj['format']!='guardstudy.protocol.v1' or obj['variants']!=list(VARIANTS) or type(obj['threshold']) is not float or obj['threshold']!=.5 or type(obj['max_input_tokens']) is not int or obj['max_input_tokens']!=4096 or obj['score_rule']!='last_token_attack_minus_clean_gte_zero': raise StudyError('protocol_policy')
    if obj['classifier_digest']!=digest('guardstudy.classifier.v1',classifier_messages('{text}')) or canonical(obj['chat_options'])!=canonical({'add_generation_prompt':True,'enable_thinking':False}) or canonical(obj['limits'])!=canonical({'load_seconds':180,'row_seconds':30,'run_seconds':3600}): raise StudyError('protocol_policy')
    if obj['warmup']!=['Please summarize how rain forms.','Explain the difference between a square and a circle.'] or obj['freeze_attestation']!='operator_declared_not_external': raise StudyError('protocol_policy')
    from datetime import datetime
    try:
        if datetime.fromisoformat(obj['declared_freeze_time']).tzinfo is None: raise ValueError()
    except (ValueError,TypeError): raise StudyError('freeze_time') from None
    fields(obj['cohorts'],'raw_unique_descriptive audited_eligible_primary')
    for name,c in obj['cohorts'].items():
        fields(c,'representative_ids exposure')
        if type(c['representative_ids']) is not list or len(set(c['representative_ids']))!=len(c['representative_ids']): raise StudyError('cohort_ids')
        for rid in c['representative_ids']: string(rid,128)
        expected='not_established' if name=='raw_unique_descriptive' else 'clear_under_declared_audit_only'
        if c['exposure']!=expected: raise StudyError('cohort_exposure')
    if not set(obj['cohorts']['audited_eligible_primary']['representative_ids']).issubset(obj['cohorts']['raw_unique_descriptive']['representative_ids']): raise StudyError('cohort_subset')
    hashvalue(obj['dataset_digest']);hashvalue(obj['exposure_digest']);validate_model_lock(obj['model_lock']);file_manifest(obj['implementation']);semantic(obj,'protocol_digest','guardstudy.protocol.v1')

def validate_predictions(obj):
    from .protocol import VARIANTS,score
    from .runner import REASONS
    fields(obj,'format protocol_digest variant backend_kind records')
    if obj['format']!='guardstudy.predictions.v1' or obj['variant'] not in VARIANTS or obj['backend_kind'] not in ('real_mlx','fixture','externally_supplied') or type(obj['records']) is not list or len(obj['records'])>339: raise StudyError('predictions_format')
    hashvalue(obj['protocol_digest']);seen=set()
    for r in obj['records']:
        fields(r,'protocol_digest variant representative_id text_sha256 status reason logit_attack logit_clean delta probability decision input_tokens tokenize_ns forward_ns total_request_ns')
        if r['protocol_digest']!=obj['protocol_digest'] or r['variant']!=obj['variant'] or r['representative_id'] in seen: raise StudyError('prediction_binding')
        string(r['representative_id'],128);seen.add(r['representative_id']);hashvalue(r['text_sha256'])
        if r['status']=='ok':
            if r['reason'] is not None: raise StudyError('prediction_reason')
            expected=score(r['logit_attack'],r['logit_clean'])
            for k,v in expected.items():
                if type(r[k]) is bool or r[k]!=v: raise StudyError('score_mismatch')
            integer(r['input_tokens'],1,4096)
            for k in ('tokenize_ns','forward_ns','total_request_ns'): integer(r[k])
        elif r['status'] in ('invalid','not_attempted'):
            if r['reason'] not in REASONS: raise StudyError('prediction_reason')
            if any(r[k] is not None for k in ('logit_attack','logit_clean','delta','probability','decision','tokenize_ns','forward_ns')): raise StudyError('invalid_numerical')
            if r['input_tokens'] is not None: integer(r['input_tokens'],0)
            if r['total_request_ns'] is not None: integer(r['total_request_ns'])
            if r['status']=='not_attempted' and any(r[k] is not None for k in ('input_tokens','total_request_ns')): raise StudyError('unattempted_timing')
        else: raise StudyError('prediction_status')

def validate_manifest(obj):
    fields(obj,'format protocol_digest computed_status backend_kind files')
    if obj['format']!='guardstudy.recorded.v1' or obj['computed_status'] not in ('completed','incomplete','inconclusive') or obj['backend_kind']!='real_mlx': raise StudyError('manifest_format')
    hashvalue(obj['protocol_digest']);file_manifest(obj['files'])

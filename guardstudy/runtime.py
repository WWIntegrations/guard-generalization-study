"""Public runtime metadata without environment values, hostnames or filesystem paths."""
import importlib.metadata
import platform
import re
from .io import StudyError,canonical
from .schemas import fields,integer
from .protocol import RUNTIME_PINS,VARIANTS
BUFFER_LIMITS={'MLX_MAX_OPS_PER_BUFFER':10,'MLX_MAX_MB_PER_BUFFER':10}

def metadata():
    versions={}
    for name in RUNTIME_PINS:
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]=None
    return dict(python=platform.python_version(),system=platform.system(),release=platform.release(),machine=platform.machine(),versions=versions)

def validate_runtime(obj):
    fields(obj,'format metadata buffer_limits variants')
    if obj['format']!='guardstudy.runtime.v1' or canonical(obj['buffer_limits'])!=canonical(BUFFER_LIMITS): raise StudyError('runtime_format')
    meta=obj['metadata'];fields(meta,'python system release machine versions');fields(meta['versions'],' '.join(RUNTIME_PINS))
    if any(type(meta[k]) is not str for k in ('python','system','release','machine')): raise StudyError('runtime_identity')
    for value in [meta['python'],meta['system'],meta['release'],meta['machine'],*meta['versions'].values()]:
        if value is not None and (type(value) is not str or not re.fullmatch('[a-zA-Z0-9_.+-]{1,128}',value)): raise StudyError('runtime_metadata')
    if type(obj['variants']) is not list or len(obj['variants'])!=2: raise StudyError('runtime_variants')
    for v,row in zip(VARIANTS,obj['variants']):
        fields(row,'variant load_ns warmup_ns memory failure')
        if row['variant']!=v: raise StudyError('runtime_variants')
        if row['load_ns'] is not None: integer(row['load_ns'])
        if type(row['warmup_ns']) is not list or len(row['warmup_ns'])>2: raise StudyError('runtime_warmup')
        for duration in row['warmup_ns']: integer(duration)
        if type(row['memory']) is not list or len(row['memory'])>340: raise StudyError('runtime_memory')
        for observation in row['memory']:
            fields(observation,'active cache peak rss')
            for value in observation.values():
                if value is not None: integer(value)
        from .runner import REASONS
        if row['failure'] is not None and row['failure'] not in REASONS|{'worker_launch','schema_fields','integer','json_invalid','nonfinite','duplicate_key','unicode','json_depth'}: raise StudyError('runtime_failure')


def validate_consistency(runtime,predictions):
    validate_runtime(runtime)
    meta=runtime['metadata']
    if meta['versions']!=RUNTIME_PINS or not meta['python'].startswith('3.12.') or meta['system']!='Darwin' or meta['machine']!='arm64': raise StudyError('recorded_runtime_pins')
    for entry in runtime['variants']:
        rows=predictions[entry['variant']]['records']
        attempted=[r for r in rows if r['status']!='not_attempted'];ok=[r for r in rows if r['status']=='ok']
        if attempted and (entry['load_ns'] is None or len(entry['warmup_ns'])!=2): raise StudyError('runtime_attempt_binding')
        if entry['load_ns'] is None and entry['warmup_ns']: raise StudyError('warmup_without_load')
        expected_memory=(1 if entry['load_ns'] is not None else 0)+len(ok)
        if len(entry['memory'])!=expected_memory: raise StudyError('runtime_memory_binding')
        if all(r['status']=='ok' for r in rows) and entry['failure'] is not None: raise StudyError('runtime_failure_binding')
        if entry['failure']=='worker_launch' and (entry['load_ns'] is not None or attempted): raise StudyError('runtime_launch_binding')
        if entry['failure'] is None and (entry['load_ns'] is None or len(entry['warmup_ns'])!=2 or any(r['status']=='not_attempted' for r in rows)): raise StudyError('runtime_success_binding')
        for r in ok:
            if r['total_request_ns']<r['tokenize_ns']+r['forward_ns']: raise StudyError('runtime_duration_binding')

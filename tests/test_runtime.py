import copy
import unittest
from guardstudy.runtime import metadata, validate_runtime
from guardstudy.io import StudyError
from guardstudy.protocol import VARIANTS

def runtime_fixture():
    return dict(format='guardstudy.runtime.v1',metadata=metadata(),buffer_limits={'MLX_MAX_OPS_PER_BUFFER':10,'MLX_MAX_MB_PER_BUFFER':10},variants=[dict(variant=v,load_ns=1,warmup_ns=[1,1],memory=[],failure=None) for v in VARIANTS])
class RuntimeTests(unittest.TestCase):
    def test_runtime_closed(self):
        r=runtime_fixture();validate_runtime(r)
        for mutate in [lambda x:x.update(private_path='/private/secret'),lambda x:x['variants'][0].update(private_text='secret'),lambda x:x['variants'][0].update(load_ns=True),lambda x:x['metadata'].update(secret='x')]:
            value=copy.deepcopy(r);mutate(value)
            with self.assertRaises(StudyError): validate_runtime(value)

    def test_null_identity_and_float_limits_rejected(self):
        for field in ('python','system','release','machine'):
            r=runtime_fixture();r['metadata'][field]=None
            with self.assertRaises(StudyError): validate_runtime(r)
        r=runtime_fixture();r['buffer_limits']['MLX_MAX_OPS_PER_BUFFER']=10.0
        with self.assertRaises(StudyError): validate_runtime(r)

    def test_warmup_without_load_rejected(self):
        from tests.test_recorded import fixture_bundle
        from guardstudy.recorded import seal_recorded
        import tempfile
        from pathlib import Path
        from guardstudy.runner import empty_prediction
        d,e,p,o=fixture_bundle()
        o['predictions']=[empty_prediction(p,v,c,'not_attempted','not_attempted_after_worker_failure') for v in VARIANTS for c in d['clusters']]
        for row in o['runtime']: row.update(load_ns=None,warmup_ns=[1],memory=[],failure='worker_failure')
        with self.assertRaises(StudyError): seal_recorded(o,dict(dataset=d,exposure=e,protocol=p),Path(tempfile.mkdtemp())/'bundle')

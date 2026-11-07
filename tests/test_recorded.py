import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from guardstudy.recorded import build_report, seal_recorded, verify_recorded, observe_output, validate_grid
from guardstudy.runner import empty_prediction
from guardstudy.protocol import VARIANTS, score
from guardstudy.io import StudyError, PublicationError, canonical, sha256, read_json
from tests.test_protocol import protocol_fixture

def fixture_bundle():
    d,e,p=protocol_fixture();rows=[]
    for v in VARIANTS:
        for c in d['clusters']:
            r=empty_prediction(p,v,c,'ok',None);r.update(score(-1.,1.),input_tokens=20,tokenize_ns=1,forward_ns=2,total_request_ns=3);rows.append(r)
    from tests.test_runtime import runtime_fixture
    runtime=runtime_fixture()
    from guardstudy.protocol import RUNTIME_PINS
    runtime['metadata']=dict(python='3.12.0',system='Darwin',release='fixture',machine='arm64',versions=RUNTIME_PINS.copy())
    for entry in runtime['variants']: entry['memory']=[dict(active=None,cache=None,peak=None,rss=None) for _ in range(340)]
    o=dict(runtime_metadata=runtime['metadata'],format='guardstudy.outcome.v1',protocol_digest=p['protocol_digest'],backend_kind='real_mlx',predictions=rows,runtime=runtime['variants'])
    return d,e,p,o
class RecordedTests(unittest.TestCase):
    def test_report_and_missing(self):
        d,e,p,o=fixture_bundle();report=build_report(p,d,e,o)
        self.assertEqual(report['counts']['raw_rows'],339)
        self.assertEqual(report['cohorts']['audited_eligible_primary']['variants'][VARIANTS[0]]['status'],'inconclusive')
        self.assertEqual(report['cohorts']['raw_unique_descriptive']['variants'][VARIANTS[0]]['fp'],0)
    def test_bad_grid(self):
        d,e,p,o=fixture_bundle()
        for mutate in [lambda r:r.pop(),lambda r:r.append(r[0]),lambda r:r[0].update(decision='ATTACK'),lambda r:r[0].update(text_sha256='f'*64),lambda r:r[0].update(input_tokens=True),lambda r:r[0].update(extra=1)]:
            rows=copy.deepcopy(o['predictions']);mutate(rows)
            with self.assertRaises(StudyError): validate_grid(p,d,rows)
    def test_seal_verify_and_no_overwrite(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp(prefix='guardstudy-recorded-test-'))/'bundle'
        seal_recorded(o,{'dataset':d,'exposure':e,'protocol':p},root)
        result=verify_recorded(root)
        self.assertEqual(result['integrity'],'valid');self.assertEqual(result['producer_durability'],'not_evaluated')
        first=(root/'recorded-manifest.json').read_bytes();verify_recorded(root)
        self.assertEqual(first,(root/'recorded-manifest.json').read_bytes())
        with self.assertRaises(PublicationError): seal_recorded(o,{'dataset':d,'exposure':e,'protocol':p},root)
    def test_fixture_cannot_be_recorded(self):
        d,e,p,o=fixture_bundle();o['backend_kind']='fixture'
        with self.assertRaises(StudyError): seal_recorded(o,{'dataset':d,'exposure':e,'protocol':p},Path(tempfile.mkdtemp())/'bundle')
    def test_post_manifest_fsync_failure(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle'
        import guardstudy.io as io
        original=io.fsync_dir
        def fail(path):
            if (root/'recorded-manifest.json').exists(): raise OSError()
            return original(path)
        with patch('guardstudy.io.fsync_dir',side_effect=fail):
            with self.assertRaises(PublicationError) as caught: seal_recorded(o,{'dataset':d,'exposure':e,'protocol':p},root)
        self.assertEqual(caught.exception.observed_output,'complete')
        self.assertEqual(verify_recorded(root)['integrity'],'valid')
    def test_observer_and_corruption(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle'
        self.assertEqual(observe_output(root,'0'*64)['observed_output'],'absent')
        seal_recorded(o,{'dataset':d,'exposure':e,'protocol':p},root)
        h=sha256((root/'recorded-manifest.json').read_bytes())
        self.assertEqual(observe_output(root,h)['observed_output'],'complete')
        (root/'report.json').write_bytes(b'{}')
        with self.assertRaises(StudyError): verify_recorded(root)
        self.assertEqual(observe_output(root,h)['observed_output'],'partial')

    def test_crash_after_manifest_link(self):
        import multiprocessing
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle'
        ctx=multiprocessing.get_context('fork');proc=ctx.Process(target=crash_publish,args=(o,dict(dataset=d,exposure=e,protocol=p),root))
        proc.start();proc.join(5)
        if proc.is_alive(): proc.kill();proc.join();self.fail('child deadline')
        self.assertEqual(proc.exitcode,77)
        self.assertEqual(verify_recorded(root)['producer_durability'],'not_evaluated')
        h=sha256((root/'recorded-manifest.json').read_bytes())
        self.assertEqual(observe_output(root,h)['observed_output'],'complete')

    def test_observer_read_error_unknown(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle'
        seal_recorded(o,dict(dataset=d,exposure=e,protocol=p),root)
        with patch('guardstudy.recorded.read_bytes',side_effect=StudyError('read_failed')):
            self.assertEqual(observe_output(root,'0'*64)['observed_output'],'unknown')

    def test_partial_manifest_write(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle'
        import guardstudy.recorded as module
        original=module.write_new
        def fail(path,data,**kw):
            if path.name=='recorded-manifest.json': raise PublicationError()
            return original(path,data,**kw)
        with patch('guardstudy.recorded.write_new',side_effect=fail):
            with self.assertRaises(PublicationError) as exc: seal_recorded(o,dict(dataset=d,exposure=e,protocol=p),root)
        self.assertFalse((root/'recorded-manifest.json').exists());self.assertEqual(exc.exception.observed_output,'partial')

def crash_publish(outcome,artifacts,root):
    import guardstudy.io as io
    original=io.os.link
    def link(source,target,**kw):
        original(source,target,**kw)
        if Path(target).name=='recorded-manifest.json': os._exit(77)
    io.os.link=link
    seal_recorded(outcome,artifacts,root)

class RuntimeConsistencyTests(unittest.TestCase):
    def test_successful_predictions_require_successful_runtime(self):
        d,e,p,o=fixture_bundle()
        for row in o['runtime']:
            row.update(load_ns=None,warmup_ns=[],memory=[],failure='worker_launch')
        o['runtime_metadata']['versions']={k:None for k in o['runtime_metadata']['versions']}
        with self.assertRaises(StudyError): seal_recorded(o,dict(dataset=d,exposure=e,protocol=p),Path(tempfile.mkdtemp())/'bundle')

    def test_report_type_tamper_after_rehash(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle';seal_recorded(o,dict(dataset=d,exposure=e,protocol=p),root)
        report=read_json(root/'report.json');report['counts']['raw_rows']=339.0
        raw=canonical(report)+b'\n';(root/'report.json').write_bytes(raw)
        manifest=read_json(root/'recorded-manifest.json')
        for f in manifest['files']:
            if f['name']=='report.json': f.update(size=len(raw),sha256=sha256(raw))
        (root/'recorded-manifest.json').write_bytes(canonical(manifest)+b'\n')
        with self.assertRaises(StudyError): verify_recorded(root)

    def test_unknown_empty_directory_rejected(self):
        d,e,p,o=fixture_bundle();root=Path(tempfile.mkdtemp())/'bundle';seal_recorded(o,dict(dataset=d,exposure=e,protocol=p),root)
        (root/'unexpected-empty-directory').mkdir()
        with self.assertRaises(StudyError): verify_recorded(root)

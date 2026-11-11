import os
import signal
import sys
import unittest
from pathlib import Path
from unittest import mock
from guardstudy.runner import Worker, supervise
from tests.test_protocol import protocol_fixture
class RunnerTests(unittest.TestCase):
    def run_mode(self,mode):
        d,e,p=protocol_fixture()
        command=[sys.executable,'-B',str(Path(__file__).parent/'fixtures/worker_fixture.py'),mode]
        return supervise(p,d,command,{},backend_kind='fixture',test_deadlines=(.8,.2,5))
    def test_fixture_complete_marked(self):
        out=self.run_mode('good');self.assertEqual(out['backend_kind'],'fixture')
        self.assertTrue(all(r['status']=='ok' for r in out['predictions']))
        self.assertEqual(len(out['predictions']),678)
    def test_crash_and_timeout_preserve_grid(self):
        for mode in ['crash','timeout','bad_id','nan']:
            with self.subTest(mode=mode):
                out=self.run_mode(mode);rows=out['predictions'][:339]
                self.assertEqual(rows[0]['status'],'invalid');self.assertEqual(rows[1]['status'],'not_attempted')
                self.assertEqual(len({(r['variant'],r['representative_id']) for r in out['predictions']}),678)
    def test_exit_after_result_no_duplicate(self):
        rows=self.run_mode('exit_after_result')['predictions'][:339]
        self.assertEqual(rows[0]['status'],'ok');self.assertEqual(rows[1]['status'],'invalid')
    def test_load_timeout(self):
        rows=self.run_mode('load_timeout')['predictions']
        self.assertTrue(all(r['status']=='not_attempted' for r in rows))
    def test_close_tolerates_a_worker_that_exited_but_is_not_yet_reaped(self):
        # macOS answers killpg with EPERM, not ESRCH, when the group holds only
        # a zombie. A worker that dies between poll() and killpg() must not
        # abort the run and discard the prediction grid.
        worker=Worker([sys.executable,'-B','-c','import time; time.sleep(30)'])
        real=os.killpg
        def exited_first(pid,sig):
            real(pid,signal.SIGKILL);worker.proc.wait(timeout=5)
            raise PermissionError(1,'Operation not permitted')
        with mock.patch('guardstudy.runner.os.killpg',side_effect=exited_first): worker.close()
        self.assertEqual(worker.proc.returncode,-signal.SIGKILL)
        self.assertTrue(worker.proc.stdout.closed)

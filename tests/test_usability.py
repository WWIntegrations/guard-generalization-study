import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = 'examples/recorded'


def run(*args, cwd=None):
    return subprocess.run([sys.executable, '-B', '-m', 'guardstudy', *args], cwd=cwd or ROOT,
                          capture_output=True, text=True, env={'PYTHONPATH': str(ROOT), 'PATH': '/usr/bin:/bin'}, timeout=120)


class UsabilityTests(unittest.TestCase):
    def test_verify_default_is_human_and_json_flag_is_machine(self):
        text = run('verify', '--recorded-dir', REC)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn('integrity: valid', text.stdout)
        self.assertNotIn('{', text.stdout)
        data = json.loads(run('verify', '--recorded-dir', REC, '--json').stdout)
        self.assertEqual(data['integrity'], 'valid')

    def test_report_prints_summary_without_output_file_and_repeats(self):
        for _ in range(2):
            result = run('report', '--recorded-dir', REC)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('110 / 257 flagged  FPR 42.80%', result.stdout)
            self.assertIn('exact McNemar p = 0.10886', result.stdout)
            self.assertIn('Limits:', result.stdout)

    def test_report_json_is_the_verified_report(self):
        result = run('report', '--recorded-dir', REC, '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads((ROOT / REC / 'report.json').read_text()))

    def test_report_summary_for_inconclusive_bundle(self):
        # Partial exposure coverage leaves the primary cohort empty: rates and p-values are undefined.
        from guardstudy.recorded import seal_recorded
        from tests.test_recorded import fixture_bundle
        with tempfile.TemporaryDirectory() as work:
            d, e, p, o = fixture_bundle()
            seal_recorded(o, dict(dataset=d, exposure=e, protocol=p), Path(work) / 'bundle')
            result = run('report', '--recorded-dir', str(Path(work) / 'bundle'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Study status: inconclusive.', result.stdout)
            self.assertIn('0 / 0   flagged  FPR undefined  (Wilson 95% undefined)', result.stdout)
            self.assertIn('paired difference (v2 minus base): undefined over 0 pairs', result.stdout)

    def test_report_out_writes_markdown_and_keeps_create_only(self):
        with tempfile.TemporaryDirectory() as work:
            target = str(Path(work) / 'r.md')
            self.assertEqual(run('report', '--recorded-dir', REC, '--out', target).returncode, 0)
            self.assertIn('# Guard benign false-positive study', Path(target).read_text())
            self.assertEqual(run('report', '--recorded-dir', REC, '--out', target).returncode, 3)

    def test_own_data_exposure_example_and_default_output_dir_reruns(self):
        with tempfile.TemporaryDirectory() as work:
            inventory = json.loads((ROOT / 'examples/own-data/inventory.json').read_text())
            inventory['sources'][0]['path'] = str(ROOT / inventory['sources'][0]['path'])
            local = Path(work) / 'inventory.json'
            local.write_text(json.dumps(inventory))
            args = ('exposure', '--dataset', str(ROOT / REC / 'dataset.json'), '--private-inventory', str(local))
            first = run(*args, cwd=work)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('excluded_exact       1', first.stdout)
            self.assertTrue((Path(work) / 'exposure-out/exposure-receipt.json').exists())
            second = run(*args, cwd=work)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue((Path(work) / 'exposure-out-2/exposure-receipt.json').exists())
            self.assertNotIn('Can I ignore', first.stdout)

    def test_terminal_escapes_neutralised(self):
        from guardstudy.summary import clean, report_text, verify_text
        evil = '\x1b]8;;http://evil\x1b\\X\u202e\r\n\u2066'
        self.assertNotRegex(clean(evil), '[\x1b\r\n\u202e\u2066]')
        cohort = {'variants': {evil: {'fp': 1, 'ok': 2, 'fpr_observed': .5, 'wilson95': [.1, .9], 'invalid': 0, 'not_attempted': 0}},
                  'paired': {'delta_fpr_v2_minus_base': 0.0, 'mcnemar_exact_p': 1.0, 'pairs': 2}}
        report = {'status': evil, 'backend_kind': evil, 'counts': {'unique_clusters': evil}, 'cohorts': {evil: cohort}, 'limits': [evil]}
        text = report_text(report, saved=evil) + verify_text(dict(integrity=evil, status=evil, files=evil, protocol_digest=evil, producer_durability=evil))
        for bad in ('\x1b', '\r', '\u202e', '\u2066'):
            self.assertNotIn(bad, text)
        self.assertIn('\\x1b', text)


if __name__ == '__main__':
    unittest.main()

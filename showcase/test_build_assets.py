import importlib.util
import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('builder', ROOT / 'tools/build_showcase.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuilderTests(unittest.TestCase):
    def test_intercepted_anchor_destinations_accept_programmatic_focus(self):
        class Anchors(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.targets = {}, set()

            def handle_starttag(self, tag, attributes):
                values = dict(attributes)
                if 'id' in values:
                    self.ids[values['id']] = (tag, values)
                if tag == 'a' and values.get('href', '').startswith('#'):
                    self.targets.add(values['href'][1:])

        parser = Anchors()
        parser.feed((ROOT / 'showcase/template.html').read_text())
        for identifier in parser.targets:
            tag, attributes = parser.ids[identifier]
            self.assertTrue(tag in {'a', 'button', 'input', 'select', 'textarea'}
                            or attributes.get('tabindex') in {'-1', '0'}, identifier)

    def test_injected_text_cannot_close_data_script(self):
        value = builder.script_json({'text': '</script><img src=x onerror=alert(1)>'})
        self.assertNotIn('</script', value)
        self.assertIn('\\u003c', value)

    def test_replacement_does_not_reprocess_inserted_markers(self):
        self.assertEqual(builder.fill_template('__A__ __B__', {'__A__': '__B__', '__B__': 'ok'}), '__B__ ok')

    def test_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'preview.html'
            builder.publish_new(path, b'first')
            with self.assertRaises(FileExistsError):
                builder.publish_new(path, b'second')
            self.assertEqual(path.read_bytes(), b'first')

    def test_missing_recorded_path_fails_closed(self):
        from guardstudy.io import StudyError
        with self.assertRaises(StudyError):
            builder.recorded_payload(Path('does-not-exist'))

    def test_export_bytes_come_from_the_verified_snapshot_without_reread(self):
        # Synthetic unit boundary only; never an example or recorded study.
        raw = b'{"text":"a\\n\\u017c"}\n'
        snapshot = {'manifest': {}, 'report': {'status': 'inconclusive'}, 'dataset': {},
                    'predictions': {}, 'exposure': {}, 'protocol': {}, 'raw_files': {'dataset.json': raw}}
        with patch('guardstudy.recorded.load_verified_bundle', return_value=snapshot) as verify:
            payload = builder.recorded_payload(Path('not-read-by-builder'))
        verify.assert_called_once()
        self.assertEqual(base64.b64decode(payload['originals']['dataset.json']['base64']), raw)
        self.assertNotIn('raw_files', payload['inspector'])


if __name__ == '__main__':
    unittest.main()

"""Create an offline viewer without generating predictions or modifying outputs."""
import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def script_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def fill_template(template, replacements):
    spans = []
    for marker, value in replacements.items():
        if template.count(marker) != 1:
            raise ValueError('Missing or repeated marker: ' + marker)
        spans.append((template.index(marker), marker, value))
    chunks, cursor = [], 0
    for start, marker, value in sorted(spans):
        chunks.extend([template[cursor:start], value])
        cursor = start + len(marker)
    return ''.join(chunks + [template[cursor:]])


def publish_new(path, content):
    # This is a preview writer, not the core bundle publication protocol.
    # Failure may leave a partial new file. Existing files are never replaced.
    with Path(path).open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def recorded_payload(directory):
    from guardstudy.recorded import load_verified_bundle
    snapshot = load_verified_bundle(directory)
    originals = {name: {'base64': base64.b64encode(raw).decode('ascii'),
                        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                 for name, raw in snapshot['raw_files'].items()}
    inspector = {key: value for key, value in snapshot.items() if key != 'raw_files'}
    return {'buildMode': 'Validated recorded study. Metrics replayed from saved predictions; inference not repeated.',
            'inspector': inspector, 'originals': originals}


def assemble(payload):
    source = ROOT / 'showcase'
    script = (source / 'bundle.js').read_text()
    if '</script' in script.lower():
        raise ValueError('Unsafe inline script terminator')
    fonts = {
        '__ANTON_FONT__': ('Anton', ROOT / 'docs/fonts/anton/Anton-Regular.ttf', 'ttf'),
        '__MONO_FONT__': ('Departure Mono', ROOT / 'docs/fonts/departure-mono/DepartureMono-Regular.woff2', 'woff2'),
    }
    replacements, licenses = {}, {}
    for marker, (name, path, kind) in fonts.items():
        replacements[marker] = 'data:font/' + kind + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
        licenses[name] = (path.parent / 'OFL.txt').read_text()
    for package, filename in [('three', 'LICENSE'), ('esbuild', 'LICENSE.md')]:
        licenses[package] = (ROOT / 'node_modules' / package / filename).read_text()
    css = fill_template((source / 'style.css').read_text(), replacements)
    return fill_template((source / 'template.html').read_text(), {
        '__STYLE__': css, '__DATA__': script_json(payload),
        '__LICENSES__': script_json(licenses), '__BUNDLE__': script,
        '__FAVICON__': 'data:image/svg+xml;base64,' + base64.b64encode((ROOT / 'docs/favicon.svg').read_bytes()).decode('ascii'),
    }).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--artwork-preview', action='store_true')
    mode.add_argument('--from-recorded', action='store_true')
    parser.add_argument('--recorded-dir', type=Path, default=ROOT / 'examples/recorded')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.artwork_preview:
        if not args.out:
            parser.error('Artwork preview requires an explicit private --out path')
        payload = {'buildMode': 'Artwork preview. No recorded results loaded.', 'inspector': None, 'originals': {}}
    else:
        payload = recorded_payload(args.recorded_dir)
    destination = args.out or ROOT / 'docs/index.html'
    content = assemble(payload)
    publish_new(destination, content)
    print(json.dumps({'output': str(destination), 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'recorded': args.from_recorded}))


if __name__ == '__main__':
    main()

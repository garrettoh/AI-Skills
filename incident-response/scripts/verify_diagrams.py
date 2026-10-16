"""Exercise reviewed brief validation, exports and provenance without npm or evidence access."""
import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from components import component_path, dependencies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    skill = component_path(args.skills_root, 'incident-diagrams')
    helper = skill / 'scripts/build_diagrams.py'
    fixture = json.loads((skill/'references/example-brief.json').read_text(encoding='utf-8'))
    if dependencies(['incident-diagrams']):
        raise RuntimeError('Standalone diagram skill unexpectedly requires evidence parser libraries')
    with tempfile.TemporaryDirectory(prefix='incident-diagrams-') as temporary:
        root = Path(temporary)
        brief, output = root/'brief.json', root/'diagrams'
        def build(data, *options, expected=0):
            brief.write_text(json.dumps(data), encoding='utf-8')
            result = subprocess.run([sys.executable, str(helper), '--brief', str(brief), '--output', str(output), *options],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode != expected:
                raise RuntimeError(f'Expected exit {expected}; got {result.returncode}: {result.stdout}\n{result.stderr}')
            return result
        formats = ['storyboard', 'timeline', 'technical', 'network', 'data-flow', 'identity']
        build(fixture, '--formats', *formats)
        manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        if len(manifest['exports']) != 6 or manifest['evidence']['move1'] != fixture['relationships'][0]['evidence']:
            raise RuntimeError('Exports or relationship evidence mapping missing')
        for fmt in formats:
            scene = json.loads((output/f'{fmt}.excalidraw').read_text(encoding='utf-8'))
            if scene['appState']['viewBackgroundColor'] != '#2E3440' or not scene['elements']:
                raise RuntimeError('Missing Nord scene or drawable content')
        for export in manifest['exports']:
            if any(key not in manifest['evidence'] for key in export['visual_items'].values()):
                raise RuntimeError('A visual item has no provenance mapping')
        if json.loads((output/'brief.snapshot.json').read_text(encoding='utf-8')) != fixture:
            raise RuntimeError('Reproducible reviewed brief snapshot missing')
        technical = (output/'technical.excalidraw').read_text(encoding='utf-8')
        if 'Time unknown' not in technical or 'Response timing not supplied' not in technical:
            raise RuntimeError('Unknown time was lost or invented')
        data = copy.deepcopy(fixture)
        data['events'][0]['time'] = '2026-01-02T09:00:00'
        build(data, expected=2)
        data = copy.deepcopy(fixture)
        data['events'][0]['evidence'] = []
        build(data, expected=2)
        data = copy.deepcopy(fixture)
        data['relationships'][0]['target'] = 'absent-host'
        build(data, expected=2)
        data = copy.deepcopy(fixture)
        data['relationships'][0]['id'] = data['events'][0]['id']
        build(data, expected=2)
        data = copy.deepcopy(fixture)
        data['relationships'][0]['category'] = 'identity'
        build(data, '--formats', 'network', expected=2)
        if json.loads((output/'manifest.json').read_text())['exports']:
            raise RuntimeError('Authentication-only evidence created lateral movement')
        data = copy.deepcopy(fixture)
        data['reviewed'] = False
        build(data, expected=2)
        # Stale images must never be advertised as newly rendered output.
        (output/'storyboard.png').write_bytes(b'stale')
        data = copy.deepcopy(fixture)
        data['title'] = '<script>alert(1)</script>'
        build(data)
        gallery = (output/'index.html').read_text(encoding='utf-8')
        if '<script>' in gallery or 'src="storyboard.png"' in gallery:
            raise RuntimeError('Gallery escaped-text or stale-render handling failed')
        # Deliberately hide the renderer: valid scenes must survive, but PNG success must not be claimed.
        unavailable = subprocess.run([sys.executable, str(helper), '--brief', str(brief), '--output', str(output),
                                      '--formats', 'storyboard', '--render'],
                                     env={**os.environ, 'PATH': ''}, capture_output=True, text=True, timeout=30)
        failed_render = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        if unavailable.returncode != 2 or 'png' in failed_render['exports'][0] or not failed_render['exports'][0].get('error'):
            raise RuntimeError('Missing renderer did not preserve an honest failed-export status')
        case = root/'case'
        case.mkdir()
        (case/'overview.json').write_text(json.dumps({'milestones': [dict(time='Jan 2, 9am', title='Observed event',
            description='Needs review', evidence='example record')]}), encoding='utf-8')
        result = subprocess.run([sys.executable, str(helper), '--case-dir', str(case), '--prepare'], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        draft = json.loads((case/'diagrams/diagram-brief.draft.json').read_text(encoding='utf-8'))
        if draft['reviewed'] is not False or draft['events'][0]['time'] is not None:
            raise RuntimeError('Draft preparation approved conclusions or inferred a timezone')
        build(draft, expected=2)
    print('PASS: six formats, independent dependencies, provenance, unknown times, review gates, unsupported movement, inert gallery and stale PNG handling')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

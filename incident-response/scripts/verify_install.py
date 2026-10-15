"""Verify selected skills without requiring unselected source skills."""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from components import select, dependencies, component_path


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {command}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', required=True, type=Path)
    parser.add_argument('--skills', nargs='+', help='Verify selected names; default: all')
    args = parser.parse_args()
    names = select(args.skills)
    root = args.skills_root.expanduser().resolve()
    for name in names:
        folder = component_path(root, name)
        if not (folder / 'SKILL.md').is_file():
            raise RuntimeError(f'Missing skill: {name}')
        scripts = sorted((folder / 'scripts').glob('*.py'))
        if not scripts:
            raise RuntimeError(f'Missing executable helpers: {name}')
        for script in scripts:
            run([sys.executable, str(script), '--help'])
    for name in dependencies(names):
        if not (component_path(root, name) / '__init__.py').is_file():
            raise RuntimeError(f'Missing dependency: {name}')
    with tempfile.TemporaryDirectory(prefix='selected-skill-check-') as temporary:
        work = Path(temporary)
        evidence = work / 'evidence'
        evidence.mkdir()
        with (evidence / 'events.csv').open('w', encoding='utf-8', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['EventId', 'TimeCreated', 'Provider', 'Computer', 'Payload'])
            writer.writerow(['4104', '2026-01-02 03:04:05', 'PowerShell', 'test-host', 'powershell.exe'])
        if 'ez-evtx-parser' in names:
            script = component_path(root, 'ez-evtx-parser') / 'scripts/filter_csv.py'
            report = work / 'filtered.md'
            run([sys.executable, str(script), str(evidence), '--keyword', 'powershell.exe', '--output', str(report)])
            text = report.read_text(encoding='utf-8')
            if 'matching rows: 1' not in text or '4104' not in text:
                raise RuntimeError('EVTX synthetic record was not found')
        if 'kape-orchestrator' in names:
            folder = component_path(root, 'kape-orchestrator') / 'scripts'
            inventory = work / 'inventory.json'
            run([sys.executable, str(folder / 'route_artifacts.py'), str(evidence), '--output', str(inventory)])
            if json.loads(inventory.read_text())['files'][0]['family'] != 'evtx':
                raise RuntimeError('KAPE router did not identify EVTX')
            report = work / 'timeline.md'
            run([sys.executable, str(folder / 'correlate_timeline.py'), str(evidence), '--keyword', 'powershell.exe', '--output', str(report)])
            text = report.read_text(encoding='utf-8')
            if 'Events in time bounds: 1' not in text or 'verified EVTX TimeCreated UTC values normalized: 1' not in text:
                raise RuntimeError('KAPE timeline did not automatically normalize naive EVTX TimeCreated as UTC')
            run([sys.executable, str(folder / 'investigate.py'), str(evidence), '--case', 'kape',
                 '--lead', 'powershell.exe', '--output-root', str(work / 'agent_output')])
        if 'hindsight-orchestrator' in names:
            sample = work / 'browser.jsonl'
            sample.write_text(json.dumps(dict(datetime='2026-01-02T03:04:04Z', timestamp_desc='Visit Time',
                profile='test-profile', url='https://example.invalid/fleetdeck')) + '\n', encoding='utf-8')
            script = component_path(root, 'hindsight-orchestrator') / 'scripts/hunt_hindsight.py'
            run([sys.executable, str(script), str(sample), '--case', 'browser', '--lead', 'fleetdeck',
                 '--output-root', str(work / 'agent_output')])
            events = [json.loads(line) for line in (work / 'agent_output/browser/timeline.jsonl').read_text().splitlines()]
            if len(events) != 1 or events[0]['profile'] != 'test-profile' or events[0]['record'] != '1':
                raise RuntimeError('Standalone Hindsight normalization failed')
    if 'investigation-orchestrator' in names:
        print(run([sys.executable, str(Path(__file__).with_name('verify_orchestration.py')),
                   '--skills-root', str(root)]).strip())
    print(f'PASS: {len(names)} selected skill(s), required helpers and applicable workflows at {root}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

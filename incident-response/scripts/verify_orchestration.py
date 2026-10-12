"""Exercise cross-source lead exchange and normalized persistence on isolated evidence."""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path, required=True)
    args = parser.parse_args()
    script = args.skills_root.resolve() / 'investigation-orchestrator/scripts/investigate.py'
    with tempfile.TemporaryDirectory(prefix='investigation-check-') as temporary:
        work = Path(temporary)
        kape = work / 'kape'
        browser = work / 'browser'
        kape.mkdir()
        browser.mkdir()
        with (kape / 'events.csv').open('w', encoding='utf-8', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['EventId', 'TimeCreated', 'Provider', 'Computer', 'Payload'])
            writer.writerow(['1', '2026-01-02T03:04:05Z', 'test', 'host-a',
                             'FleetDeck downloaded https://example.invalid/drop.exe'])
            writer.writerow(['2', '2026-01-02 03:04:06', 'test', 'host-a', 'FleetDeck naive UTC unknown'])
        record = dict(datetime='2026-01-02T03:04:04+00:00', timestamp_desc='Visit Time',
                      data_type='chrome:history:page_visited', profile='profile-a',
                      url='https://example.invalid/drop.exe', message='visit')
        (browser / 'chrome.jsonl.jsonl').write_text(json.dumps(record) + '\n', encoding='utf-8')
        command = [sys.executable, str(script), '--case', 'check', '--source', f'kape={kape}',
                   '--source', f'hindsight={browser}', '--lead', 'fleetdeck']
        def run(extra=(), expected=0):
            result = subprocess.run(command + list(extra), cwd=work, capture_output=True, text=True, timeout=60)
            if result.returncode != expected:
                raise RuntimeError(f'Unexpected exit {result.returncode}: {result.stdout} {result.stderr}')
        run()
        case = work / 'agent_output/check'
        if not (case / 'report.md').exists():
            raise RuntimeError('No deliverable before follow-up')
        initial = [json.loads(line) for line in (case / 'timeline.jsonl').read_text().splitlines()]
        if len(initial) != 1 or initial[0]['orchestrator'] != 'kape':
            raise RuntimeError('Initial lead was not searched independently in both sources')
        untimed = [json.loads(line) for line in (case / 'untimed.jsonl').read_text().splitlines()]
        if len(untimed) != 1 or untimed[0]['timestamp_utc'] is not None:
            raise RuntimeError('Unknown timezone was not preserved as untimed')
        leads = json.loads((case / 'leads.json').read_text())['leads']
        url = next(lead for lead in leads if lead['kind'] == 'url')
        if url['status'] != 'candidate' or not url['evidence']['parent_leads']:
            raise RuntimeError('Discovered URL has no candidate provenance')
        # Selective review imports must activate an existing candidate, not only new leads.
        url['status'] = 'active'
        selected = work / 'selected.json'
        selected.write_text(json.dumps({'leads': [url]}), encoding='utf-8')
        run(['--leads-file', str(selected)])
        events = [json.loads(line) for line in (case / 'timeline.jsonl').read_text().splitlines()]
        if [event['orchestrator'] for event in events] != ['hindsight', 'kape']:
            raise RuntimeError('URL did not pivot from KAPE to Hindsight in UTC order')
        if events[0]['profile'] != 'profile-a' or events[0]['record'] != '1':
            raise RuntimeError('Browser profile or citation lost')
        run()
        repeated = (case / 'timeline.jsonl').read_text().splitlines()
        if len(repeated) != 2:
            raise RuntimeError('Repeated rounds duplicated observations')
        # Incomplete coverage still produces a deliverable and signals exit 2.
        with (browser / 'chrome.jsonl.jsonl').open('a') as output:
            output.write('{broken\n')
        run(['--rescan'], expected=2)
        coverage = json.loads((case / 'hindsight/round-0004/coverage.json').read_text())
        if coverage['coverage'][0]['malformed'] != 1:
            raise RuntimeError('Malformed JSONL coverage missing')
        if not (case / 'report.md').exists():
            raise RuntimeError('Partial deliverable lost')
    print('PASS: initial dispatch, deliverable before pivot, KAPE-to-Hindsight URL exchange, UTC sorting, untimed retention, deduplication and malformed coverage')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, StopIteration) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

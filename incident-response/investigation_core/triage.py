"""Single-pass incident discovery with bounded summaries and source citations."""
import html
import json
import re
from collections import Counter
from urllib.parse import urlsplit

from kape_core.cli import stamp
from .rmm_triage import record_object, safe_excerpt

RMM = re.compile(r'screenconnect|connectwise|splashtop|srservice\.exe|srserver\.exe|beyondtrust|bomgar|anydesk|teamviewer|rustdesk|meshagent|meshcentral|tactical.?rmm|simplehelp|logmein|gotoassist|zoho.?assist|ninjarmm|ninjaone|action1|\batera\b', re.I)
RISKY_PS = re.compile(r'encodedcommand|\bfrombase64string\b|downloadstring|downloadfile|invoke-webrequest|invoke-restmethod|\biex\b|executionpolicy\s+bypass|add-mppreference|set-mppreference|putobject|\bbackup\b.*https?://|schtasks|new-service|new-localuser|add-localgroupmember', re.I)
EXECUTABLE = re.compile(r'\.(?:exe|msi|msix|dll|scr|ps1|bat|cmd|vbs|hta|js|zip|iso)(?:[?&#\s"\x27]|$)', re.I)
PERSISTENCE = re.compile(r'\\(?:runonce|run|winlogon|image file execution options|taskcache|services)(?:\\|$)|\\start menu\\programs\\startup\\', re.I)
SECURITY = {
    '4624': ('logon-success', 1), '4625': ('logon-failure', 1),
    '4648': ('explicit-credentials', 2), '4672': ('privileged-logon', 1),
    '4720': ('account-created', 3), '4722': ('account-enabled', 3),
    '4724': ('password-reset', 3), '4728': ('group-membership-added', 3),
    '4732': ('group-membership-added', 3), '4756': ('group-membership-added', 3),
    '4738': ('account-changed', 2), '4719': ('audit-policy-changed', 3),
    '4697': ('service-installed', 3), '4698': ('task-created', 3),
    '4702': ('task-changed', 3), '1102': ('security-log-cleared', 3),
    '4663': ('object-access', 1), '5140': ('share-access', 1),
    '5145': ('share-access-check', 1),
}


def event_values(row):
    """Decode EvtxECmd named values only for event categories needing attribution."""
    try:
        data = json.loads(row.get('Payload', '{}')).get('EventData', {})
        items = data.get('Data', []) if isinstance(data, dict) else []
        if isinstance(items, dict):
            items = [items]
        return {item['@Name']: str(item.get('#text', '')) for item in items
                if isinstance(item, dict) and '@Name' in item}
    except (ValueError, TypeError, AttributeError):
        return {}


def classify(record, source):
    """Return (category, priority, subject, details) without rereading evidence."""
    row, family = record['data'], record['family']
    signals = []
    if family == 'evtx':
        eid = str(row.get('EventId', ''))
        provider = row.get('Provider', '').casefold()
        channel = row.get('Channel', '').casefold()
        if 'security-auditing' in provider or ('security' == channel) or (eid == '1102' and 'eventlog' in provider):
            if eid in SECURITY:
                values = event_values(row)
                category, priority = SECURITY[eid]
                if eid == '4624' and values.get('LogonType') == '10':
                    category, priority = 'remote-interactive-logon', 3
                # Type 3 is network authentication, not evidence of an interactive desktop.
                relevant = {k: v for k, v in values.items() if k in {
                    'TargetUserName', 'TargetDomainName', 'SubjectUserName', 'MemberName',
                    'MemberSid', 'TargetSid', 'LogonType', 'IpAddress', 'WorkstationName',
                    'TargetLogonId', 'SubjectLogonId', 'ProcessName', 'ObjectName',
                    'ShareName', 'RelativeTargetName', 'AccessMask', 'ServiceName', 'TaskName'}}
                subject = '|'.join(relevant.get(k, '') for k in (
                    'TargetUserName', 'LogonType', 'IpAddress', 'ServiceName', 'TaskName',
                    'ShareName', 'ObjectName', 'RelativeTargetName', 'MemberName'))
                signals.append((category, priority, subject or row.get('PayloadData1', eid), relevant))
        elif 'powershell' in provider:
            if eid in {'400', '4103', '4104'}:
                text = '\n'.join(str(row.get(k, '')) for k in ('PayloadData1', 'ExecutableInfo', 'Payload'))
                risky = bool(RISKY_PS.search(text))
                signals.append(('powershell-review' if risky else 'powershell-activity',
                                3 if risky else 1, safe_excerpt(text, 180), {}))
        elif provider == 'service control manager' and eid in {'7045', '7040'}:
            signals.append(('service-installed' if eid == '7045' else 'service-start-type-changed',
                            3, row.get('PayloadData1', ''), {}))
        elif 'taskscheduler' in provider and eid in {'106', '140', '141'}:
            signals.append(('task-registration-change', 3, row.get('PayloadData1') or row.get('Payload', '')[:180], {}))
        elif ('terminalservices' in provider and eid in {'1149', '21', '24', '25'}):
            signals.append(('remote-access-event', 3, row.get('UserName') or row.get('PayloadData1', ''), event_values(row)))
        elif ('sentinelone' in provider and eid == '31') or ('defender' in provider and eid in {'1116', '1117'}):
            signals.append(('security-detection', 3, row.get('ExecutableInfo') or row.get('PayloadData1', ''), {}))
        elif 'msiinstaller' in provider and eid in {'11707', '1033', '11724', '1034'}:
            category = 'software-removal' if eid in {'11724', '1034'} else 'software-installation'
            signals.append((category, 2, row.get('PayloadData1') or row.get('Payload', '')[:180], {}))
        if (eid == '4688' and 'security-auditing' in provider) or (eid == '1' and 'sysmon' in provider):
            values = event_values(row)
            command = values.get('CommandLine', '')
            image = values.get('NewProcessName', values.get('Image', ''))
            if RISKY_PS.search(command):
                signals.append(('process-execution-review', 3, image + '|' + safe_excerpt(command, 180),
                                {k: values[k] for k in ('ProcessGuid', 'ParentProcessGuid', 'NewProcessId', 'SubjectLogonId', 'ParentImage') if k in values}))
            elif re.search(r'powershell|pwsh|mshta|wscript|cscript', image, re.I):
                signals.append(('script-host-execution', 1, image, {}))
        # Only inspect free text on the smaller set of process/product records or classified events.
        if any(s[0] in {'service-installed', 'service-start-type-changed', 'task-registration-change', 'powershell-review', 'powershell-activity', 'software-installation'} for s in signals) or eid in {'4688', '1', '20', '100', '101', '801', '7031', '7036'} or RMM.search(provider):
            text = '\n'.join(str(v) for k, v in row.items() if k not in {'SourceFile', 'Computer'})
            if RMM.search(text):
                for item in record_object(record['source'], int(record['record']), row):
                    signals.append(('rmm', 3 if item['evidence_type'] in {'service-install', 'remote-session-or-connection'} else 2,
                                    item['tool'] + '|' + '|'.join(d['value'] for d in item['domains']), item))
    elif source == 'hindsight':
        kind = str(row.get('data_type', row.get('Type', ''))).casefold()
        url = str(row.get('url', row.get('URL', '')))
        try:
            host = urlsplit(url).hostname or ''
        except ValueError:
            host = ''
        if host:
            signals.append(('browser-domain', 0, host.casefold(), {}))
        if 'download' in kind or row.get('download_path') or row.get('target_path'):
            details = {k: safe_excerpt(v, 400) for k, v in row.items()
                       if re.search('url|path|size|opened|state|hash|etag', k, re.I)}
            signals.append(('browser-download', 3 if EXECUTABLE.search(str(row)) else 2,
                            str(row.get('target_path', row.get('download_path', url))), details))
    elif family in {'registry', 'registry-detail'}:
        text = ' '.join(str(v) for v in row.values())
        if PERSISTENCE.search(text):
            key_path = row.get('KeyPath', row.get('BatchKeyPath', ''))
            service_inventory = '\\services\\' in key_path.casefold()
            signals.append(('service-registry-inventory' if service_inventory else 'registry-persistence',
                            1 if service_inventory else 3, key_path, {}))
        if re.search(r'uninstall|installed.?program', text, re.I):
            signals.append(('installed-program', 2, row.get('ValueData', row.get('DisplayName', '')), {}))
        if RMM.search(text):
            for item in record_object(record['source'], int(record['record']), row):
                signals.append(('rmm', 2, item['tool'], item))
    else:
        # Avoid full MFT/USN content matching: only their relevant path columns are needed.
        path = ' '.join(str(row.get(k, '')) for k in ('FullPath', 'Path', 'Executable', 'ExeInfo', 'ExecutableName', 'FileName', 'ParentPath', 'AbsolutePath', 'Name', 'DisplayName'))
        if RMM.search(path):
            for item in record_object(record['source'], int(record['record']), row):
                signals.append(('rmm', 2, item['tool'], item))
        if '\\startup\\' in path.casefold():
            signals.append(('startup-folder', 3, path, {}))
        if 'amcache' in family and row.get('ApplicationName'):
            signals.append(('installed-program-inventory', 1, row['ApplicationName'], {}))
        if family in {'shellbags', 'shortcut', 'jumplist-auto', 'jumplist-custom', 'activity'}:
            accessed = row.get('TargetIDAbsolutePath') or row.get('AbsolutePath') or row.get('Executable') or row.get('TargetPath') or path
            signals.append(('file-folder-or-application-interaction', 1, accessed, {}))
        if family == 'srum':
            signals.append(('application-resource-or-network-use', 1, row.get('ExeInfo', ''), {}))
    return signals


def boundary_samples(samples):
    """Keep the exact citations establishing each group's observed time boundaries."""
    if not samples:
        return []
    timed = [s for s in samples if any(t.get('utc') for t in s['times'])]
    if not timed:
        return samples[:2]
    first = min(timed, key=lambda s: min(t['utc'] for t in s['times'] if t.get('utc')))
    last = max(timed, key=lambda s: max(t['utc'] for t in s['times'] if t.get('utc')))
    return [first] if first == last else [first, last]


class Triage:
    """Bound memory to 2,048 groups; keep detailed grouping on disk."""
    def __init__(self, db, assume_utc=False, start=None, end=None, policy=None):
        self.db, self.assume_utc, self.start, self.end = db, assume_utc, start, end
        self.cache = {}
        self.policy = policy
        self.counts = Counter()
        db.execute('create table if not exists triage_groups(key text primary key, category text, priority integer, subject text, count integer, first_utc text, last_utc text, samples text)')

    def observe(self, record, source):
        signals = classify(record, source)
        if not signals:
            return []
        times = [(field, raw, self.policy.resolve(raw, record['family'], field, explicit,
                 record.get('timezone_bases', {}).get(field))[0] if self.policy else stamp(raw, explicit or self.assume_utc))
                 for field, raw, explicit in record['times']]
        eligible = [(f, r, u) for f, r, u in times if not u or
                    ((not self.start or u >= self.start) and (not self.end or u <= self.end))]
        if times and not eligible:
            return []
        timed = sorted(u for _, _, u in eligible if u)
        citation = dict(source=record['source'], record=record['record'], host=record['host'], user=record['user'],
                        times=[dict(field=f, raw=r, utc=u) for f, r, u in eligible])
        for category, priority, subject, details in signals:
            subject = safe_excerpt(subject, 240)
            key = json.dumps([category, subject, record['host'], record['user']])
            sample = dict(citation, details=details)
            group = self.cache.get(key)
            if group is None:
                group = self.cache[key] = dict(category=category, priority=priority, subject=subject, count=0,
                    first_utc=None, last_utc=None, samples=[])
            group['count'] += 1
            group['priority'] = max(priority, group['priority'])
            if timed:
                group['first_utc'] = min(timed[0], group['first_utc'] or timed[0])
                group['last_utc'] = max(timed[-1], group['last_utc'] or timed[-1])
            group['samples'] = boundary_samples(group['samples'] + [sample])
            self.counts[category] += 1
        if len(self.cache) >= 2048:
            self.flush()
        return [s[0] for s in signals if s[1] >= 3]

    def flush(self):
        for key, group in self.cache.items():
            old = self.db.execute('select count,first_utc,last_utc,samples,priority from triage_groups where key=?', (key,)).fetchone()
            if old:
                group['count'] += old[0]
                group['first_utc'] = min(filter(None, [old[1], group['first_utc']]), default=None)
                group['last_utc'] = max(filter(None, [old[2], group['last_utc']]), default=None)
                group['samples'] = boundary_samples(json.loads(old[3]) + group['samples'])
                group['priority'] = max(old[4], group['priority'])
            self.db.execute('insert or replace into triage_groups values(?,?,?,?,?,?,?,?)', (
                key, group['category'], group['priority'], group['subject'], group['count'],
                group['first_utc'], group['last_utc'], json.dumps(group['samples'], ensure_ascii=False)))
        self.cache.clear()

    def finish(self, destination):
        self.flush()
        # Small model-facing index; complete groups stay available on disk.
        with (destination / 'triage-groups.jsonl').open('w', encoding='utf-8') as output:
            for category, priority, subject, count, first, last, samples in self.db.execute(
                    'select category,priority,subject,count,first_utc,last_utc,samples from triage_groups order by priority desc,first_utc is null,first_utc'):
                output.write(json.dumps(dict(category=category, priority=priority, subject=subject, count=count,
                    first_utc=first, last_utc=last, samples=json.loads(samples)), ensure_ascii=False) + '\n')
        summary = dict(counts=dict(self.counts), groups=self.db.execute('select count(*) from triage_groups').fetchone()[0],
                       categories={})
        for category in self.counts:
            selected = {}
            # Include recent changes as well as earliest evidence and frequent baseline.
            for ordering, limit in [('first_utc is null,first_utc', 2), ('last_utc is null,last_utc desc', 2), ('count desc', 1)]:
                for key, s, n, f, l, e, priority in self.db.execute(
                        'select key,subject,count,first_utc,last_utc,samples,priority from triage_groups where category=? order by ' + ordering + ' limit ?', (category, limit)):
                    selected[key] = dict(subject=s, count=n, first_utc=f, last_utc=l, priority=priority, evidence=json.loads(e))
            summary['categories'][category] = list(selected.values())
        (destination / 'triage-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        return dict(counts=dict(self.counts), groups=summary['groups'], summary=str(destination / 'triage-summary.json'))

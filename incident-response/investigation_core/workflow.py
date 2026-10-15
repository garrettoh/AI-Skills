"""Local lead exchange and normalized, persistent forensic timelines."""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from kape_core.cli import cell, stamp
from kape_core.timezones import TimestampPolicy, default_timezone, display_timestamp, source_rules, zone, list_zones
from .adapters import ADAPTERS
from .dashboard import build_dashboard
from .output_paths import configured_destination
from .triage import Triage


def dump(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def candidates(data):
    """Extract concrete values from matched evidence; these are leads, not verdicts."""
    result = set()
    for key, value in data.items():
        text = str(value)
        for match in re.finditer(r'https?://[^\s<>"\x27]+', text, re.I):
            url = match[0].rstrip('.,;)')
            if len(url) <= 4096:
                result.add(('url', url))
                try:
                    host = urlsplit(url).hostname
                    if host:
                        result.add(('domain', host))
                except ValueError:
                    pass
        if re.search(r'(path|executable|filename|exeinfo|target)', key, re.I):
            if 2 < len(text) <= 1024 and ('\\' in text or '/' in text or text.lower().endswith(('.exe', '.dll', '.msi', '.ps1'))):
                result.add(('path', text))
        if re.fullmatch(r'[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', text):
            result.add(('hash', text.lower()))
    return sorted(result)


def initialize(db):
    db.executescript('''
        create table if not exists leads(
            id text primary key, kind text, value text, origin text, evidence text,
            status text, round integer);
        create table if not exists searched(lead text, source text, primary key(lead, source));
        create table if not exists events(
            id text primary key, utc text, source text, record text, field text,
            event text);
        create table if not exists rounds(id integer primary key, scope text);
    ''')


def add_lead(db, kind, value, origin, evidence, status, number):
    key = identity(kind, value.casefold())
    db.execute('insert or ignore into leads values(?,?,?,?,?,?,?)',
               (key, kind, value, origin, json.dumps(evidence), status, number))
    return key


def export_leads(db, destination):
    leads = []
    for key, kind, value, origin, evidence, status, number in db.execute('select * from leads order by round,id'):
        leads.append(dict(id=key, kind=kind, value=value, origin=origin,
                          evidence=json.loads(evidence), status=status, round=number,
                          searched_by=[r[0] for r in db.execute('select source from searched where lead=?', (key,))]))
    dump(destination / 'leads.json', {'schema_version': 1, 'leads': leads})


def deliver(db, destination, limit, number):
    """Write complete machine outputs and a bounded user-facing report before more pivots."""
    settings_path = destination / 'case-settings.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
    display_zone = settings.get('display_timezone') or default_timezone()
    fields = ['event_id', 'timestamp_utc', 'timestamp_display', 'display_timezone', 'timestamp_raw', 'time_field', 'timezone_basis',
              'orchestrator', 'family', 'source', 'record', 'host', 'user', 'profile',
              'matched_leads', 'observation', 'confidence', 'data']
    with (destination / 'timeline.jsonl').open('w', encoding='utf-8') as lines, \
         (destination / 'timeline.csv').open('w', encoding='utf-8', newline='') as table, \
         (destination / 'untimed.jsonl').open('w', encoding='utf-8') as untimed:
        writer = csv.DictWriter(table, fieldnames=fields)
        writer.writeheader()
        for utc, payload in db.execute('select utc,event from events order by utc is null,utc,source,record,field'):
            event = json.loads(payload)
            event['timestamp_display'] = display_timestamp(event['timestamp_utc'], display_zone)
            event['display_timezone'] = display_zone
            if utc is None:
                untimed.write(json.dumps(event, ensure_ascii=False) + '\n')
            else:
                lines.write(json.dumps(event, ensure_ascii=False) + '\n')
                writer.writerow({k: json.dumps(event[k], ensure_ascii=False) if isinstance(event[k], (dict, list)) else event[k] for k in fields})
    total, timed = db.execute('select count(*),count(utc) from events').fetchone()
    with (destination / 'report.md').open('w', encoding='utf-8') as report:
        report.write(f'# Investigation timeline\n\nCompleted round: {number}. Observations: {total}; timed: {timed}; untimed: {total-timed}.\n\n')
        report.write('This is an evidence timeline. Matching an initial hypothesis does not establish compromise. Validate host, user, profile, executable identity and timestamp semantics before inferring causation. Missing attribution stays blank.\n\n')
        report.write('## Scope and coverage\n\n')
        for round_id, scope in db.execute('select * from rounds order by id'):
            report.write(f'### Round {round_id}\n\n```json\n{scope}\n```\n\n')
        report.write(f'## Timeline\n\nDisplay timezone: `{display_zone}`. UTC and raw timestamps are retained in exports.\n\n| Selected timezone | Source / record | Time semantics | Observation |\n|---|---|---|---|\n')
        for payload, in db.execute('select event from events where utc is not null order by utc,source,record,field limit ?', (limit,)):
            e = json.loads(payload)
            report.write('| ' + ' | '.join(cell(v, 700) for v in [display_timestamp(e['timestamp_utc'], display_zone), f"{e['orchestrator']}: {e['source']} / {e['record']}", e['time_field'], e['observation']]) + ' |\n')
        report.write(f'\nDisplayed up to {limit} timed events. Full timed records are in timeline.jsonl and timeline.csv; untimed observations are in untimed.jsonl. Records retain original fields and citations. Counts include separate timestamp fields as separate observations.\n\n')
        report.write('## Next leads\n\n| Kind | Value | Origin | Status |\n|---|---|---|---|\n')
        for kind, value, origin, status in db.execute('select kind,value,origin,status from leads order by round,id limit ?', (limit,)):
            report.write('| ' + ' | '.join(cell(v, 400) for v in [kind, value, origin, status]) + ' |\n')
        report.write('\nFull lead provenance and search acknowledgments are in leads.json. Candidate leads need relevance review. Zero matches do not establish absence; inspect source errors, malformed rows, unknown schemas, skipped timestamps, and excluded companion exports.\n')
    export_leads(db, destination)
    deliver_triage(destination)
    build_dashboard(destination)


def deliver_triage(destination):
    """A bounded index lets the analyst select evidence without reading whole exports."""
    sources = {}
    for name in ADAPTERS:
        paths = sorted((destination / name).glob('round-*/triage-summary.json'))
        if paths:
            path = paths[-1]
            sources[name] = dict(summary=str(path), **json.loads(path.read_text(encoding='utf-8')))
    if not sources:
        return
    # Compact path references avoid repeating long acquisition paths in model context.
    references, brief = {}, {}
    def citation(sample):
        path = sample.get('source', '')
        if path not in references:
            references[path] = 'S' + str(len(references) + 1)
        times = sample.get('times', [])
        timed = sorted((t for t in times if t.get('utc')), key=lambda t: t['utc'])
        boundaries = ([timed[0]] if timed[0] == timed[-1] else [timed[0], timed[-1]]) if timed else times[:1]
        return dict(source=references[path], record=sample.get('record'), host=sample.get('host'),
                    user=sample.get('user'), times=boundaries)
    for name, summary in sources.items():
        categories = {}
        for category, entries in summary['categories'].items():
            categories[category] = [dict(subject=e['subject'], count=e['count'],
                first_utc=e['first_utc'], last_utc=e['last_utc'],
                citations=[citation(s) for s in e['evidence']],
                identifiers=[dict(tool=s['details']['tool'],
                                  domains=[dict(value=d['value'], triage=d.get('screenconnect_triage')) for d in s['details'].get('domains', [])],
                                  ips=[d['value'] for d in s['details'].get('ips', [])],
                                  ids=s['details'].get('identifiers', []))
                             for s in e['evidence'] if s.get('details', {}).get('tool')]) for e in entries]
        brief[name] = dict(counts=summary['counts'], groups=summary['groups'], summary=summary['summary'], categories=categories)
    dump(destination / 'case-brief.json', dict(sources=brief, references={v:k for k,v in references.items()}))
    settings = json.loads((destination / 'case-settings.json').read_text(encoding='utf-8')) if (destination / 'case-settings.json').exists() else {}
    display_zone = settings.get('display_timezone') or default_timezone()
    with (destination / 'triage.md').open('w', encoding='utf-8') as output:
        output.write('# Incident triage index\n\nThese are review priorities, not malware verdicts. Earliest observed activity is limited by acquisition coverage; the oldest artifact is not necessarily initial access.\n\n')
        for name, summary in sources.items():
            output.write(f'## {name}\n\nFull grouped evidence: `{summary["summary"]}` and sibling `triage-groups.jsonl`. Counts represent classified records, not necessarily unique actions.\n\n')
            for category, entries in sorted(summary['categories'].items(), key=lambda item: -max((e.get('priority', 0) for e in item[1]), default=0)):
                output.write(f'### {category} ({summary["counts"][category]})\n\n')
                for entry in entries[:5]:
                    sample = entry['evidence'][0] if entry['evidence'] else {}
                    ref = references.get(sample.get('source', ''), '')
                    first_display = display_timestamp(entry["first_utc"], display_zone) or "unverified"
                    last_display = display_timestamp(entry["last_utc"], display_zone) or "unverified"
                    output.write(f'- {cell(entry["subject"], 140)}; {display_zone} {first_display} to {last_display}; count {entry["count"]}; {ref} / record {sample.get("record", "")}\n')
                output.write('\n')
        output.write('## Source references\n\n')
        for path, ref in references.items():
            output.write(f'- {ref}: `{path}`\n')


def scan(db, name, root, leads, args, destination, number):
    coverage = []
    counts = dict(matched_records=0, events=0, invalid_or_unknown_times=0,
                  outside_bounds=0, candidates_omitted=0)
    inbox = [{'id': lead[0], 'value': lead[1]} for lead in leads]
    source_dir = destination / name / f'round-{number:04d}'
    source_dir.mkdir(parents=True, exist_ok=True)
    dump(source_dir / 'inbox.json', {'leads': inbox, 'input': str(root)})
    proposals = 0
    policy = TimestampPolicy(getattr(args, 'source_timezones', {}), args.assume_utc)
    triage = Triage(db, args.assume_utc, args.start, args.end, policy) if getattr(args, 'triage', True) else None
    # A single literal prefilter avoids comparing every lead with every field on nonmatches.
    prefilter = re.compile('|'.join(re.escape(value.casefold()) for _, value in leads)) if leads else None
    with (source_dir / 'events.jsonl').open('w', encoding='utf-8') as output:
        for record in ADAPTERS[name](root, args.encoding, coverage):
            categories = triage.observe(record, name) if triage else []
            values = [str(v).casefold() for v in record['data'].values()] if prefilter else []
            matched = ([key for key, value in leads if any(value.casefold() in v for v in values)]
                       if prefilter and any(prefilter.search(value) for value in values) else [])
            if not matched and not categories:
                continue
            counts['matched_records'] += 1
            evidence = {'source': record['source'], 'record': record['record']}
            # Extract only from records in the requested time scope, unless untimed.
            eligible = not record['times']
            events = []
            for field, raw, explicit_utc in record['times'] or [('', '', False)]:
                utc, time_basis = policy.resolve(raw, record['family'], field, explicit_utc,
                                                record.get('timezone_bases', {}).get(field))
                if raw and utc is None:
                    counts['invalid_or_unknown_times'] += 1
                if utc and ((args.start and utc < args.start) or (args.end and utc > args.end)):
                    counts['outside_bounds'] += 1
                    continue
                eligible = True
                key = identity(name, record['source'], record['record'], field, raw)
                observation = '; '.join(f'{k}={v}' for k, v in record['data'].items() if v not in ('', None))
                if not matched:
                    observation = observation[:1200]
                event = dict(event_id=key, timestamp_utc=utc, timestamp_raw=raw,
                             time_field=field, timezone_basis=time_basis,
                             orchestrator=name, family=record['family'], source=record['source'],
                             record=record['record'], host=record['host'], user=record['user'],
                             profile=record['profile'], matched_leads=matched,
                             observation=observation, confidence='observed artifact; significance unassessed',
                             data=record['data'])
                if categories:
                    event['triage_categories'] = categories
                previous = db.execute('select event from events where id=?', (key,)).fetchone()
                if previous:
                    event['matched_leads'] = sorted(set(matched + json.loads(previous[0])['matched_leads']))
                db.execute('insert or replace into events values(?,?,?,?,?,?)',
                           (key, utc, record['source'], record['record'], field, json.dumps(event, ensure_ascii=False)))
                output.write(json.dumps(event, ensure_ascii=False) + '\n')
                events.append(key)
                counts['events'] += 1
            # Unreviewed background triage must not flood the shared queue with every URL.
            if eligible and matched:
                for kind, value in candidates(record['data']):
                    if db.execute('select 1 from leads where id=?', (identity(kind, value.casefold()),)).fetchone():
                        continue
                    if proposals >= args.max_candidates:
                        counts['candidates_omitted'] += 1
                        continue
                    add_lead(db, kind, value, name, dict(evidence, event_ids=events, parent_leads=matched), 'candidate', number)
                    proposals += 1
    # Failed or malformed sources remain retryable instead of acknowledging incomplete work.
    if coverage and not any(c.get('error') or c.get('malformed') for c in coverage):
        for key, _ in leads:
            db.execute('insert or ignore into searched values(?,?)', (key, identity(name, str(root))))
        if triage:
            db.execute('insert or ignore into searched values(?,?)', ('__triage_v2_timezones__', identity(name, str(root))))
    summary = dict(orchestrator=name, input=str(root), coverage=coverage, **counts)
    if triage:
        summary['triage'] = triage.finish(source_dir)
    if not coverage:
        summary['error'] = 'No supported exports discovered'
    dump(source_dir / 'coverage.json', summary)
    dump(source_dir / 'outbox.json', {'leads': [dict(id=k, kind=t, value=v, evidence=json.loads(e)) for k,t,v,e in db.execute('select id,kind,value,evidence from leads where origin=? and round=?', (name, number))]})
    return summary


def scan_isolated(name, root, leads, args, destination, number, seed_leads):
    """Each worker owns its connection and source artifacts; no shared case writes."""
    source_dir = destination / name / f'round-{number:04d}'
    source_dir.mkdir(parents=True, exist_ok=True)
    # A failed, uncommitted round can be retried using the same round number.
    staging = source_dir / 'scan.sqlite'
    staging.unlink(missing_ok=True)
    db = sqlite3.connect(str(staging))
    try:
        initialize(db)
        db.executemany('insert into leads values(?,?,?,?,?,?,?)', seed_leads)
        summary = scan(db, name, root, leads, args, destination, number)
        db.commit()
        return summary
    finally:
        db.close()


def merge_scan(db, destination, name, number):
    """Merge on the coordinator thread, preserving prior matches and first provenance."""
    staging = destination / name / f'round-{number:04d}' / 'scan.sqlite'
    source = sqlite3.connect(str(staging))
    try:
        for key, utc, path, record, field, payload in source.execute('select * from events'):
            event = json.loads(payload)
            previous = db.execute('select event from events where id=?', (key,)).fetchone()
            if previous:
                event['matched_leads'] = sorted(set(event['matched_leads'] + json.loads(previous[0])['matched_leads']))
            db.execute('insert or replace into events values(?,?,?,?,?,?)',
                       (key, utc, path, record, field, json.dumps(event, ensure_ascii=False)))
        db.executemany('insert or ignore into leads values(?,?,?,?,?,?,?)',
                       source.execute('select * from leads'))
        db.executemany('insert or ignore into searched values(?,?)',
                       source.execute('select * from searched'))
    finally:
        source.close()


def execute(args, only=None):
    started = perf_counter()
    args.triage = getattr(args, 'triage', True)
    sources = {}
    if only:
        sources[only] = args.input
    else:
        for source in args.source:
            if '=' not in source:
                raise ValueError('--source requires NAME=PATH')
            name, path = source.split('=', 1)
            if name not in ADAPTERS:
                raise ValueError(f'Unknown adapter {name}; register it in investigation_core/adapters.py')
            if name in sources:
                raise ValueError('Use one root per adapter; put multiple acquisitions beneath that root')
            sources[name] = path
    if not sources:
        raise ValueError('Provide at least one evidence source')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', args.case):
        raise ValueError('Case must be a simple name, up to 80 characters')
    destination = configured_destination(args, sources)
    settings_path = destination / 'case-settings.json'
    previous_settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
    display_zone = getattr(args, 'timezone', None) or previous_settings.get('display_timezone') or default_timezone()
    zone(display_zone)
    specified_rules = getattr(args, 'source_timezone', None)
    args.source_timezones = source_rules(specified_rules) if specified_rules is not None else previous_settings.get('source_timezones', {})
    if args.source_timezones != previous_settings.get('source_timezones', {}):
        args.rescan = True
    for path in sources.values():
        evidence = Path(path).resolve()
        if not evidence.exists():
            raise ValueError(f'Input does not exist: {evidence}')
        if destination == evidence or (evidence.is_dir() and destination.is_relative_to(evidence)):
            raise ValueError('agent_output must be outside all evidence roots')
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / '.writer.lock'
    try:
        handle = lock.open('x', encoding='utf-8')
    except FileExistsError:
        raise ValueError(f'Case already has a writer. If interrupted, verify it stopped before removing {lock}')
    db = None
    try:
        handle.close()
        dump(settings_path, dict(display_timezone=display_zone, source_timezones=args.source_timezones))
        db = sqlite3.connect(str(destination / 'investigation.sqlite'))
        initialize(db)
        number = db.execute('select coalesce(max(id),0)+1 from rounds').fetchone()[0]
        if not args.triage and not args.lead and not args.leads_file and not db.execute('select 1 from leads').fetchone():
            raise ValueError('Provide --lead or --leads-file for the initial investigation')
        for value in args.lead:
            if not value.strip():
                raise ValueError('Empty leads are not allowed')
            key = add_lead(db, 'keyword', value, 'user', {}, 'active', number)
            db.execute("update leads set status='active' where id=?", (key,))
        if args.leads_file:
            payload = json.loads(Path(args.leads_file).read_text(encoding='utf-8-sig'))
            for lead in payload['leads']:
                value = str(lead['value'])
                if not value.strip():
                    raise ValueError('Empty imported lead')
                status = lead.get('status', 'active')
                if status not in {'active', 'candidate', 'rejected'}:
                    raise ValueError(f'Unknown lead status: {status}')
                key = add_lead(db, lead.get('kind', 'keyword'), value, lead.get('origin', 'import'),
                               lead.get('evidence', {}), status, number)
                db.execute('update leads set status=? where id=?', (status, key))
        if args.follow_candidates:
            db.execute("update leads set status='active' where status='candidate'")
        leads = list(db.execute("select id,value from leads where status='active' order by id"))
        if len(leads) > args.max_leads:
            raise ValueError(f'{len(leads)} active leads exceed --max-leads {args.max_leads}; review or increase the limit')
        if not leads and not args.triage:
            raise ValueError('No active leads; use --follow-candidates or import reviewed leads')
        jobs = []
        summaries = {}
        for name, root in sources.items():
            token = identity(name, str(Path(root).resolve()))
            pending = leads if args.rescan else [(k,v) for k,v in leads if not db.execute('select 1 from searched where lead=? and source=?', (k,token)).fetchone()]
            triage_needed = args.triage and (args.rescan or not db.execute(
                'select 1 from searched where lead=? and source=?', ('__triage_v2_timezones__', token)).fetchone())
            if pending or triage_needed:
                jobs.append((name, Path(root).resolve(), pending))
            else:
                summaries[name] = dict(orchestrator=name, input=root, skipped='All active leads already searched; --rescan if evidence or scope changed')
        seed_leads = list(db.execute('select * from leads'))
        workers = min(args.workers, len(jobs))
        if jobs:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [(name, pool.submit(scan_isolated, name, root, pending, args,
                                               destination, number, seed_leads))
                           for name, root, pending in jobs]
                # All scans are submitted first. Result collection does not serialize scans.
                for name, future in futures:
                    summaries[name] = future.result()
            for name, _, _ in jobs:
                merge_scan(db, destination, name, number)
                summary = summaries[name]
                if summary.get('error') or any(c.get('error') or c.get('malformed') for c in summary.get('coverage', [])):
                    db.execute('delete from searched where source=?', (identity(name, str(Path(sources[name]).resolve())),))
        summaries = [summaries[name] for name in sources]
        scope = dict(leads=[v for _,v in leads], start=args.start, end=args.end,
                     assume_utc=args.assume_utc, encoding=args.encoding,
                     scan_workers=workers, triage=args.triage, sources=summaries)
        scope['display_timezone'] = display_zone
        scope['source_timezones'] = args.source_timezones
        db.execute('insert into rounds values(?,?)', (number, json.dumps(scope, ensure_ascii=False, indent=2)))
        db.commit()
        deliver(db, destination, args.limit, number)
        compact_sources = []
        for summary in summaries:
            compact = {k: v for k, v in summary.items() if k != 'coverage'}
            compact['files_scanned'] = len(summary.get('coverage', []))
            compact['records_scanned'] = sum(c.get('scanned', 0) for c in summary.get('coverage', []))
            compact['coverage_report'] = str(destination / summary['orchestrator'] / f'round-{number:04d}' / 'coverage.json')
            compact['input_errors'] = [dict(source=c['source'], error=c.get('error'), malformed=c.get('malformed', 0))
                                       for c in summary.get('coverage', []) if c.get('error') or c.get('malformed')]
            compact_sources.append(compact)
        print(json.dumps({'dashboard': str(destination / 'dashboard.html'), 'report': str(destination / 'report.md'),
                          'triage': str(destination / 'triage.md') if (destination / 'triage.md').exists() else None,
                          'round': number, 'elapsed_seconds': round(perf_counter() - started, 3), 'sources': compact_sources}))
        return 2 if any(s.get('error') or any(c.get('error') or c.get('malformed') for c in s.get('coverage', [])) for s in summaries) else 0
    finally:
        if db:
            db.close()
        lock.unlink(missing_ok=True)


def run(only=None):
    parser = argparse.ArgumentParser(description=__doc__)
    if only:
        parser.add_argument('input', nargs='?')
    else:
        parser.add_argument('--source', action='append', default=[], help='kape=PATH or hindsight=PATH')
    parser.add_argument('--case', default=datetime.now(timezone.utc).strftime('case-%Y%m%dT%H%M%S%fZ'))
    parser.add_argument('--output-root', help='Legacy parent folder; case name is appended')
    parser.add_argument('--output-directory', help='Exact output folder; overrides installed output location')
    parser.add_argument('--lead', action='append', default=[])
    parser.add_argument('--leads-file')
    parser.add_argument('--follow-candidates', action='store_true')
    parser.add_argument('--rescan', action='store_true')
    parser.add_argument('--leads-only', dest='triage', action='store_false', default=True,
                        help='Disable automatic incident triage and search only explicit leads')
    parser.add_argument('--workers', type=int, default=2,
                        help='Concurrent isolated source scans (default: 2; use 1 for sequential scans)')
    parser.add_argument('--max-candidates', type=int, default=200)
    parser.add_argument('--max-leads', type=int, default=500)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--encoding', default='utf-8-sig')
    parser.add_argument('--assume-utc', action='store_true')
    parser.add_argument('--timezone', help='Display timezone: IANA name, UTC or fixed offset; overrides case/installation default')
    parser.add_argument('--source-timezone', action='append', default=None, metavar='FAMILY.FIELD=ZONE',
                        help='Verified source interpretation for naive timestamps; repeatable; wildcards supported')
    parser.add_argument('--list-timezones', action='store_true')
    parser.add_argument('--start')
    parser.add_argument('--end')
    args = parser.parse_args()
    if args.list_timezones:
        print('\n'.join(list_zones()))
        return 0
    if only and not args.input:
        parser.error('input is required')
    if min(args.limit, args.max_candidates, args.max_leads, args.workers) < 1:
        parser.error('Limits must be positive')
    for bound in ('start', 'end'):
        value = getattr(args, bound)
        if value:
            normalized = stamp(value, False)
            if not normalized:
                parser.error('Time bounds must have explicit offsets')
            setattr(args, bound, normalized)
    if args.start and args.end and args.start > args.end:
        parser.error('Start must precede end')
    try:
        return execute(args, only)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2

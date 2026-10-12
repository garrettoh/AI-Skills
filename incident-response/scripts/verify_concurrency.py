"""Verify overlapping real source scans, deterministic merging, and case isolation."""
import argparse
import contextlib
import csv
import io
import json
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path, required=True)
    root = parser.parse_args().skills_root.resolve()
    sys.path[:0] = [str(root), str(root / 'kape_analysis')]
    from investigation_core import workflow

    with tempfile.TemporaryDirectory(prefix='concurrent-investigation-') as temporary:
        work = Path(temporary)
        kape, browser = work / 'kape', work / 'browser'
        kape.mkdir()
        browser.mkdir()
        url = 'https://example.invalid/drop.exe'
        with (kape / 'events.csv').open('w', encoding='utf-8', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['EventId', 'TimeCreated', 'Provider', 'Computer', 'Payload'])
            writer.writerow(['1', '2026-01-02T03:04:05Z', 'test', 'host-a', f'FleetDeck {url}'])
        (browser / 'chrome.jsonl').write_text(json.dumps(dict(
            datetime='2026-01-02T03:04:04Z', timestamp_desc='Visit Time',
            data_type='chrome:history:page_visited', profile='profile-a',
            url=url, message='FleetDeck visit')) + '\n', encoding='utf-8')

        def options(case, workers, lead='fleetdeck'):
            return argparse.Namespace(source=[f'kape={kape}', f'hindsight={browser}'],
                case=case, output_root=str(work / 'output'), lead=[lead], leads_file=None,
                follow_candidates=False, rescan=False, workers=workers, max_candidates=200,
                max_leads=500, limit=100, encoding='utf-8-sig', assume_utc=False,
                start=None, end=None)

        def run(args):
            with contextlib.redirect_stdout(io.StringIO()):
                assert workflow.execute(args) == 0

        originals = dict(workflow.ADAPTERS)
        barrier = threading.Barrier(2, timeout=10)
        threads = set()
        guard = threading.Lock()

        def overlapping(adapter):
            def wrapped(source, encoding, coverage):
                with guard:
                    threads.add(threading.get_ident())
                # Each adapter must enter before either can read its evidence.
                barrier.wait()
                assert (work / 'output/parallel/.writer.lock').exists()
                # A second coordinator cannot write this case during worker scans.
                try:
                    workflow.execute(options('parallel', 2))
                except ValueError as exc:
                    assert 'already has a writer' in str(exc)
                else:
                    raise AssertionError('Concurrent case writer accepted')
                yield from adapter(source, encoding, coverage)
            return wrapped

        try:
            workflow.ADAPTERS.update({name: overlapping(adapter) for name, adapter in originals.items()})
            run(options('parallel', 2))
            assert len(threads) == 2, 'Source scans did not use separate workers'
        finally:
            workflow.ADAPTERS.clear()
            workflow.ADAPTERS.update(originals)
        run(options('sequential', 1))
        parallel = work / 'output/parallel'
        sequential = work / 'output/sequential'
        for filename in ('timeline.jsonl', 'timeline.csv', 'untimed.jsonl', 'leads.json'):
            assert (parallel / filename).read_bytes() == (sequential / filename).read_bytes(), filename
        for name in ('kape', 'hindsight'):
            staging = parallel / name / 'round-0001/scan.sqlite'
            assert staging.exists(), 'Source staging database missing'
            proposals = json.loads((staging.parent / 'outbox.json').read_text())['leads']
            assert any(lead['value'] == url for lead in proposals), 'Source proposal provenance lost'
        with contextlib.closing(sqlite3.connect(parallel / 'investigation.sqlite')) as db:
            scope = json.loads(db.execute('select scope from rounds').fetchone()[0])
            assert scope['scan_workers'] == 2
            assert db.execute('select count(*) from searched').fetchone()[0] == 2
            assert db.execute('select count(*) from leads where kind="url"').fetchone()[0] == 1
        # New lead searches must union prior event matches rather than replace them.
        run(options('parallel', 2, url))
        run(options('sequential', 1, url))
        assert (parallel / 'timeline.jsonl').read_bytes() == (sequential / 'timeline.jsonl').read_bytes()
        events = [json.loads(line) for line in (parallel / 'timeline.jsonl').read_text().splitlines()]
        assert len(events) == 2 and all(len(event['matched_leads']) == 2 for event in events)

        def failed(source, encoding, coverage):
            raise OSError('Simulated source failure')
            yield

        workflow.ADAPTERS['hindsight'] = failed
        try:
            try:
                run(options('retry', 2))
            except OSError as exc:
                assert 'Simulated source failure' in str(exc)
            else:
                raise AssertionError('Worker error was hidden')
        finally:
            workflow.ADAPTERS.update(originals)
        assert not (work / 'output/retry/.writer.lock').exists()
        run(options('retry', 2))
        assert len((work / 'output/retry/timeline.jsonl').read_text().splitlines()) == 2
    print('PASS: real source scans overlap; isolated staging, case lock, deterministic merge, shared lead deduplication, match union, and failed-round retry')


if __name__ == '__main__':
    main()

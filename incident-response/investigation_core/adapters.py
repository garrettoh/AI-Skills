"""Streaming adapters for parsed KAPE and Hindsight exports."""
import json
import posixpath
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from kape_core.cli import reader
from kape_core.schemas import classify, verified_utc

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def discover(root, suffixes):
    root = Path(root).resolve()
    if not root.exists():
        raise ValueError(f'Input does not exist: {root}')
    paths = [root] if root.is_file() else sorted(root.rglob('*'))
    return [p for p in paths if p.is_file() and p.suffix.lower() in suffixes]


def kape(root, encoding, coverage):
    for path in discover(root, {'.csv'}):
        entry = {'source': str(path), 'scanned': 0, 'malformed': 0}
        coverage.append(entry)
        stream = None
        try:
            stream, rows, headers = reader(path, encoding)
            profile = classify(headers, path.name)
            entry.update(profile, headers=headers)
            for number, row in enumerate(rows, 2):
                entry['scanned'] += 1
                if None in row or any(v is None for v in row.values()):
                    entry['malformed'] += 1
                    continue
                yield {'source': str(path), 'record': str(number), 'data': row,
                       'family': profile['family'],
                       'times': [(f, row[f], verified_utc(profile, f)) for f in profile['time_fields'] if row[f]],
                       'host': row.get('Computer', row.get('ComputerName', '')),
                       'user': row.get('UserName', row.get('Sid', '')), 'profile': ''}
        except Exception as exc:
            entry['error'] = str(exc)
        finally:
            if stream:
                stream.close()


def xlsx_rows(path):
    """Disk-backed shared strings and streaming worksheets with sheet/row citations."""
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix='hindsight-xlsx-') as td:
        db = sqlite3.connect(str(Path(td) / 'strings.db'))
        try:
            db.execute('create table strings(id integer primary key, value text)')
            if 'xl/sharedStrings.xml' in archive.namelist():
                with archive.open('xl/sharedStrings.xml') as source:
                    context = ET.iterparse(source, events=('start', 'end'))
                    _, root = next(context)
                    index = 0
                    for event, node in context:
                        if event == 'end' and node.tag == NS + 'si':
                            value = ''.join(t.text or '' for t in node.iter(NS + 't'))
                            db.execute('insert into strings values(?,?)', (index, value))
                            index += 1
                            root.clear()
                db.commit()
            relations = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            targets = {n.attrib['Id']: n.attrib['Target'] for n in relations}
            workbook = ET.fromstring(archive.read('xl/workbook.xml'))
            for sheet in workbook.find(NS + 'sheets'):
                target = targets[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
                member = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
                headers = None
                with archive.open(member) as source:
                    sheet_data = None
                    for event, node in ET.iterparse(source, events=('start', 'end')):
                        if event == 'start' and node.tag == NS + 'sheetData':
                            sheet_data = node
                        if event != 'end' or node.tag != NS + 'row':
                            continue
                        values = {}
                        for cell in node.findall(NS + 'c'):
                            column = re.match(r'[A-Z]+', cell.attrib['r'])[0]
                            kind = cell.attrib.get('t')
                            value = cell.findtext(NS + 'v', '')
                            if kind == 's':
                                value = db.execute('select value from strings where id=?', (int(value),)).fetchone()[0]
                            elif kind == 'inlineStr':
                                value = ''.join(t.text or '' for t in cell.iter(NS + 't'))
                            values[column] = value
                        if headers is None:
                            lowered = {v.casefold() for v in values.values()}
                            if lowered & {'type', 'url', 'name', 'key', 'setting', 'origin'} and len(lowered) > 2:
                                headers = {k: v for k, v in values.items() if v}
                        else:
                            yield sheet.attrib['name'], int(node.attrib['r']), {v: values.get(k, '') for k, v in headers.items()}
                        node.clear()
                        if sheet_data is not None:
                            sheet_data.clear()
                if headers is None:
                    yield sheet.attrib['name'], 0, None
        finally:
            db.close()


def hindsight(root, encoding, coverage):
    paths = discover(root, {'.jsonl', '.xlsx'})
    def stem(path):
        name = path.name.casefold()
        while name.endswith(('.jsonl', '.xlsx')):
            name = name.rsplit('.', 1)[0]
        return (path.parent, name)
    json_stems = {stem(p) for p in paths if p.suffix.lower() == '.jsonl'}
    for path in paths:
        entry = {'source': str(path), 'scanned': 0, 'malformed': 0}
        coverage.append(entry)
        if path.suffix.lower() == '.xlsx' and stem(path) in json_stems:
            entry['excluded'] = 'Companion JSONL preferred. XLSX may contain additional storage sheets; search XLSX directly if needed.'
            continue
        try:
            if path.suffix.lower() == '.jsonl':
                with path.open(encoding=encoding) as source:
                    for number, line in enumerate(source, 1):
                        if not line.strip():
                            continue
                        entry['scanned'] += 1
                        try:
                            row = json.loads(line)
                            if not isinstance(row, dict):
                                raise ValueError('Record is not an object')
                        except (ValueError, TypeError):
                            entry['malformed'] += 1
                            continue
                        yield h_record(path, str(number), row)
            else:
                for sheet, number, row in xlsx_rows(path):
                    if row is None:
                        entry.setdefault('unsupported_sheets', []).append(sheet)
                        continue
                    entry['scanned'] += 1
                    yield h_record(path, f'{sheet}!{number}', row)
        except Exception as exc:
            entry['error'] = str(exc)


def h_record(path, number, row):
    times = []
    if row.get('datetime'):
        times.append((str(row.get('timestamp_desc', 'datetime')), str(row['datetime']), False))
    for field in ('Timestamp (UTC)', 'Last Modified', 'Date Created', 'Last Accessed', 'Last Modified (UTC)'):
        if row.get(field):
            times.append((field, str(row[field]), '(UTC)' in field))
    return {'source': str(path), 'record': number, 'data': row,
            'family': str(row.get('data_type', row.get('Type', 'hindsight-storage'))),
            'times': times, 'host': str(row.get('host', '')),
            'user': str(row.get('user', '')), 'profile': str(row.get('profile', row.get('Profile', '')))}


ADAPTERS = {'kape': kape, 'hindsight': hindsight}

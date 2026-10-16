"""Build Nord incident Excalidraw scenes from a reviewed brief; optionally render PNGs locally."""
import argparse
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from zoneinfo import ZoneInfo

FORMATS = ('storyboard', 'timeline', 'technical', 'network', 'data-flow', 'identity')
STATUS = {'observed': '#88C0D0', 'supported': '#A3BE8C', 'uncertain': '#EBCB8B', 'unknown': '#AAB4C3'}
BG, PANEL, BORDER, TEXT, MUTED = '#2E3440', '#3B4252', '#4C566A', '#ECEFF4', '#D8DEE9'


def read_json(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError(f'Expected a bounded visual brief/overview, not a raw evidence export: {path}')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def string(value, name, limit, required=True):
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > limit:
        raise ValueError(f'{name}: expected {"nonempty " if required else ""}text, at most {limit} characters')
    return value


def timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('time must be an ISO offset timestamp or null')
    instant = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f'Timestamp needs a verified UTC offset: {value}')
    return instant


def evidence(item):
    refs = item.get('evidence')
    if not isinstance(refs, list) or not refs or len(refs) > 20:
        raise ValueError(f'{item.get("id")}: nonempty evidence reference list required (max 20)')
    for ref in refs:
        string(ref, 'evidence reference', 500)


def validate(brief):
    if not isinstance(brief, dict) or brief.get('schema_version') != 1 or brief.get('reviewed') is not True:
        raise ValueError('Expected schema_version 1 and reviewed: true; review the draft against the analysis first')
    string(brief.get('title'), 'title', 100)
    string(brief.get('subtitle', ''), 'subtitle', 180, False)
    display_zone = ZoneInfo(brief.get('timezone', 'UTC'))
    for key, limit in [('events', 24), ('entities', 18), ('relationships', 24)]:
        items = brief.get(key, [])
        if not isinstance(items, list) or len(items) > limit or any(not isinstance(i, dict) for i in items):
            raise ValueError(f'{key}: expected at most {limit} objects')
        ids = [string(i.get('id'), f'{key}.id', 80) for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError(f'{key}: duplicate IDs')
    all_ids = [i['id'] for key in ('events', 'entities', 'relationships') for i in brief.get(key, [])]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError('IDs must be unique across events, entities and relationships for unambiguous provenance')
    entities = {e['id']: e for e in brief.get('entities', [])}
    for entity in entities.values():
        string(entity.get('label'), 'entity label', 64)
        string(entity.get('kind'), 'entity kind', 32)
    for event in brief.get('events', []):
        string(event.get('title'), 'event title', 64)
        for field, limit in [('summary', 160), ('technical', 240), ('lane', 60), ('time_label', 80)]:
            string(event.get(field, ''), field, limit, False)
        if 'milestone' in event and type(event['milestone']) is not bool:
            raise ValueError('milestone must be true or false')
    for link in brief.get('relationships', []):
        if link.get('source') not in entities or link.get('target') not in entities:
            raise ValueError(f'{link["id"]}: relationship endpoints must identify existing entities')
        if link['source'] == link['target']:
            raise ValueError(f'{link["id"]}: self links are not supported by these overview layouts')
        if link.get('category') not in {'movement', 'data', 'identity'}:
            raise ValueError('relationship category must be movement, data or identity')
        if link['category'] == 'movement' and any(entities[link[k]]['kind'] != 'host' for k in ('source', 'target')):
            raise ValueError('Movement relationships must connect two host entities')
        string(link.get('label'), 'relationship label', 72)
        string(link.get('time_label', ''), 'time_label', 80, False)
    for item in brief.get('events', []) + brief.get('relationships', []):
        if 'time' not in item:
            raise ValueError(f'{item["id"]}: time must be present (null for unknown)')
        timestamp(item['time'])
        if item.get('status', 'observed') not in STATUS:
            raise ValueError(f'{item["id"]}: unknown status')
        evidence(item)
    return display_zone


def time_text(item, zone):
    instant = timestamp(item.get('time'))
    normalized = instant.astimezone(zone).strftime('%b %d, %Y %H:%M:%S %Z') if instant else 'Time unknown'
    label = item.get('time_label')
    return f'{label} · {normalized}' if label else normalized


def sorted_events(brief):
    def order(event):
        instant = timestamp(event.get('time'))
        return instant.astimezone(dt.timezone.utc) if instant else dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    return sorted(brief.get('events', []), key=order)


class Scene:
    def __init__(self, title, subtitle):
        self.elements, self.mapping = [], {}
        height = self.text(title, 56, 32, 1488, 32)
        if subtitle:
            self.text(subtitle, 58, 32+height+12, 1480, 17, MUTED)

    def base(self, kind, x, y, w, h, stroke, fill='transparent', width=1, style='solid'):
        n = len(self.elements)
        element = dict(id=f'v{n}', type=kind, x=x, y=y, width=w, height=h, angle=0,
                       strokeColor=stroke, backgroundColor=fill, fillStyle='solid', strokeWidth=width,
                       strokeStyle=style, roughness=0, opacity=100, groupIds=[], frameId=None,
                       roundness=None, seed=101+n, version=1, versionNonce=501+n,
                       isDeleted=False, boundElements=None, updated=1, link=None, locked=False)
        self.elements.append(element)
        return element

    def rect(self, x, y, w, h, color=BORDER, fill=PANEL):
        element = self.base('rectangle', x, y, w, h, color, fill)
        element['roundness'] = {'type': 3}
        return element

    def text(self, value, x, y, w, size=17, color=TEXT):
        # Conservative bounds for Helvetica; explicit line breaks survive Excalidraw exports.
        lines = []
        for paragraph in value.split('\n'):
            lines.extend(textwrap.wrap(paragraph, max(8, int(w/(size*.63))), break_long_words=True) or [''])
        value = '\n'.join(lines)
        height = max(1, len(lines))*size*1.3
        element = self.base('text', x, y, w, height, color)
        element.update(text=value, originalText=value, fontSize=size, fontFamily=2,
                       textAlign='left', verticalAlign='top', containerId=None, autoResize=False, lineHeight=1.3)
        return height

    def edge(self, points, label, color, dashed):
        x, y = points[0]
        rel = [[px-x, py-y] for px, py in points]
        element = self.base('arrow', x, y, points[-1][0]-x, points[-1][1]-y,
                            color, width=2, style='dashed' if dashed else 'solid')
        element.update(points=rel, startBinding=None, endBinding=None, startArrowhead=None,
                       endArrowhead='triangle', lastCommittedPoint=None, elbowed=False)
        self.mapping[element['id']] = label

    def event_card(self, event, x, y, w, h, zone, technical=False):
        color = STATUS[event.get('status', 'observed')]
        card = self.rect(x, y, w, h, color)
        self.mapping[card['id']] = event['id']
        offset = y+16
        offset += self.text(time_text(event, zone), x+18, offset, w-36, 14, MUTED)+12
        offset += self.text(event['title'], x+18, offset, w-36, 21, color)+12
        body = event.get('technical') or event.get('summary', '') if technical else event.get('summary', '')
        offset += self.text(body, x+18, offset, w-36, 17)+12
        if technical and event.get('lane'):
            offset += self.text(event['lane'], x+18, offset, w-36, 14, MUTED)+8
        offset += self.text(event.get('status', 'observed').upper(), x+18, offset, w-36, 12, color)
        card['height'] = max(h, offset-y+18)
        return card['height']

    def save(self, path):
        payload = dict(type='excalidraw', version=2, source='https://excalidraw.com', elements=self.elements,
                       appState=dict(viewBackgroundColor=BG, gridSize=None, exportBackground=True,
                                     exportWithDarkMode=False), files={})
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def events_view(brief, zone, fmt):
    scene = Scene(brief['title'], f'{fmt.upper()} · {brief.get("subtitle", "")} · {zone.key}')
    events = sorted_events(brief)
    omitted = []
    if fmt == 'storyboard':
        milestones = [e for e in events if e.get('milestone', False)] or events
        events, omitted = milestones[:6], [e['id'] for e in milestones[6:]]
        columns = min(4, len(events)) if len(events) <= 4 else 3
        widths = {1: 920, 2: 710, 3: 470, 4: 350}
        width = widths.get(columns, 470)
        y = 192
        for start in range(0, len(events), max(1, columns)):
            heights, cards = [], []
            for column, event in enumerate(events[start:start+columns]):
                index = len(scene.elements)
                heights.append(scene.event_card(event, 56+column*(width+26), y, width, 250, zone))
                cards.append(scene.elements[index])
            for card in cards:
                card['height'] = max(heights)
            y += max(heights)+28
    else:
        y = 192
        for event in events:
            # Full selected chronology. Per-event lanes work across hosts, cloud and identity cases.
            height = scene.event_card(event, 56, y, 1480, 120, zone, fmt == 'technical')
            y += height+20
    return scene, omitted


def usable_links(brief, fmt):
    category = {'network': 'movement', 'data-flow': 'data', 'identity': 'identity'}[fmt]
    links = [r for r in brief.get('relationships', []) if r['category'] == category]
    if fmt == 'network':
        entities = {e['id']: e for e in brief.get('entities', [])}
        # Require an actual reviewed host-to-host observation before offering a movement map.
        observed = [r for r in links if r.get('status', 'observed') == 'observed'
                    and entities[r['source']]['kind'] == entities[r['target']]['kind'] == 'host']
        if not observed:
            return []
    return links


def graph_view(brief, zone, fmt, links):
    scene = Scene(brief['title'], f'{fmt.upper()} · {brief.get("subtitle", "")} · {zone.key}')
    entities = {e['id']: e for e in brief.get('entities', [])}
    # One directed relationship per row avoids crossed labels and scales to multiple incidents.
    # Repeated node labels retain their identity; each row is a documented path, not a new host.
    for i, link in enumerate(links):
        y = 220+i*225
        color = STATUS[link.get('status', 'observed')]
        points = [(411, y+85), (1151, y+85)]
        scene.edge(points, link['id'], color, link.get('status', 'observed') in {'uncertain', 'unknown'})
        scene.text(link['label'], 455, y+15, 650, 19, color)
        scene.text(time_text(link, zone), 455, y+105, 650, 14, MUTED)
        scene.text(link.get('status', 'observed').upper(), 455, y+157, 650, 12, color)
        for key, x in [('source', 56), ('target', 1170)]:
            entity = entities[link[key]]
            box = scene.rect(x, y, 335, 165, '#81A1C1')
            scene.mapping[box['id']] = entity['id']
            scene.text(entity['kind'].upper(), x+16, y+12, 303, 12, MUTED)
            scene.text(entity['label'], x+16, y+46, 303, 20, TEXT)
    return scene


def render(scene, png, allow_npx):
    cli = shutil.which('excalidraw')
    if cli:
        command = [cli]
    elif allow_npx and shutil.which('npx'):
        command = [shutil.which('npx'), '--yes', '@excalidraw/cli']
    else:
        raise ValueError('Excalidraw CLI unavailable; install @excalidraw/cli or authorize --allow-npx; editable exports are available')
    # Temporary destination avoids CLI overwrite failures and preserves the last successful PNG on error.
    handle, temporary = tempfile.mkstemp(suffix='.png', prefix='render-', dir=png.parent)
    os.close(handle)
    temp = Path(temporary)
    temp.unlink()
    try:
        command += ['render', str(scene), '--out', str(temp), '--theme', 'light', '--fonts-url', 'none',
                    '--max-width', '3200', '--max-height', '8000']
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError(f'CLI render failed: {(result.stderr or result.stdout)[-1500:]}')
        if not temp.exists() or temp.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('CLI did not produce a PNG')
        temp.replace(png)
    finally:
        temp.unlink(missing_ok=True)


def gallery(output, manifest):
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
             '<title>Incident diagrams</title><style>body{background:#2e3440;color:#eceff4;font:16px system-ui;margin:32px}a{color:#88c0d0}article{background:#3b4252;padding:20px;margin:24px 0;border-radius:12px}img{max-width:100%;height:auto}p{line-height:1.5}</style>',
             '<h1>'+html.escape(manifest['title'])+'</h1><p>Reviewed incident views · <a href="manifest.json">Evidence references and export status</a> · <a href="brief.snapshot.json">Reviewed brief</a></p>']
    for entry in manifest['exports']:
        parts.append('<article><h2>'+html.escape(entry['format'])+'</h2><p><a href="'+entry['scene']+'">Editable Excalidraw</a></p>')
        if entry.get('png'):
            parts.append('<a href="'+entry['png']+'"><img alt="'+html.escape(entry['format'])+'" src="'+entry['png']+'"></a>')
        if entry.get('error'):
            parts.append('<p>'+html.escape(entry['error'])+'</p>')
        parts.append('</article>')
    for skipped in manifest['skipped']:
        parts.append('<p>'+html.escape(skipped['format']+': '+skipped['reason'])+'</p>')
    parts.append('</html>')
    (output/'index.html').write_text('\n'.join(parts), encoding='utf-8')


def prepare(case, output):
    overview = read_json(case/'overview.json')
    if not isinstance(overview, dict):
        raise ValueError('overview.json must contain an object')
    milestones = overview.get('milestones', [])
    if not isinstance(milestones, list) or len(milestones) > 24:
        raise ValueError('Select at most 24 milestones for the visual brief')
    draft = dict(schema_version=1, reviewed=False, title='Incident overview',
                 subtitle='', timezone='UTC', events=[], entities=[], relationships=[])
    for i, milestone in enumerate(milestones):
        if not isinstance(milestone, dict):
            raise ValueError('Overview milestones must be objects')
        ref = milestone.get('evidence', '')
        draft['events'].append(dict(id=f'e{i+1}', time=None, time_label=milestone.get('time', ''),
                                    title=milestone.get('title', ''), summary=milestone.get('description', ''),
                                    technical='', lane='', status='observed', milestone=True,
                                    evidence=ref if isinstance(ref, list) else [ref]))
    output.mkdir(parents=True, exist_ok=True)
    path = output/'diagram-brief.draft.json'
    if path.exists():
        raise ValueError(f'Draft already exists; review it instead of overwriting: {path}')
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Draft only; review titles, scope, descriptions, timestamps, statuses and citations: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief', type=Path)
    parser.add_argument('--case-dir', type=Path)
    parser.add_argument('--prepare', action='store_true', help='Draft an unreviewed brief from case overview.json')
    parser.add_argument('--output', type=Path, help='Exact output directory; defaults to brief parent or case-dir/diagrams')
    parser.add_argument('--formats', nargs='+', default=['auto'], choices=['auto', *FORMATS])
    parser.add_argument('--render', action='store_true', help='Render locally with the official Excalidraw CLI')
    parser.add_argument('--allow-npx', action='store_true', help='Allow npx package fetching if CLI is absent')
    args = parser.parse_args()
    if args.prepare:
        if not args.case_dir or args.brief or args.render or args.allow_npx:
            parser.error('--prepare requires --case-dir and cannot build or render')
        prepare(args.case_dir.resolve(), (args.output or args.case_dir/'diagrams').resolve())
        return 0
    if not args.brief or args.case_dir:
        parser.error('Building requires --brief; --case-dir is for --prepare')
    if args.allow_npx and not args.render:
        parser.error('--allow-npx requires --render')
    brief = read_json(args.brief)
    zone = validate(brief)
    if 'auto' in args.formats and args.formats != ['auto']:
        parser.error('Use auto by itself or select explicit formats')
    formats = list(dict.fromkeys(args.formats))
    if formats == ['auto']:
        formats = ['storyboard', 'technical'] if brief.get('events') else []
        formats += next(([f] for f in ('network', 'data-flow', 'identity') if usable_links(brief, f)), [])
    output = (args.output or args.brief.parent).resolve()
    reserved = [output/'manifest.json', output/'index.html'] + [output/f'{f}.excalidraw' for f in FORMATS]
    if args.brief.resolve() in reserved:
        raise ValueError('Input brief uses a generated output filename; select a different brief name or output directory')
    output.mkdir(parents=True, exist_ok=True)
    (output/'brief.snapshot.json').write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = dict(schema_version=1, title=brief['title'], brief='brief.snapshot.json',
                    timezone=zone.key, exports=[], skipped=[],
                    evidence={i['id']: i.get('evidence', []) for i in brief.get('events', [])+brief.get('relationships', [])})
    for entity in brief.get('entities', []):
        manifest['evidence'][entity['id']] = list(dict.fromkeys(ref for link in brief.get('relationships', [])
            if entity['id'] in (link['source'], link['target']) for ref in link['evidence']))
    failed = False
    for fmt in formats:
        print(f'Building {fmt}...', flush=True)
        if fmt in ('storyboard', 'timeline', 'technical'):
            if not brief.get('events'):
                manifest['skipped'].append(dict(format=fmt, reason='No reviewed events'))
                continue
            scene, omitted = events_view(brief, zone, fmt)
        else:
            links = usable_links(brief, fmt)
            if not links:
                manifest['skipped'].append(dict(format=fmt, reason='No qualifying reviewed relationships'))
                continue
            scene, omitted = graph_view(brief, zone, fmt, links), []
        path = output/f'{fmt}.excalidraw'
        if path.resolve() == args.brief.resolve():
            raise ValueError('Output scene would overwrite the input brief')
        scene.save(path)
        entry = dict(format=fmt, scene=path.name, visual_items=scene.mapping, omitted_events=omitted)
        if args.render:
            try:
                png = path.with_suffix('.png')
                render(path, png, args.allow_npx)
                entry['png'] = png.name
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                entry['error'] = str(exc)
                failed = True
        manifest['exports'].append(entry)
    if not manifest['exports']:
        failed = True
        manifest['skipped'].append(dict(format='build', reason='No supported diagrams to export'))
    (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    gallery(output, manifest)
    print(json.dumps(dict(output=str(output), exports=len(manifest['exports']), skipped=manifest['skipped'],
                          render_errors=[e['error'] for e in manifest['exports'] if 'error' in e]), indent=2))
    return 2 if failed else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)

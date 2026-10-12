"""Build a portable, offline incident dashboard from normalized case exports."""
import argparse
import json
from pathlib import Path


def build_dashboard(case_dir):
    case_dir = Path(case_dir)
    def lines(name):
        path = case_dir / name
        if not path.exists():
            raise ValueError(f'Missing case export: {path}')
        with path.open(encoding='utf-8-sig') as stream:
            return [json.loads(line) for line in stream if line.strip()]
    events = lines('timeline.jsonl') + lines('untimed.jsonl')
    leads = json.loads((case_dir / 'leads.json').read_text(encoding='utf-8-sig'))['leads']
    coverage = []
    for path in sorted(case_dir.glob('*/round-*/coverage.json')):
        coverage.append({'file': str(path.relative_to(case_dir)), 'details': json.loads(path.read_text(encoding='utf-8-sig'))})
    analysis = case_dir / 'analysis.md'
    payload = dict(case=case_dir.name, events=events, leads=leads, coverage=coverage,
                   analysis=analysis.read_text(encoding='utf-8-sig') if analysis.exists() else 'Analyst interpretation has not been added yet. Observations are not findings of compromise.')
    # Escape HTML delimiters even inside JSON: evidence must never close a script tag.
    encoded = json.dumps(payload, ensure_ascii=True).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    output = case_dir / 'dashboard.html'
    temporary = output.with_suffix('.html.tmp')
    temporary.write_text(TEMPLATE.replace('__CASE_DATA__', encoded), encoding='utf-8')
    temporary.replace(output)
    return output


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Incident explorer</title><style>
:root{color-scheme:dark;--bg:#0b1120;--panel:#121d30;--edge:#29364d;--muted:#a4b4ca;--accent:#67e8c3}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#edf3fc;font:15px/1.6 system-ui,sans-serif}header,main{max-width:1400px;margin:auto;padding:28px}header{border-bottom:1px solid var(--edge)}.eyebrow{color:var(--accent);font-size:12px;letter-spacing:3px;text-transform:uppercase}h1{font-size:34px;margin:8px 0}h2{margin-top:0}p{color:var(--muted)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}.stat,.panel{background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:20px}.stat strong{display:block;font-size:28px}.stat span,.meta{color:var(--muted);font-size:13px}nav,.filters,.pager{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:20px}button,input,select,a.download{font:inherit;border:1px solid var(--edge);border-radius:8px;padding:10px 14px;background:var(--panel);color:inherit}button,a{cursor:pointer}button[aria-selected=true]{background:var(--accent);color:#08251e}button:disabled{opacity:.4;cursor:default}input[type=search]{flex:1;min-width:240px}label{display:flex;gap:6px;align-items:center;color:var(--muted);font-size:13px}a{color:var(--accent)}.event{margin:0 0 16px 10px;padding:0 0 8px 24px;border-left:2px solid var(--edge);position:relative}.event:before{content:'';position:absolute;left:-6px;top:9px;width:10px;height:10px;background:var(--accent);border-radius:50%}.badge{font-size:12px;padding:3px 8px;border-radius:20px;background:#233b48;color:#a3f4de;margin-left:8px}.summary{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0}.meta{overflow-wrap:anywhere}details{background:var(--panel);border:1px solid var(--edge);padding:12px;border-radius:8px;margin:8px 0}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace;max-height:550px;overflow:auto}.analysis{white-space:pre-wrap;overflow-wrap:anywhere}#histogram{display:flex;align-items:flex-end;gap:4px;height:90px;margin:16px 0 24px;border-bottom:1px solid var(--edge)}#histogram button{flex:1;padding:0;min-width:4px;background:#358d83;border:0;border-radius:3px 3px 0 0}#histogram button:hover{background:var(--accent)}.histlabel{font-size:12px;color:var(--muted)}:focus-visible{outline:2px solid var(--accent);outline-offset:3px}[hidden]{display:none!important}@media(max-width:650px){header,main{padding:18px}.stats{grid-template-columns:repeat(2,1fr)}h1{font-size:26px}.filters{align-items:stretch;flex-direction:column}}@media print{nav,.filters,.pager,#histogram{display:none}body{background:white;color:black}.panel,.stat,details{background:white;color:black}pre{max-height:none}}
</style></head><body><header><div class="eyebrow">Local evidence workspace</div><h1 id="title"></h1><p>Browse observations, inspect original records, and review investigative leads. All timeline times are UTC. Separate time fields count as separate observations.</p><a class="download" href="timeline.csv" download>Download timeline CSV</a> <a class="download" href="timeline.jsonl" download>Event JSONL</a> <a class="download" href="untimed.jsonl" download>Untimed JSONL</a></header>
<main><div class="stats" id="stats"></div><nav aria-label="Dashboard sections"><button data-tab="timeline" aria-selected="true">Timeline</button><button data-tab="analysis" aria-selected="false">Analyst findings</button><button data-tab="leads" aria-selected="false">Leads</button><button data-tab="coverage" aria-selected="false">Coverage</button></nav>
<section id="timeline"><div class="filters"><input id="search" type="search" aria-label="Search all evidence fields" placeholder="Search paths, users, domains, records…"><select id="source" aria-label="Source"><option value="">All sources</option></select><select id="family" aria-label="Artifact family"><option value="">All artifact families</option></select><select id="timing" aria-label="Timestamp status"><option value="all">All observations</option><option value="timed">Timed only</option><option value="untimed">Untimed only</option></select><label>From UTC <input id="start" type="date"></label><label>Through UTC <input id="end" type="date"></label><button id="reset">Reset</button></div><div class="histlabel">Activity by UTC day · select a bar to inspect that day</div><div id="histogram" aria-label="Daily activity"></div><p id="count" role="status"></p><div id="events"></div><div class="pager"><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></div></section>
<section id="analysis" class="panel" hidden><h2>Analyst findings</h2><div id="narrative" class="analysis"></div></section>
<section id="leads" hidden><h2>Investigative leads</h2><p>Candidate leads await relevance review; matching a value does not establish maliciousness.</p><input id="leadsearch" type="search" aria-label="Search leads" placeholder="Search leads and provenance"><div id="leadrows"></div></section>
<section id="coverage" hidden><h2>Scope and coverage</h2><p>Review source errors, malformed records, exclusions, and timestamp gaps before interpreting zero matches.</p><div id="coveragerows"></div></section></main>
<script id="case-data" type="application/json">__CASE_DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('case-data').textContent), $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e};
const detail=(title,value)=>{const d=node('details');d.append(node('summary',title),node('pre',JSON.stringify(value,null,2)));return d};
$('title').textContent=data.case+' / Incident explorer';$('narrative').textContent=data.analysis;
const timed=data.events.filter(e=>e.timestamp_utc).length;
for(const [value,label] of [[data.events.length,'Observations'],[timed,'Timed observations'],[data.events.length-timed,'Unverified or missing times'],[data.leads.length,'Investigative leads']]){const s=node('div',undefined,'stat');s.append(node('strong',value.toLocaleString()),node('span',label));$('stats').append(s)}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(t=>{const selected=t===b;t.setAttribute('aria-selected',selected);$(t.dataset.tab).hidden=!selected})});
for(const [id,key] of [['source','orchestrator'],['family','family']])for(const v of [...new Set(data.events.map(e=>e[key]).filter(Boolean))].sort()){const o=node('option',v);o.value=v;$(id).append(o)}
// Precompute search strings once; DOM rendering stays bounded to one page.
const indexed=data.events.map(e=>({e,text:JSON.stringify(e).toLowerCase()})).sort((a,b)=>(a.e.timestamp_utc||'~').localeCompare(b.e.timestamp_utc||'~'));
let page=0,filtered=[],size=50;
function filter(){const q=$('search').value.toLowerCase(),start=$('start').value,end=$('end').value;
filtered=indexed.filter(({e,text})=>{const day=(e.timestamp_utc||'').slice(0,10);return text.includes(q)&&(!$('source').value||e.orchestrator===$('source').value)&&(!$('family').value||e.family===$('family').value)&&($('timing').value==='all'||Boolean(day)===($('timing').value==='timed'))&&(!day||((!start||day>=start)&&(!end||day<=end)))});page=0;histogram();render()}
function histogram(){const days=new Map();for(const {e} of filtered)if(e.timestamp_utc){const day=e.timestamp_utc.slice(0,10);days.set(day,(days.get(day)||0)+1)}$('histogram').replaceChildren();const entries=[...days],max=Math.max(1,...days.values());if(entries.length>120){$('histogram').append(node('span','Narrow the date range to display daily activity (120 days maximum).','meta'));return}for(const [day,n] of entries){const b=node('button');b.style.height=Math.max(5,n/max*85)+'px';b.title=day+' · '+n+' observations';b.setAttribute('aria-label',b.title);b.onclick=()=>{$('start').value=day;$('end').value=day;filter()};$('histogram').append(b)}}
function render(){const pages=Math.max(1,Math.ceil(filtered.length/size));$('count').textContent=filtered.length.toLocaleString()+' of '+data.events.length.toLocaleString()+' observations · Date filters retain untimed evidence.';$('events').replaceChildren();if(!filtered.length)$('events').append(node('p','No observations match these filters.'));
for(const {e} of filtered.slice(page*size,(page+1)*size)){const card=node('article',undefined,'event'),head=node('div');head.append(node('strong',e.timestamp_utc||'Untimed / timezone unverified'),node('span',e.family||e.orchestrator,'badge'));card.append(head,node('div',(e.orchestrator||'')+' · '+e.source+' / record '+e.record,'meta'),node('div',[e.time_field,e.timezone_basis,e.host&&'Host: '+e.host,e.user&&'User: '+e.user,e.profile&&'Profile: '+e.profile].filter(Boolean).join(' · '),'meta'),node('div',(e.observation||'').slice(0,500)+((e.observation||'').length>500?'…':''),'summary'),detail('Inspect complete record, confidence and lead citations',e));$('events').append(card)}$('page').textContent='Page '+(page+1)+' of '+pages;$('prev').disabled=page===0;$('next').disabled=page+1>=pages}
let debounce;for(const id of ['search','source','family','timing','start','end'])$(id).addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(filter,120)});
$('prev').onclick=()=>{page--;render()};$('next').onclick=()=>{page++;render()};$('reset').onclick=()=>{for(const id of ['search','source','family','start','end'])$(id).value='';$('timing').value='all';filter()};
let leadpage=0;function leads(){const matches=data.leads.filter(l=>JSON.stringify(l).toLowerCase().includes($('leadsearch').value.toLowerCase()));$('leadrows').replaceChildren(node('p',matches.length+' leads'));for(const l of matches.slice(0,(leadpage+1)*100))$('leadrows').append(detail(l.status+' · '+l.kind+' · '+l.value,l));if(matches.length>(leadpage+1)*100){const b=node('button','Show more leads');b.onclick=()=>{leadpage++;leads()};$('leadrows').append(b)}}$('leadsearch').oninput=()=>{leadpage=0;leads()};
for(const c of data.coverage)$('coveragerows').append(detail(c.file,c.details));if(!data.coverage.length)$('coveragerows').append(node('p','No per-source coverage reports are available.'));
filter();leads();
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_directory', type=Path)
    args = parser.parse_args()
    try:
        print(build_dashboard(args.case_directory).resolve())
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())

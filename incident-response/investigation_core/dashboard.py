"""Build a portable, offline incident dashboard from normalized case exports."""
import argparse
import json
from pathlib import Path
if __package__:
    from .markdown_view import render as render_markdown
else:
    from markdown_view import render as render_markdown


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
    triage = case_dir / 'triage.md'
    payload = dict(case=case_dir.name, events=events, leads=leads, coverage=coverage,
                   triage=triage.read_text(encoding='utf-8') if triage.exists() else 'Automatic triage has not been run for this case.',
                   analysis=analysis.read_text(encoding='utf-8-sig') if analysis.exists() else 'Analyst interpretation has not been added yet. Observations are not findings of compromise.')
    settings = case_dir / 'case-settings.json'
    payload['settings'] = json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
    payload['analysis_html'], payload['outline'] = render_markdown(payload['analysis'])
    payload['triage_html'], _ = render_markdown(payload['triage'])
    overview = case_dir / 'overview.json'
    payload['overview'] = json.loads(overview.read_text(encoding='utf-8-sig')) if overview.exists() else {}
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
body{background:radial-gradient(ellipse at top left,#172b3a 0,transparent 50%),var(--bg)}header,main{max-width:1280px}header{padding-bottom:20px}.stats{gap:12px;margin-bottom:24px}.stat{padding:14px 20px}.stat strong{font-size:24px}nav{position:sticky;top:0;z-index:2;background:#0b1120ed;padding:12px 0;backdrop-filter:blur(12px)}nav button{border-radius:24px;padding:9px 18px}.hero{padding:30px;border-left:4px solid var(--accent);background:linear-gradient(120deg,#163b3b,#121d30);border-radius:12px;margin-bottom:22px}.hero h2{font-size:30px;margin:8px 0}.hero p{font-size:17px;max-width:900px}.two-column{display:grid;grid-template-columns:1.3fr 1fr;gap:20px;margin-bottom:20px}.panel h2{font-size:21px}.panel li{margin:10px 0}.milestone{padding:16px 0;border-bottom:1px solid var(--edge)}.milestone strong{display:block}.milestone p{margin:5px 0}.reading-layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:24px}.outline{align-self:start;position:sticky;top:80px;max-height:75vh;overflow:auto}.outline a{display:block;font-size:13px;padding:7px 10px;text-decoration:none;border-left:2px solid var(--edge)}.outline a:hover{background:#20334a}.analysis{white-space:normal;overflow-wrap:anywhere;max-width:900px;line-height:1.85}.analysis h1{font-size:29px}.analysis h2{margin-top:32px;padding-top:16px;border-top:1px solid var(--edge)}.analysis h3{margin-top:24px}.analysis p,.analysis li{color:#cad5e5}.analysis code{background:#243247;border-radius:4px;padding:2px 5px;font-size:.9em}.analysis pre{background:#091222;padding:18px;line-height:1.6}.analysis pre code{background:none;padding:0}.analysis blockquote{border-left:3px solid var(--accent);padding:8px 18px;margin-left:0;color:var(--muted)}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}th,td{text-align:left;border:1px solid var(--edge);padding:10px 12px;vertical-align:top}th{background:#1b3044}tr:nth-child(even){background:#122237}.event{padding:16px 18px;margin:0 0 14px;background:#111f32;border:1px solid var(--edge);border-radius:10px}.event:before{display:none}.event h3{font-size:18px;margin:8px 0}.summary{color:#c5d2e4}.downloads{margin-top:18px}details pre{font-size:12px}.status{font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--accent)}@media(max-width:800px){.two-column,.reading-layout{grid-template-columns:1fr}.outline{position:static;max-height:180px}.hero{padding:20px}.hero h2{font-size:25px}nav{position:static}}@media print{.outline{display:none}.reading-layout{display:block}.hero{background:white;color:black}section[hidden]{display:none!important}}
</style></head><body><header><div class="eyebrow">Incident review</div><h1 id="title"></h1><p>Read the assessment, follow the sequence of events, and open supporting evidence when needed.</p></header>
<main><nav aria-label="Dashboard sections"><button data-tab="overview" aria-selected="true">Overview</button><button data-tab="analysis" aria-selected="false">Full report</button><button data-tab="timeline" aria-selected="false">Evidence timeline</button><button data-tab="triage" aria-selected="false">Investigation leads</button><button data-tab="leads" aria-selected="false">IOC pivots</button><button data-tab="coverage" aria-selected="false">Source coverage</button></nav><div class="stats" id="stats"></div>
<section id="overview"><div class="hero"><div class="status" id="verdictconfidence"></div><h2 id="verdict"></h2><p id="overviewsummary"></p></div><div class="two-column"><div class="panel"><h2>What the evidence supports</h2><ul id="keyfindings"></ul></div><div class="panel"><h2>What remains uncertain</h2><ul id="unknowns"></ul></div></div><div class="panel"><h2>Incident at a glance</h2><p>Analyst-selected milestones. Each entry retains its evidence reference and time basis.</p><div id="milestones"></div></div><div class="downloads"><details><summary>Download reports and evidence exports</summary><p><a href="analysis.md" download>Analyst report (Markdown)</a> · <a href="timeline.csv" download>Timeline CSV</a> · <a href="timeline.jsonl" download>Event JSONL</a> · <a href="untimed.jsonl" download>Untimed observations</a></p></details></div></section>
<section id="timeline" hidden><p>Search supporting observations. Choose a display timezone; open a record for its original fields and source citation.</p><label>Display timezone <input id="timezone" value="UTC" placeholder="America/Los_Angeles or +05:30"></label><span id="timezone-status" role="status"></span><div class="filters"><input id="search" type="search" aria-label="Search all evidence fields" placeholder="Find a program, user, domain or file…"><select id="source" aria-label="Source"><option value="">All sources</option></select><select id="family" aria-label="Artifact family"><option value="">All artifact families</option></select><select id="timing" aria-label="Timestamp status"><option value="all">All observations</option><option value="timed">Timed only</option><option value="untimed">Untimed only</option></select><label>From date <input id="start" type="date"></label><label>Through date <input id="end" type="date"></label><button id="reset">Reset</button></div><div class="histlabel">Activity by selected timezone day · select a bar to inspect that day</div><div id="histogram" aria-label="Daily activity"></div><p id="count" role="status"></p><div id="events"></div><div class="pager"><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></div></section>
<section id="triage" class="panel" hidden><h2>Incident triage</h2><a href="case-brief.json" download>Compact evidence index</a> <a href="triage.md" download>Triage summary</a><div id="triagenarrative" class="analysis"></div></section>
<section id="analysis" hidden><div class="reading-layout"><aside id="outline" class="outline" aria-label="Report contents"></aside><article id="narrative" class="analysis panel"></article></div></section>
<section id="leads" hidden><h2>Investigative leads</h2><p>Candidate leads await relevance review; matching a value does not establish maliciousness.</p><input id="leadsearch" type="search" aria-label="Search leads" placeholder="Search leads and provenance"><div id="leadrows"></div></section>
<section id="coverage" hidden><h2>Scope and coverage</h2><p>Review source errors, malformed records, exclusions, and timestamp gaps before interpreting zero matches.</p><div id="coveragerows"></div></section></main>
<script id="case-data" type="application/json">__CASE_DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('case-data').textContent), $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e};
const detail=(title,value)=>{const d=node('details');d.append(node('summary',title),node('pre',JSON.stringify(value,null,2)));return d};
$('title').textContent=data.case;
// Only the builder's escaped Markdown renderer supplies HTML. Raw evidence uses textContent.
$('narrative').innerHTML=data.analysis_html;$('triagenarrative').innerHTML=data.triage_html;
for(const item of data.outline||[]){if(item.level>3)continue;const a=node('a',item.title);a.href='#'+item.id;$('outline').append(a)}
const overview=data.overview||{};$('verdict').textContent=overview.verdict||'Assessment pending';$('verdictconfidence').textContent=overview.confidence||'Analyst review';$('overviewsummary').textContent=overview.summary||'Open the full report for the current analyst account. Evidence observations and automated leads are available in the other views.';
for(const [id,items,fallback] of [['keyfindings',overview.findings,'See the full report for evidence-backed findings.'],['unknowns',overview.unknowns,'The analyst has not published a concise uncertainty summary.']]){for(const item of items?.length?items:[fallback])$(id).append(node('li',item))}
for(const item of overview.milestones||[]){const card=node('div',undefined,'milestone');card.append(node('div',item.time||'Time unverified','meta'),node('strong',item.title),node('p',item.description),node('div',item.evidence||'','meta'));if(item.search){const b=node('button','View supporting evidence');b.onclick=()=>{$('reset').onclick();$('search').value=item.search;filter();selectTab('timeline')};card.append(b)}$('milestones').append(card)}
if(!overview.milestones?.length)$('milestones').append(node('p','No analyst-selected milestones yet. Browse the evidence timeline to inspect observations.'));
const timed=data.events.filter(e=>e.timestamp_utc).length;
for(const [value,label] of [[new Set(data.events.map(e=>e.host).filter(Boolean)).size,'Hosts referenced'],[new Set(data.events.map(e=>e.source)).size,'Evidence exports'],[data.events.length,'Supporting observations'],[data.events.length-timed,'Times needing review']]){const s=node('div',undefined,'stat');s.append(node('strong',value.toLocaleString()),node('span',label));$('stats').append(s)}
function selectTab(name){document.querySelectorAll('[data-tab]').forEach(t=>{const selected=t.dataset.tab===name;t.setAttribute('aria-selected',selected);$(t.dataset.tab).hidden=!selected});if(typeof window!=='undefined')window.scrollTo(0,0)}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>selectTab(b.dataset.tab));
if(typeof location!=='undefined'&&['overview','analysis','timeline','triage','leads','coverage'].includes(location.hash.slice(1)))selectTab(location.hash.slice(1));
for(const [id,key] of [['source','orchestrator'],['family','family']])for(const v of [...new Set(data.events.map(e=>e[key]).filter(Boolean))].sort()){const o=node('option',v);o.value=v;$(id).append(o)}
// Precompute search strings once; DOM rendering stays bounded to one page.
const timeFormatters=new Map();
let displayZone=data.settings?.display_timezone||'UTC';
$('timezone').value=displayZone;
function zoned(utc,dayOnly=false){if(!utc)return '';let date=new Date(utc),tz=displayZone;const m=/^(?:UTC|GMT)?([+-])(\d{2}):(\d{2})$/i.exec(tz);if(m){date=new Date(date.getTime()+(m[1]==='+'?1:-1)*(Number(m[2])*60+Number(m[3]))*60000);tz='UTC'}const key=tz+'|'+dayOnly;if(!timeFormatters.has(key))timeFormatters.set(key,new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit',...(dayOnly?{}:{hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'})}));const parts=timeFormatters.get(key).formatToParts(date);const v=Object.fromEntries(parts.map(p=>[p.type,p.value]));return v.year+'-'+v.month+'-'+v.day+(dayOnly?'':' '+v.hour+':'+v.minute+':'+v.second+' '+displayZone)}
$('timezone').addEventListener('change',()=>{const before=displayZone;try{displayZone=$('timezone').value.trim();const m=/^(?:UTC|GMT)?([+-])(\d{2}):(\d{2})$/i.exec(displayZone);if(m&&(Number(m[2])>23||Number(m[3])>59))throw Error('Invalid offset');zoned('2026-01-01T00:00:00Z');$('timezone-status').textContent='';filter()}catch(error){displayZone=before;$('timezone-status').textContent='Unknown timezone. Use an IANA name or +05:30.'}});
const indexed=data.events.map(e=>({e,text:JSON.stringify(e).toLowerCase()})).sort((a,b)=>(a.e.timestamp_utc||'~').localeCompare(b.e.timestamp_utc||'~'));
let page=0,filtered=[],size=50;
function filter(){const q=$('search').value.toLowerCase(),start=$('start').value,end=$('end').value;
filtered=indexed.filter(({e,text})=>{const day=zoned(e.timestamp_utc,true);return text.includes(q)&&(!$('source').value||e.orchestrator===$('source').value)&&(!$('family').value||e.family===$('family').value)&&($('timing').value==='all'||Boolean(day)===($('timing').value==='timed'))&&(!day||((!start||day>=start)&&(!end||day<=end)))});page=0;histogram();render()}
function histogram(){const days=new Map();for(const {e} of filtered)if(e.timestamp_utc){const day=zoned(e.timestamp_utc,true);days.set(day,(days.get(day)||0)+1)}$('histogram').replaceChildren();const entries=[...days],max=Math.max(1,...days.values());if(entries.length>120){$('histogram').append(node('span','Narrow the date range to display daily activity (120 days maximum).','meta'));return}for(const [day,n] of entries){const b=node('button');b.style.height=Math.max(5,n/max*85)+'px';b.title=day+' · '+n+' observations';b.setAttribute('aria-label',b.title);b.onclick=()=>{$('start').value=day;$('end').value=day;filter()};$('histogram').append(b)}}
function render(){const pages=Math.max(1,Math.ceil(filtered.length/size));$('count').textContent=filtered.length.toLocaleString()+' of '+data.events.length.toLocaleString()+' observations · Date filters retain untimed evidence.';$('events').replaceChildren();if(!filtered.length)$('events').append(node('p','No observations match these filters.'));
for(const {e} of filtered.slice(page*size,(page+1)*size)){const card=node('article',undefined,'event'),head=node('div'),d=e.data||{};const title=(e.triage_categories?.[0]||d.MapDescription||d.data_type||e.family||'Evidence observation').replace(/[-_:]/g,' ');const description=[d.ExecutableInfo,d.PayloadData1,d.PayloadData2,d.url,d.target_path,d.FullPath,d.Path,d.FileName].filter(Boolean).join(' · ')||e.observation||'';head.append(node('strong',e.timestamp_utc?zoned(e.timestamp_utc):'Time unverified'),node('span',e.orchestrator,'badge'));card.append(head,node('h3',title),node('div',[e.host,e.user,e.profile].filter(Boolean).join(' · '),'meta'),node('div',description.slice(0,240)+(description.length>240?'…':''),'summary'),node('div',(e.source||'').split(/[\\/]/).pop()+' · record '+e.record+' · '+e.time_field,'meta'),detail('View supporting record and full source citation',e));$('events').append(card)}$('page').textContent='Page '+(page+1)+' of '+pages;$('prev').disabled=page===0;$('next').disabled=page+1>=pages}
let debounce;for(const id of ['search','source','family','timing','start','end'])$(id).addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(filter,120)});
$('prev').onclick=()=>{page--;render()};$('next').onclick=()=>{page++;render()};$('reset').onclick=()=>{for(const id of ['search','source','family','start','end'])$(id).value='';$('timing').value='all';filter()};
let leadpage=0;function leads(){const matches=data.leads.filter(l=>JSON.stringify(l).toLowerCase().includes($('leadsearch').value.toLowerCase()));$('leadrows').replaceChildren(node('p',matches.length+' leads'));for(const l of matches.slice(0,(leadpage+1)*100))$('leadrows').append(detail(l.status+' · '+l.kind+' · '+l.value,l));if(matches.length>(leadpage+1)*100){const b=node('button','Show more leads');b.onclick=()=>{leadpage++;leads()};$('leadrows').append(b)}}$('leadsearch').oninput=()=>{leadpage=0;leads()};
for(const c of data.coverage){const files=c.details.coverage||[],errors=files.filter(f=>f.error||f.malformed),excluded=files.filter(f=>f.excluded),count=files.reduce((sum,f)=>sum+(f.scanned||0),0);const card=node('div',undefined,'panel');card.append(node('h3',c.details.orchestrator||c.file),node('p',count.toLocaleString()+' records scanned · '+files.length+' exports · '+errors.length+' files with issues · '+excluded.length+' excluded companions'),detail('Review file coverage and collection gaps',c.details));$('coveragerows').append(card)}if(!data.coverage.length)$('coveragerows').append(node('p','No per-source coverage reports are available.'));
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

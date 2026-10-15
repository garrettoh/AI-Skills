"""Stream CSV hunts and use temporary SQLite storage for timeline sorting."""
import argparse,csv,json,sqlite3,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
from .schemas import classify, verified_utc
csv.field_size_limit(16*1024*1024)
def files(path):
 p=Path(path)
 if not p.exists(): raise ValueError("Input does not exist")
 if p.is_file():
  if p.suffix.lower()!=".csv": raise ValueError("Input must be CSV")
  yield p
 else:
  yield from sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower()==".csv")
def reader(path,encoding):
 f=path.open(encoding=encoding,newline="")
 try:
  sample=f.read(8192);f.seek(0)
  try: dialect=csv.Sniffer().sniff(sample,delimiters=",;\t")
  except csv.Error: dialect=csv.excel
  r=csv.DictReader(f,dialect=dialect,strict=True);h=r.fieldnames or []
  if not h or len(h)!=len(set(h)): raise ValueError("Empty or duplicate headers")
  return f,r,h
 except Exception:
  f.close();raise
def stamp(v,assume):
 try:
  d=datetime.fromisoformat(v.strip().replace("Z","+00:00"))
  if d.tzinfo is None:
   if not assume:return None
   d=d.replace(tzinfo=timezone.utc)
  return d.astimezone(timezone.utc).isoformat(timespec="microseconds")
 except (ValueError,OverflowError):return None
def cell(v,cap=240):
 v=str(v).replace("|","\\|").replace("\r"," ").replace("\n"," ")
 return v if len(v)<=cap else v[:cap]+"… [truncated]"
def main(mode="hunt",skill=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("input");p.add_argument("--output",required=True);p.add_argument("--encoding",default="utf-8-sig")
 if mode!="inventory":
  p.add_argument("--keyword",action="append",default=[]);p.add_argument("--ioc",action="append",default=[])
  p.add_argument("--where",action="append",default=[]);p.add_argument("--search-columns");p.add_argument("--columns")
  p.add_argument("--limit",type=int,default=100);p.add_argument("--max-cell",type=int,default=240)
 if mode=="timeline":
  p.add_argument("--assume-utc",action="store_true");p.add_argument("--start");p.add_argument("--end")
 a=p.parse_args();predicates=[];start=end=None
 if mode!="inventory":
  if a.limit<1 or a.max_cell<1:p.error("Limits must be positive")
  for w in a.where:
   if "=" not in w:p.error("--where requires COLUMN=VALUE")
   predicates.append(w.split("=",1))
 if mode=="timeline":
  start=stamp(a.start,False) if a.start else None;end=stamp(a.end,False) if a.end else None
  if (a.start and not start) or (a.end and not end):p.error("Bounds need ISO timestamps with timezone")
  if start and end and start>end:p.error("Start must precede end")
 evidence=Path(a.input).resolve();out=Path(a.output).resolve()
 if out==evidence or (evidence.is_dir() and out.is_relative_to(evidence)):p.error("Report must be outside evidence")
 paths=files(a.input)
 scanned=matched=shown=malformed=skipped=eligible=events=auto_utc=0;errors=[];inventory=[];bad_rows=[]
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix="kape-") as td,out.open("w",encoding="utf-8") as report:
  db=sqlite3.connect(str(Path(td)/"timeline.db"))
  if mode=="timeline":db.execute("create table events(utc text,source text,rownum integer,field text,raw text,family text,data text)")
  if mode!="inventory":
   report.write("# KAPE hunt report\n\n## Scope\n\nInput: "+cell(evidence,1000)+"\n\nFilters: "+cell(json.dumps(dict(keyword=a.keyword,ioc=a.ioc,where=a.where,search_columns=a.search_columns)),2000)+"\n\nLogical CSV record numbers include the header as row 1. Matches require analyst interpretation.\n\n## Evidence\n\n")
   report.write("| Source CSV | Row | Family | Evidence |\n|---|---:|---|---|\n" if mode=="hunt" else "| UTC | Raw time | Time field | Source CSV | Row | Family | Evidence |\n|---|---|---|---|---:|---|---|\n")
  for path in paths:
   f=None
   try:
    f,r,h=reader(path,a.encoding);profile=classify(h,path.name)
    if mode=="inventory":
     inventory.append(dict(path=str(path.resolve()),bytes=path.stat().st_size,headers=h,**profile));continue
    if skill and profile["skill"]!=skill:continue
    eligible+=1
    search=a.search_columns.split(",") if a.search_columns else h
    columns=a.columns.split(",") if a.columns else h[:12]
    missing=set(search+columns+[k for k,v in predicates])-set(h)
    if missing:
     errors.append(dict(path=str(path),error="Missing columns: "+", ".join(sorted(missing))));continue
    for n,row in enumerate(r,2):
     scanned+=1
     if None in row or any(v is None for v in row.values()):
      malformed+=1
      if len(bad_rows)<100:bad_rows.append(dict(path=str(path),row=n))
      continue
     if any(row[k].casefold()!=v.casefold() for k,v in predicates):continue
     values=[row[k].casefold() for k in search]
     if a.keyword or a.ioc:
      if not (any(k.casefold() in v for k in a.keyword for v in values) or any(i.casefold()==v for i in a.ioc for v in values)):continue
     matched+=1
     render_columns=list(columns)
     if not a.columns and (a.keyword or a.ioc):
      hit_columns=[k for k in search if any(t.casefold() in row[k].casefold() for t in a.keyword) or any(t.casefold()==row[k].casefold() for t in a.ioc)]
      render_columns=list(dict.fromkeys(hit_columns+columns))[:12]
     data="; ".join(k+"="+cell(row[k],a.max_cell) for k in render_columns)
     if mode=="hunt":
      if shown<a.limit:
       report.write("| "+cell(path,1000)+" | "+str(n)+" | "+profile["family"]+" | "+data+" |\n");shown+=1
     else:
      for field in profile["time_fields"]:
       raw=row[field]
       if not raw:continue
       source_utc=verified_utc(profile,field)
       utc=stamp(raw,a.assume_utc or source_utc)
       if not utc:skipped+=1;continue
       if (start and utc<start) or (end and utc>end):continue
       if source_utc:auto_utc+=1
       db.execute("insert into events values(?,?,?,?,?,?,?)",(utc,str(path),n,field,raw,profile["family"],data))
    if mode=="timeline":db.commit()
   except (OSError,UnicodeError,csv.Error,ValueError) as exc:errors.append(dict(path=str(path),error=str(exc)))
   finally:
    if f:f.close()
  if mode=="inventory":
   json.dump(dict(files=inventory,errors=errors,schema_only=True,non_csv_policy="Excluded; archives are not extracted"),report,indent=2)
  else:
   if mode=="timeline":
    events=db.execute("select count(*) from events").fetchone()[0]
    for utc,source,n,field,raw,family,data in db.execute("select * from events order by utc,source,rownum,field limit ?",(a.limit,)):
     report.write("| "+" | ".join([utc,cell(raw,a.max_cell),field,cell(source,1000),str(n),family,data])+" |\n");shown+=1
   report.write(f"\n## Coverage and limitations\n\nEligible files: {eligible}; scanned rows: {scanned}; matching rows: {matched}; displayed records: {shown}; malformed rows: {malformed}.\n\n")
   if mode=="timeline":report.write(f"Events in time bounds: {events}; verified EVTX TimeCreated UTC values normalized: {auto_utc}; skipped nonempty unparseable or timezone-unknown times: {skipped}; assume other naive UTC: {a.assume_utc}; bounds: {start} to {end}. Separate fields are separate events. Proximity does not prove causation.\n\n")
   report.write("Display caps do not stop scanning. Cells can be truncated. Exact IOCs match whole fields; use keywords for embedded values. Unknown schemas are searchable but have no timeline fields. Zero matches do not prove absence.\n\n## Errors\n\n")
   if bad_rows:
    report.write("Malformed records (first 100): "+cell(json.dumps(bad_rows),20000)+"\n\n")
   report.write("".join("- "+cell(e["path"],1000)+": "+cell(e["error"],1000)+"\n" for e in errors) or "None.\n")
  db.close()
 print(json.dumps(dict(output=str(out),files=len(inventory) if mode=="inventory" else eligible,scanned=scanned,matched=matched,displayed=shown,errors=len(errors))))
 return 2 if errors or malformed else 0
def run(mode="hunt",skill=None):
 try:return main(mode,skill)
 except (OSError,ValueError,sqlite3.Error) as e:
  print(str(e),file=sys.stderr);return 2

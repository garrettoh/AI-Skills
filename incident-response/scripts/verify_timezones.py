"""Check verified UTC fields, local overrides, DST boundaries and display offsets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'kape_analysis'))
from kape_core.timezones import TimestampPolicy,display_timestamp,source_rules,zone
from kape_core.schemas import UTC_FIELDS,utc_basis
p=TimestampPolicy()
for family,fields in UTC_FIELDS.items():
 for field in fields:
  assert p.resolve('2026-10-14 23:38:10',family,field,True,utc_basis({'family':family},field))[0]=='2026-10-14T23:38:10.000000+00:00'
assert p.resolve('2026-10-14 23:38:10','shellbags','CreatedOn')[0] is None
assert p.resolve('2026-10-14 23:38:10','registry-detail','FirstConnectLOCAL')[0] is None
assert display_timestamp('2026-10-14T23:38:10Z','America/Los_Angeles')=='2026-10-14T16:38:10.000000-07:00'
assert display_timestamp('2026-01-14T23:38:10Z','America/Los_Angeles')=='2026-01-14T15:38:10.000000-08:00'
assert display_timestamp('2026-10-14T23:38:10Z','Asia/Kolkata')=='2026-10-15T05:08:10.000000+05:30'
assert display_timestamp('2026-10-14T23:38:10Z','+05:45')=='2026-10-15T05:23:10.000000+05:45'
p=TimestampPolicy(source_rules(['shellbags.*=America/Los_Angeles']))
assert p.resolve('2026-10-14 16:38:10','shellbags','CreatedOn')[0]=='2026-10-14T23:38:10.000000+00:00'
assert 'ambiguous' in p.resolve('2026-11-01 01:30:00','shellbags','CreatedOn')[1]
assert 'nonexistent' in p.resolve('2026-03-08 02:30:00','shellbags','CreatedOn')[1]
assert p.resolve('2026-11-01T01:30:00-07:00','shellbags','CreatedOn')[0]=='2026-11-01T08:30:00.000000+00:00'
try:zone('made/up')
except ValueError:pass
else:raise AssertionError('Invalid zone accepted')
print('PASS: all UTC allowlisted fields, unknown local fields, DST, midnight rollover, fractional offsets, source rules and explicit-offset precedence')

# Exercise persisted settings and cache behavior through the public orchestrator CLI.
import csv,json,subprocess,tempfile
script=Path(__file__).resolve().parents[1]/'investigation-orchestrator/scripts/investigate.py'
with tempfile.TemporaryDirectory(prefix='timezone-case-') as temporary:
 work=Path(temporary);evidence=work/'evidence';evidence.mkdir()
 with (evidence/'registry.csv').open('w',newline='') as output:
  writer=csv.writer(output);writer.writerow(['BatchKeyPath','BatchValueName','Timestamp','Payload'])
  writer.writerow(['Test','Value','2026-10-14 16:38:10','timezone-test'])
 command=[sys.executable,str(script),'--source','kape='+str(evidence),'--case','test','--output-root',str(work/'output'),'--lead','timezone-test']
 def run(extra):
  result=subprocess.run(command+extra,capture_output=True,text=True,timeout=60)
  assert result.returncode==0,result.stderr
  return json.loads(result.stdout)
 case=work/'output/test'
 run(['--timezone','Asia/Kolkata'])
 assert json.loads((case/'case-settings.json').read_text())['display_timezone']=='Asia/Kolkata'
 assert len((case/'untimed.jsonl').read_text().splitlines())==1
 result=run(['--timezone','America/Los_Angeles'])
 assert result['sources'][0]['records_scanned']==0
 result=run(['--source-timezone','registry-detail.Timestamp=America/Los_Angeles'])
 assert result['sources'][0]['records_scanned']==1
 event=json.loads((case/'timeline.jsonl').read_text().strip())
 assert event['timestamp_utc']=='2026-10-14T23:38:10.000000+00:00'
 assert event['timestamp_display']=='2026-10-14T16:38:10.000000-07:00'
 assert event['timestamp_raw']=='2026-10-14 16:38:10'
 assert not (case/'untimed.jsonl').read_text().strip()
 run([])
 assert json.loads((case/'case-settings.json').read_text())['display_timezone']=='America/Los_Angeles'
print('PASS: selected zone persistence, display-only cache reuse, source-rule rescan, raw retention and untimed-to-timed replacement')

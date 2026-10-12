# Hindsight exports

The supplied sample layout contains admin1_Edge.jsonl.jsonl, workstation_Chrome.jsonl.jsonl and workstation_Edge.jsonl.jsonl, plus corresponding .xlsx.xlsx workbooks. Discovery is recursive and suffix based, so repeated suffixes work. No sample evidence is committed to Git.

JSONL is preferred: UTF-8/BOM aware, one JSON object per physical line, constant memory per record. Directory discovery excludes an XLSX with the same repeated-suffix-stripped basename and directory when JSONL is present. Exclusions are recorded; workbook Storage/Extension/Sync/Preferences sheets can contain additional data. Search a workbook explicitly when that coverage is needed, and document overlapping timeline records. Files with distinct names are treated as distinct acquisitions, with no identity assumption.

Observed JSONL fields include source_short, source_long, parser, profile, url, value, key, datetime, timestamp_desc, data_type, message and interpretation. Fields vary by artifact. Filters search all values, including nested values rendered as text. Keep full original data in normalized output. `datetime` supplies event time and `timestamp_desc` its semantics. The supplied samples use offset-bearing ISO datetimes; other exports must be inspected rather than assumed UTC.

The XLSX fallback uses Python's ZIP/XML libraries and disk-backed shared strings, then streams worksheets. It never evaluates formulas, macros or links. Timeline headers include Type, Timestamp (UTC), URL, Title / Name / Status, Data / Value / Path, Interpretation, Profile and source-specific fields. The title row is skipped and the header row detected. Unknown sheets are disclosed. Text timestamp values are supported; numeric Excel serial dates or unfamiliar schemas remain unparseable/untimed until a verified adapter is added. Only explicit UTC field labels establish UTC for naive values. Preserve XLSX sheet and row citations.

Interpretation pivots:

| Browser evidence | Corroboration |
|---|---|
| URL visit or cached response | Navigation context, redirects and related URLs; endpoint network evidence |
| Download URL and destination | KAPE MFT/USN, file hashes, Prefetch/Amcache and event logs |
| Search text or typed URL | Visit semantics and profile attribution; do not infer intent from presence alone |
| Preference, extension or session changes | Browser session context, installation artifacts and endpoint persistence evidence |
| Storage/sync records | Domain/profile context and timestamp meaning; records may lack usable event time |

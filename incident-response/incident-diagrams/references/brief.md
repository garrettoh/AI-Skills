# Reviewed visual brief

The helper accepts a JSON object with `schema_version: 1` and `reviewed: true`. IDs must be unique across events, entities and relationships. It does not infer incidents from raw records. The writer is responsible for checking the assessment and citations before marking a brief reviewed.

```json
{
  "schema_version": 1,
  "reviewed": true,
  "title": "Incident overview",
  "subtitle": "Selected activity on two systems",
  "timezone": "UTC",
  "events": [
    {
      "id": "e1",
      "time": "2026-01-02T03:04:05Z",
      "title": "Remote authentication observed",
      "summary": "An account authenticated to the server.",
      "technical": "Network logon; authentication alone does not establish code execution.",
      "lane": "SERVER-01 / account-a",
      "status": "observed",
      "milestone": true,
      "evidence": ["Security export, record 42"]
    }
  ],
  "entities": [
    {"id": "h1", "label": "WORKSTATION-01", "kind": "host"},
    {"id": "h2", "label": "SERVER-01", "kind": "host"}
  ],
  "relationships": [
    {
      "id": "r1", "source": "h1", "target": "h2",
      "label": "Remote authentication",
      "category": "identity",
      "status": "observed",
      "time": "2026-01-02T03:04:05Z",
      "evidence": ["Security export, record 42"]
    }
  ]
}
```

This authentication example supports an identity view. It deliberately does not qualify as lateral movement. Use `category: movement` only after reviewing host-to-host movement evidence, with source and target hosts identified. An observed movement edge supports a network view; uncertain movement edges may appear alongside it if labeled honestly.

Fields and limits:

- `title` is required (up to 100 characters). `subtitle` is optional (up to 180). `timezone` is an IANA zone or `UTC`; Python may need system zone data or the `tzdata` package for IANA zones. Use `UTC` if verified local conversion cannot be performed and report that limitation.
- `events` is bounded to 24 selected events. `id` is unique. `title` is short (up to 64 characters); `summary` up to 160; optional `technical` up to 240 and `lane` up to 60. `status` is `observed`, `supported`, `uncertain` or `unknown`. Every event needs nonempty `evidence` references.
- `time` is an offset-bearing ISO timestamp or `null` for an explicitly unknown time. Optional `time_label` (up to 80 characters) explains a range or approximation and is displayed alongside the normalized instant when supplied. Preparation from a human-formatted overview preserves its text in `time_label` and leaves `time` unknown for analyst review. It never guesses a timezone or parses dates from prose.
- `milestone: true` selects storyboard beats. Up to six are shown, with overflow disclosed in the manifest; use `timeline` or `technical` for the full selection. When no flags are supplied, the first six selected events are used.
- `entities` is bounded to 18 objects. Each has a unique `id`, short `label` (up to 64), and `kind` such as host/account/process/service/storage/domain. Relationship views show one documented source → target path per row to keep labels and dates clear. Repeated host labels refer to the same entity.
- `relationships` is bounded to 24 selected links, each with unique `id`, existing `source` and `target` IDs, a short `label` (up to 72), `category` (`movement`, `data` or `identity`), `status`, `time` (ISO offset timestamp or null) and nonempty `evidence`. Optional `time_label` communicates approximate or unknown timing.

Treat strings as plain text. Do not include secrets or raw command dumps. Evidence references should identify source files and records, not include pre-signed URLs or credentials. Store the reviewed brief with generated exports so later edits can reproduce the drawings.

[example-brief.json](example-brief.json) is a clearly labeled synthetic multi-host example with all six formats. Its movement evidence is explicitly simulated and must never be mixed into a real case.

Commands:

```powershell
# Draft from a case overview; review and save diagram-brief.json before building.
python incident-response/incident-diagrams/scripts/build_diagrams.py --case-dir CASE_OUTPUT --prepare

# Default complementary views; editable exports and local HTML gallery.
python incident-response/incident-diagrams/scripts/build_diagrams.py --brief CASE_OUTPUT/diagrams/diagram-brief.json

# Explicit audience-specific views and PNG rendering.
python incident-response/incident-diagrams/scripts/build_diagrams.py --brief BRIEF.json --formats storyboard technical data-flow --render

# Allow the documented npx fallback when package fetching is authorized.
python incident-response/incident-diagrams/scripts/build_diagrams.py --brief BRIEF.json --render --allow-npx
```

Output defaults to the brief's directory. Use `--output PATH` to select an exact directory. Exports include `.excalidraw` scenes, PNGs when rendered successfully, a reproducible `brief.snapshot.json`, `manifest.json` with evidence mappings, and an offline `index.html` gallery. Failed or skipped formats remain visible in the manifest. The gallery shows only the current build's exports, so stale PNGs from an earlier run are not presented as fresh output.

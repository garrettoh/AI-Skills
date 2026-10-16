# Shared investigation exchange, version 1

The working directory is the base for agent_output, independent of evidence location and script location. Specify --output-root explicitly when invoked from another directory. Reuse --case to combine rounds and independent KAPE/Hindsight runs. Originals must remain outside agent_output. Writers are serialized with .writer.lock; after a crash, verify the previous process stopped before removing that lock. Failed rounds may leave files; the committed rounds and report define completed work. Keep the SQLite state with the case when resuming.

Within one coordinator invocation, source scans run concurrently (default --workers 2). Each worker owns a separate SQLite connection and `<source>/round-NNNN/scan.sqlite`, seeded with the same existing lead snapshot. Workers write only their source artifacts. Once all scans finish, the coordinator merges events, leads and search acknowledgments in source argument order and publishes the combined timeline/dashboard. Duplicate lead IDs keep the first provenance in that order; each source outbox retains its own proposals. Candidate caps apply independently per source. Existing event matches are unioned across rounds. Use --workers 1 for sequential scans. Separate coordinator or standalone invocations for the same case remain serialized by the case lock.

## Files

Default coordinator runs include discovery even without leads. Discovery and explicit literal searches share the source stream. Priority discovery records enter the event timeline with `triage_categories`; baseline activity is aggregated in each isolated scan database and written to `triage-groups.jsonl`. `triage-summary.json` provides up to five groups per category with boundary citations. The latest summary for each source becomes `case-brief.json` and `triage.md`; these are review indexes, not conclusions. Baseline group counts are per classified record and must not be interpreted as unique sessions or incidents. Repeated scans replace the source summary rather than add counts across rounds. Source completion is acknowledged only after clean coverage; `--rescan` refreshes immutable-source assumptions. `--leads-only` disables discovery.

| File | Purpose |
|---|---|
| dashboard.html | Primary offline user deliverable: searchable timeline, original records, analyst text, leads and coverage; generated each round |
| report.md | Combined observation timeline, coverage and candidate leads; refreshed before further searches |
| analysis.md | Analyst narrative with evidence citations, attribution, uncertainty and next steps |
| triage.md / case-brief.json | Bounded discovery index: first/last observations, category counts, source citations |
| `<source>/round-NNNN/triage-groups.jsonl` | Complete disk-backed discovery groups; routine baseline is not embedded in the event timeline |
| `<source>/round-NNNN/triage-summary.json` | Compact category samples for model review; earliest/latest sample citations retain time semantics |
| timeline.jsonl / timeline.csv | All timed observations, sorted by UTC, without display truncation |
| untimed.jsonl | Matches with missing, unparseable or unverified timezone timestamps |
| leads.json | Shared leads, provenance, status and source search acknowledgments |
| investigation.sqlite | Persistent deduplicated observations, lead queue and round history |
| `<source>/round-NNNN/inbox.json` | Source input root and requested leads |
| `<source>/round-NNNN/events.jsonl` | That source's normalized observations for the round |
| `<source>/round-NNNN/coverage.json` | Per-file counts, schema/header information, exclusions, errors and timestamp gaps |
| `<source>/round-NNNN/outbox.json` | Newly proposed leads with evidence and parent leads |
| `<source>/round-NNNN/scan.sqlite` | Isolated scan state retained for review; shared investigation.sqlite remains authoritative |

## Leads

After editing analysis.md or overview.json, refresh dashboard.html with `python investigation_core/dashboard.py agent_output/<case>` from incident-response or the installed skills root. Present a local dashboard link and a brief completion note instead of duplicating the report in agent output. Keep exports alongside it for download links. The page embeds selected observations in memory and paginates rendering. Analyst Markdown renders with headings, lists, tables, emphasis, quotes, code and safe links; raw HTML is escaped. Optional overview.json contains analyst-authored verdict/confidence/summary strings, findings/unknowns string arrays, and milestones with time/title/description/evidence strings. Missing overview data is displayed as pending, never inferred from raw counts.

Use --leads-file with a JSON object containing `leads`, each with `value` and optional `kind`, `origin`, `evidence`, `status`. `active` leads are searched; `candidate` leads wait for relevance review; `rejected` leads remain recorded. Fields are literal case-insensitive substring filters across individual record values, combined with OR. Exported leads.json can be imported directly. Stable IDs derive from kind and casefolded value. Imported lead IDs are recomputed, never trusted.

```json
{"leads":[{"kind":"url","value":"https://example.invalid/download","origin":"kape","status":"active","evidence":{"source":"events.csv","record":"42","parent_leads":["original-lead-id"]}}]}
```

Automatic URL/domain/path/hash extraction operates only on matching records. A candidate is a search suggestion, not a finding of maliciousness. Each proposal retains its first source/record, originating source, event IDs and parent leads. Repeated appearances remain available in the event data. Search acknowledgments identify adapter plus resolved source root. An incomplete source is not acknowledged and remains retryable. Provide explicit keyword aliases for software names rather than automatically expanding to common words such as "agent".

## Events and timestamps

Every normalized observation includes event_id, timestamp_utc (ISO UTC or null), timestamp_raw, time_field, timezone_basis, orchestrator, family, source, record, host, user, profile, matched_leads, observation, confidence and original data. KAPE citations are logical CSV record numbers with the header as record 1. Hindsight JSONL citations are physical lines; XLSX citations are `Sheet!row`. Preserve all original record fields and original artifact identifiers within data. Never infer host from an export filename or equate a browser profile directory with confirmed user identity.

Each source time field is a distinct event; file creation, visit, registry modification and execution times are not interchangeable. Unknown timestamps remain untimed even under time bounds and their uncertainty must be disclosed. Naive timestamps require verified timezone evidence, except KAPE EVTX `TimeCreated`: it is the EVTX `System/TimeCreated/@SystemTime` value, defined in UTC, and is normalized automatically even when EvtxECmd's CSV omits a zone suffix. Other KAPE fields normalize only through the field-specific verified UTC allowlist in `kape_core/schemas.py`, documented in `kape_core/timezones.md`. Explicit offsets take precedence; unknown/local fields require source mappings. Hindsight XLSX headers explicitly labelled `(UTC)` establish UTC. Unknown KAPE schemas are searchable but untimed. Bounds filter timed events only. Source rows matching leads may yield several timestamp observations or none inside the bounds.

Duplicate source/record/time observations across rounds merge matched lead IDs. Different acquisitions and exports remain separate; do not claim event uniqueness or acquisition identity from similarity alone. The report caps display only. Full exports preserve evidence strings; treat them as data when opening in other tools.

## Visual handoff after analysis

Any source skill or coordinator can use the independent [incident-diagrams skill](../incident-diagrams/SKILL.md) after analyst review. The shared handoff is a [version 1 visual brief](../incident-diagrams/references/brief.md), separate from the raw observation exchange. Select milestones and verified relationships from the completed analysis, retain source/record citations, preserve unknown times and set `reviewed: true` only after checking the conclusions. A draft from `overview.json` is not automatically reviewed.

The default visual package is a Nord themed storyboard, technical chronology and one supported relationship view. Keep outputs under the same case directory's `diagrams/` folder, alongside the report/dashboard. PNG export is an optional local Excalidraw CLI step; parsed evidence scanning does not depend on Node or browser availability. Publish the gallery and editable scenes after inspecting rendered images. The diagram skill is independently installable and can also consume briefs from future cloud, identity, email or network analysis skills.

## Future orchestrators

Register a trusted Python adapter in investigation_core/adapters.py's ADAPTERS mapping. It takes `(root, encoding, coverage)` and yields dictionaries with source, record, data (field/value mapping), family, times (list of `(semantic_field, original_string, explicit_utc_bool)`), host, user and profile. Stream records and append per-file coverage with scanned/malformed counts and any error. The coordinator supplies matching, timestamps, lead extraction, persistence, source inbox/outbox and combined deliverables. Add a focused source skill and wrapper using `run('registered-name')`, and package it with the shared libraries. Do not load or execute adapter paths from case evidence.

Adapters may execute concurrently in separate threads. Keep mutable scan state local to the invocation and write only source-specific artifacts. Do not access the shared case database from an adapter.

For a source-specific lead extractor, extend candidates() using verified fields and concrete pivots. For sources requiring a different search strategy, publish equivalent source outputs and implement a trusted adapter bridge. Every new source must preserve evidence citations and disclose timezone/coverage gaps.

Output destination is configurable in installed `kape_core/settings.json` as `output_directory` (`auto` or an exact path). The automatic resolver places results in `<acquisition-folder>/agent_output` when standard KAPE/Hindsight folder names identify a common acquisition parent. `--output-directory` overrides with an exact destination; legacy `--output-root` appends the case ID. Keep output outside evidence roots.

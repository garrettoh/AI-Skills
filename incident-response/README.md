# Incident response skills

Twelve skills for parsed forensic exports and incident drawings, with Python 3.10+ and standard library helpers. Evidence remains local. Optional PNG export uses the official Excalidraw CLI and a local browser.

| Folder | Purpose |
|---|---|
| investigation-orchestrator/ | Main coordinator, shared leads and normalized deliverables |
| incident-diagrams/ | Independent Nord themed Excalidraw diagrams and optional PNGs |
| hindsight-orchestrator/ | Independent Hindsight browser analyzer, streaming JSONL first |
| kape_analysis/ | KAPE orchestrator, eight artifact skills and kape_core |
| investigation_core/ | Shared workflow, streaming adapters and exchange contract |
| scripts/ | Shared installers, component selection and verification |

## Installation

From the repository root in PowerShell:

```powershell
# Default: show all twelve skills and required helpers, then ask for approval.
.\incident-response\scripts\install.ps1

# Select one skill or several skills.
.\incident-response\scripts\install.ps1 -Skills hindsight-orchestrator
.\incident-response\scripts\install.ps1 -Skills incident-diagrams
.\incident-response\scripts\install.ps1 -Skills kape-orchestrator,ez-evtx-parser

# List choices or preview without installing.
.\incident-response\scripts\install.ps1 -List
.\incident-response\scripts\install.ps1 -Skills hindsight-orchestrator -Preview
```

Every individual skill can be selected. The plan names the destination, selected skills, required shared helpers, and whether components are new or will update existing files. Installation starts only after an explicit `y` or `yes`; Enter, rejection and closed input cancel with no destination writes. Default selection is all skills. Existing unselected skills are retained. Shared helper files used by existing skills may be updated and are included in the plan.

Default destination is `$CODEX_HOME/skills` or `~/.codex/skills`. Use `-SkillsRoot C:\path\to\skills` to choose another directory. The installer copies dependencies automatically: evidence analysis skills need kape_core; the three orchestrators also need investigation_core. The standalone incident-diagrams skill needs neither shared library. Selecting one orchestrator does not automatically install other skill folders. The main coordinator's adapters can process both source types with its helpers; install source skills when their specialist instructions are needed. Select incident-diagrams alongside an orchestrator for visual deliverables, or use the default full collection.

On macOS/Linux, use the same Python installer through the shell wrapper:

```sh
sh incident-response/scripts/install.sh
sh incident-response/scripts/install.sh --skills hindsight-orchestrator
sh incident-response/scripts/install.sh --skills kape-orchestrator ez-evtx-parser
sh incident-response/scripts/install.sh --skills hindsight-orchestrator --preview
sh incident-response/scripts/install.sh --skills-root /path/to/skills --skills hindsight-orchestrator
```

Direct cross-platform invocation: `python incident-response/scripts/install.py` with the same long options. A single positional destination remains supported for compatibility. Explicit `--skills all` selects all skills. Unknown names fail before copying. `-Yes` / `--yes` is for automation only after the user has explicitly approved the displayed plan; agents must follow [AGENT_INSTALL.md](AGENT_INSTALL.md).

After copying, verification checks only the selected skill folders and helpers, imports every selected executable, and exercises relevant synthetic workflows. Hindsight verifies JSONL normalization; KAPE verifies routing and timelines; EVTX verifies filtering; the main coordinator verifies cross-source lead exchange and persistent timelines. Other artifact skills receive executable/import checks. A verification failure returns a nonzero exit and does not claim success. To recheck a partial installation:

```powershell
python incident-response/scripts/verify_install.py --skills-root C:\path\to\skills --skills hindsight-orchestrator
```

Omit `--skills` to verify the full collection. Legacy KAPE installer and verifier paths still forward to the shared implementations.

## Shared investigations

The main orchestrator accepts KAPE and Hindsight folders without initial IOCs. It automatically discovers incident leads across downloads/domains, program inventory, logons, access/account/group changes, services/tasks/autoruns, RMMs, PowerShell and security detections. Source workers combine discovery and optional lead searches in one streaming pass, aggregate routine activity on disk, and retain priority records in the timeline. Read `triage.md` and `case-brief.json` before reviewing cited raw records; the agent writes the final account to `analysis.md`. Earliest observed evidence is not automatically initial compromise. Product presence, a logon or a script match alone does not prove malicious action or successful access.

```powershell
python incident-response/investigation-orchestrator/scripts/investigate.py --case incident-01 --source "kape=C:\case\parse" --source "hindsight=C:\case\Hindsight_Manual_Drops"
```

Add `--lead` for optional IOCs. RMM extraction is integrated into this command. Use `--leads-only` for a targeted search; completed discovery is cached per source and `--rescan` refreshes it. Category summaries are bounded to five groups with first/last evidence; all groups remain in per-source `triage-groups.jsonl`. See [the main skill](investigation-orchestrator/SKILL.md) for investigation and time-attribution rules.

Each structured investigation automatically creates **dashboard.html**, the primary user deliverable. Open it locally to browse a searchable UTC timeline with activity bars, source/artifact/date filters, untimed observations, full evidence records, lead provenance and coverage. The HTML is self-contained and uses no network services. Keep the case exports alongside it for download links. After writing analyst interpretation to analysis.md, refresh the page:

```powershell
python incident-response/investigation-orchestrator/scripts/build_dashboard.py agent_output/incident-01
```

The shared workflow calls the Python builder automatically at the end of every round. The builder fills a fixed HTML/CSS/JavaScript template with case exports; agents do not design or generate a new dashboard each time. The refresh command above only updates the embedded data after analyst edits. Generated reports and demos are excluded from Git by `reports/` and `agent_output/`; verification fixtures use temporary directories.

Deliver the dashboard link with a short completion note instead of repeating the incident report in agent output. It opens with an analyst-authored overview from optional `overview.json` (verdict, confidence, summary, findings, unknowns and cited milestones). The full report supports Markdown headings, lists, tables, emphasis, quotes, code and safe links with a contents sidebar. Raw records are available through evidence drill-down. Rendering works offline and escapes embedded HTML. The dashboard embeds selected observations and paginates rendering; browser memory grows with case size.

From the repository root, or use absolute script paths from your case working directory:

```powershell
python incident-response/investigation-orchestrator/scripts/investigate.py --case incident-01 --source "kape=C:\case\parse" --source "hindsight=C:\case\Hindsight_Manual_Drops" --lead fleetdeck --lead "fleet deck"
```

Both sources receive the initial leads. Hindsight scans JSONL one record at a time and excludes companion XLSX with a coverage note. Outputs go to `<working-directory>/agent_output/<case>/`: report.md, sorted timeline.jsonl/timeline.csv, untimed.jsonl, leads.json, persistent state and per-source inbox/events/coverage/outbox. Review observations, add analyst interpretation to analysis.md and deliver the timeline before pursuing discovered leads. Candidate URLs/domains/paths/hashes retain evidence and parent-lead citations.

KAPE and Hindsight scan concurrently by default within this single command. Each source writes its own staging database and artifacts; the coordinator merges both into one case database and dashboard after the scans finish. `--workers 1` runs sequentially; `--workers N` sets the concurrency limit. The case lock still permits only one coordinator invocation per case. Scan concurrency can reduce elapsed time when sources are independent, although disk contention and CPU work can limit the gain.

For an agentic investigation, ask the agent to investigate a suspected FleetDeck download using both evidence roots. The agent reads investigation-orchestrator/SKILL.md and invokes the command above. Two Python workers search Windows CSV and browser JSONL at the same time; the agent then reviews their combined evidence and writes analysis.md. A discovered download URL can become a reviewed lead in the next round to connect browser activity with Windows artifacts. The helper supplies concurrent source scans without requiring separate model agents.

Reuse the case ID and pass a reviewed JSON lead list with `--leads-file`, or deliberately adopt all candidates with `--follow-candidates`. Each invocation completes one round and its deliverable. Run one writer per case. Previously searched leads are skipped per source root; `--rescan` is required after evidence or scope changes. Time bounds require ISO offsets. KAPE EVTX `TimeCreated` is automatically normalized as UTC from EVTX `System/TimeCreated/@SystemTime`; other verified EZ Tools UTC fields also normalize automatically (see `kape_analysis/kape_core/timezones.md`); unknown/local fields require verified `--source-timezone FAMILY.FIELD=ZONE`. Display caps do not stop scans or truncate full event exports.

Standalone Hindsight:

```powershell
python incident-response/hindsight-orchestrator/scripts/hunt_hindsight.py "C:\case\Hindsight_Manual_Drops" --case incident-01 --lead fleetdeck
```

Standalone KAPE and its artifact helpers are documented in the [KAPE guide](kape_analysis/README.md). Future source orchestrators register through the [exchange contract](investigation_core/exchange.md). Preserve source/record citations, host/user/profile uncertainty and original timestamp semantics. Matching a hypothesis does not establish compromise.

## Incident diagrams

The [incident-diagrams skill](incident-diagrams/SKILL.md) turns reviewed analysis into complementary views for nontechnical and technical audiences. It is a standalone skill and is included in the default full installation. Any analysis skill can hand it a [reviewed visual brief](incident-diagrams/references/brief.md); it does not require KAPE or Windows evidence.

The workflow is **analysis and cited findings → draft brief → analyst review → Nord themed editable scenes → local PNG export → visual inspection → gallery delivery**. Storyboard and technical chronology are the default pair, with one supported network movement, data flow or identity view added automatically. Explicit format selection is available. The [format guide](incident-diagrams/references/formats.md) describes when to use each view.

```powershell
# Prepare a draft from the completed case overview; review it before building.
python incident-response/incident-diagrams/scripts/build_diagrams.py --case-dir agent_output/incident-01 --prepare

# After review, save diagrams/diagram-brief.json with reviewed: true.
python incident-response/incident-diagrams/scripts/build_diagrams.py --brief agent_output/incident-01/diagrams/diagram-brief.json --render
```

JSON generation is Python standard library only. PNG rendering uses the official [Excalidraw CLI](https://github.com/excalidraw/cli), Node.js 22+ and a local browser. If the CLI is absent, `--allow-npx` explicitly permits its documented npx fallback when package fetching is authorized. No account, API key or scene publication is needed for local rendering. The installer copies the skill but does not install Node, browsers or npm packages. A failed render retains editable scenes, records the error and returns a nonzero status.

Outputs stay under the case's `diagrams/` directory: `.excalidraw`, successful `.png` exports, `index.html` for local review and `manifest.json` with evidence mappings and skipped formats. The helper preserves unknown times and declines unsupported network views. It does not infer lateral movement or successful exfiltration from configured access or command targets. The agent reviews the exported PNGs for readability before delivering them.

## Timezones

Use `--timezone America/Los_Angeles` (or any IANA name / fixed offset) for analysis display. Installation accepts `--timezone` / PowerShell `-Timezone`. Saved case preference overrides installation default. UTC remains the correlation clock; raw evidence is retained. The HTML evidence timeline has a timezone selector. Verified EZ Tools fields normalize automatically; SBECmd and unverified registry plugin local fields need `--source-timezone FAMILY.FIELD=ZONE`. See the shared `kape_core/timezones.md` reference.

## Agent output location

The installed setting `output_directory` defaults to `auto`. For recognized acquisitions such as `<tenant>/<host_date_time>/<hostname>_KAPE/parse` plus `Hindsight_Manual_Drops`, the orchestrator writes to `<tenant>/<host_date_time>/agent_output/`, beside the artifact folders. If it cannot identify that layout, it uses `<working-directory>/agent_output/<case>/`. Set the installation default with `python incident-response/scripts/install.py --output-directory auto` or PowerShell `./scripts/install.ps1 -OutputDirectory auto`; give an absolute path to use a fixed destination. During analysis, `--output-directory PATH` selects the exact output folder for that run. Legacy `--output-root PATH` still appends the case name.

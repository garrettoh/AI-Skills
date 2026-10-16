# AI-Skills: KAPE CSV threat hunting

Nine KAPE skills for already parsed forensic CSV exports. Python 3.10+; standard library only. Individual installers include required shared helpers. Evidence remains local.

## Shared investigations

Hindsight and the main investigation orchestrator are separate folders under incident-response. See the [shared guide](../README.md) for lead exchange, normalized timelines and installation of any individual skill. KAPE CSV helpers remain in this folder.

## Quick start

Run from the repository root (prefix script paths with incident-response/kape_analysis/):

    python incident-response/kape_analysis/kape-orchestrator/scripts/route_artifacts.py "C:\Users\graese\Desktop\parse" --output reports/inventory.json
    python incident-response/kape_analysis/ez-evtx-parser/scripts/filter_csv.py "C:\Users\graese\Desktop\parse" --keyword powershell --columns TimeCreated,EventId,Computer,UserName,Payload --output reports/events.md
    python incident-response/kape_analysis/kape-orchestrator/scripts/hunt_csv.py "C:\Users\graese\Desktop\parse" --keyword powershell --output reports/hunt.md
    python incident-response/kape_analysis/kape-orchestrator/scripts/correlate_timeline.py "C:\Users\graese\Desktop\parse" --keyword powershell --output reports/timeline.md

Inspect headers before choosing columns. EVTX `TimeCreated` values are normalized as UTC automatically because they originate from EVTX `System/TimeCreated/@SystemTime`. Other verified UTC fields normalize automatically via the field allowlist. Use --timezone for presentation and --source-timezone FAMILY.FIELD=ZONE for verified local exports. Unknown fields stay untimed. See kape_core/timezones.md. Validate host, user, path and timestamp semantics before causal conclusions.

## Modules

| Skill | Artifacts |
|---|---|
| kape-orchestrator | Header inventory, generic hunting, cross-artifact timeline |
| ez-evtx-parser | EvtxECmd |
| ez-prefetch-parser | PECmd, Amcache, AppCompatCache |
| ez-registry-parser | RECmd batch and plugin details |
| ez-filesystem-parser | MFTECmd MFT, USN, Boot, SDS |
| ez-fileaccess-parser | LECmd, jump lists, ShellBags |
| ez-srum-parser | SrumECmd |
| ez-recyclebin-parser | RBCmd |
| ez-activity-parser | Windows Activity, package metadata |

## Filter and resource contract

--keyword performs case-insensitive literal substring matching. --ioc matches an entire field, case-insensitively. Repeat either for OR. Repeated --where COLUMN=VALUE restrictions are ANDed with that group. Use keywords for IOCs embedded in payloads. --search-columns restricts matching; --columns selects displayed fields; both accept comma-separated exact headers.

Streaming retains one CSV record at a time. Reports default to 100 records and 240 characters per field. Scans continue for accurate counts. Timelines use temporary SQLite disk storage and sort by UTC; disk usage scales with matching events. Inventory retains file metadata only. Fields above 16 MiB produce a disclosed parsing error. Comma, tab and semicolon delimiters are detected; default encoding is UTF-8 with optional BOM.

Exit code 0 indicates a completed scan; 2 indicates errors or malformed rows needing review. Unknown schemas remain searchable but do not generate timeline fields. Non-CSV logs and ZIP archives are excluded. No commands from evidence are executed. Reports must be outside the evidence directory.

## Per-user known-good exclusions

The KAPE orchestrator package includes an empty `kape-orchestrator/known-good.json`. Add approved, scoped exclusions to `kape-orchestrator/known-good.local.json`; the nested `.gitignore` keeps personal entries out of commits, so they remain in your checkout across `git pull`. The installer copies that file into the installed skill when present. Keep entries specific, documented, and time-bounded. Exclusions lower routine triage priority but never hide matching evidence or override suspicious context. Use `kape-orchestrator/references/known-good.template.json` for entry fields.

## Extending and packaging

Add specific verified header signatures and semantic time fields to incident-response/kape_analysis/kape_core/schemas.py, then a focused skill and wrapper. Use the shared installer for individual deployment with required helpers; repository scripts can also run directly. No third-party dependencies are required.

Local sample headers informed the profiles; no sample CSV data is included in Git. PECmd detailed and flattened timeline exports were verified against the supplied ProgramExecution1 samples. Detailed execution times include LastRun and PreviousRun0–6; flattened exports use RunTime. Discovery is recursive and independent of folder name. Use one companion export per acquisition for execution counts; both contain overlapping run observations. No other binary parser or non-CSV log support is implied.

## PECmd execution pivots

Use ez-prefetch-parser/scripts/filter_csv.py on a detailed PECmd CSV with --search-columns ExecutableName for executable pivots, or FilesLoaded/Directories for referenced paths. Inspect RunCount, ParsingError and Note. Use ez-prefetch-parser/scripts/correlate_timeline.py on either detailed or flattened exports for execution timelines; timezone rules above apply. See [Prefetch skill](ez-prefetch-parser/SKILL.md) for commands and interpretation limits.

## Install KAPE skills

Use the [shared installer](../README.md#installation), which defaults to all eleven skills and asks for confirmation after showing the full plan. To install KAPE alone from the repository root:

    .\incident-response\scripts\install.ps1 -Skills kape-orchestrator

Select any child skill in the same way, for example `-Skills ez-evtx-parser`. Required helpers are included automatically. The old kape_analysis/scripts/install.ps1 and install.sh entry points forward to the shared installer and accept the same options.

The [agent installation guide](../AGENT_INSTALL.md) requires showing the plan and receiving user approval before installation.

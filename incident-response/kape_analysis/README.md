# AI-Skills: KAPE CSV threat hunting

Nine modular skills for already parsed forensic CSV exports. Python 3.10+; standard library only. Keep kape_core beside all skill folders. Evidence remains local.

## Quick start

Run from the repository root (prefix script paths with incident-response/kape_analysis/):

    python incident-response/kape_analysis/kape-orchestrator/scripts/route_artifacts.py "C:\Users\graese\Desktop\parse" --output reports/inventory.json
    python incident-response/kape_analysis/ez-evtx-parser/scripts/filter_csv.py "C:\Users\graese\Desktop\parse" --keyword powershell --columns TimeCreated,EventId,Computer,UserName,Payload --output reports/events.md
    python incident-response/kape_analysis/kape-orchestrator/scripts/hunt_csv.py "C:\Users\graese\Desktop\parse" --keyword powershell --output reports/hunt.md
    python incident-response/kape_analysis/kape-orchestrator/scripts/correlate_timeline.py "C:\Users\graese\Desktop\parse" --keyword powershell --output reports/timeline.md

Inspect headers before choosing columns. Add --assume-utc only after confirming naive export timestamps are UTC. Otherwise only offset-bearing timestamps enter the timeline. Validate host, user, path and timestamp semantics before causal conclusions.

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

## Extending and packaging

Add specific verified header signatures and semantic time fields to incident-response/kape_analysis/kape_core/schemas.py, then a focused skill and wrapper. Deploy the complete checkout: individual skill folders rely on the shared sibling package. No third-party dependencies or installation are required to execute helpers.

Local sample headers informed the profiles; no sample CSV data is included in Git. PECmd detailed and flattened timeline exports were verified against the supplied ProgramExecution1 samples. Detailed execution times include LastRun and PreviousRun0–6; flattened exports use RunTime. Discovery is recursive and independent of folder name. Use one companion export per acquisition for execution counts; both contain overlapping run observations. No other binary parser or non-CSV log support is implied.

## PECmd execution pivots

Use ez-prefetch-parser/scripts/filter_csv.py on a detailed PECmd CSV with --search-columns ExecutableName for executable pivots, or FilesLoaded/Directories for referenced paths. Inspect RunCount, ParsingError and Note. Use ez-prefetch-parser/scripts/correlate_timeline.py on either detailed or flattened exports for execution timelines; timezone rules above apply. See [Prefetch skill](ez-prefetch-parser/SKILL.md) for commands and interpretation limits.

## Install KAPE skills

From the repository root in PowerShell:

    .\incident-response\kape_analysis\scripts\install.ps1

The installer copies the nine KAPE skills and their shared kape_core helper to %CODEX_HOME%\skills (or %USERPROFILE%\.codex\skills) and verifies the installed copy. To choose another skills directory:

    .\incident-response\kape_analysis\scripts\install.ps1 -SkillsRoot C:\path\to\skills

To verify or recheck an installation:

    python .\incident-response\kape_analysis\scripts\verify_install.py --skills-root "$env:USERPROFILE\.codex\skills"

The verifier checks each skill and runs schema routing, an EVTX keyword filter, and timeline correlation against temporary synthetic CSV evidence.

## macOS and Linux

Run from the repository root:

    ./incident-response/kape_analysis/scripts/install.sh

You may pass an alternate skills directory as its only argument. For an agent-ready instruction, see [AGENT_INSTALL.md](AGENT_INSTALL.md).

# Incident response skills

Eleven skills for parsed forensic exports, with Python 3.10+ and standard library helpers. Evidence remains local.

| Folder | Purpose |
|---|---|
| investigation-orchestrator/ | Main coordinator, shared leads and normalized deliverables |
| hindsight-orchestrator/ | Independent Hindsight browser analyzer, streaming JSONL first |
| kape_analysis/ | KAPE orchestrator, eight artifact skills and kape_core |
| investigation_core/ | Shared workflow, streaming adapters and exchange contract |
| scripts/ | Shared installers, component selection and verification |

## Installation

From the repository root in PowerShell:

```powershell
# Default: show all eleven skills and required helpers, then ask for approval.
.\incident-response\scripts\install.ps1

# Select one skill or several skills.
.\incident-response\scripts\install.ps1 -Skills hindsight-orchestrator
.\incident-response\scripts\install.ps1 -Skills kape-orchestrator,ez-evtx-parser

# List choices or preview without installing.
.\incident-response\scripts\install.ps1 -List
.\incident-response\scripts\install.ps1 -Skills hindsight-orchestrator -Preview
```

Every individual skill can be selected. The plan names the destination, selected skills, required shared helpers, and whether components are new or will update existing files. Installation starts only after an explicit `y` or `yes`; Enter, rejection and closed input cancel with no destination writes. Default selection is all skills. Existing unselected skills are retained. Shared helper files used by existing skills may be updated and are included in the plan.

Default destination is `$CODEX_HOME/skills` or `~/.codex/skills`. Use `-SkillsRoot C:\path\to\skills` to choose another directory. The installer copies dependencies automatically: every current skill needs kape_core; the three orchestrators also need investigation_core. Selecting one orchestrator does not automatically install other skill folders. The main coordinator's adapters can process both source types with its helpers; install source skills when their specialist instructions are needed.

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

Each structured investigation automatically creates **dashboard.html**, the primary user deliverable. Open it locally to browse a searchable UTC timeline with activity bars, source/artifact/date filters, untimed observations, full evidence records, lead provenance and coverage. The HTML is self-contained and uses no network services. Keep the case exports alongside it for download links. After writing analyst interpretation to analysis.md, refresh the page:

```powershell
python incident-response/investigation-orchestrator/scripts/build_dashboard.py agent_output/incident-01
```

The shared workflow calls the Python builder automatically at the end of every round. The builder fills a fixed HTML/CSS/JavaScript template with case exports; agents do not design or generate a new dashboard each time. The refresh command above only updates the embedded data after analyst edits. Generated reports and demos are excluded from Git by `reports/` and `agent_output/`; verification fixtures use temporary directories.

Deliver the dashboard link with a short completion note instead of repeating the incident report in agent output. The dashboard embeds all matched observations and paginates rendering; browser memory grows with case size. Analyst Markdown is shown as literal text.

From the repository root, or use absolute script paths from your case working directory:

```powershell
python incident-response/investigation-orchestrator/scripts/investigate.py --case incident-01 --source "kape=C:\case\parse" --source "hindsight=C:\case\Hindsight_Manual_Drops" --lead fleetdeck --lead "fleet deck"
```

Both sources receive the initial leads. Hindsight scans JSONL one record at a time and excludes companion XLSX with a coverage note. Outputs go to `<working-directory>/agent_output/<case>/`: report.md, sorted timeline.jsonl/timeline.csv, untimed.jsonl, leads.json, persistent state and per-source inbox/events/coverage/outbox. Review observations, add analyst interpretation to analysis.md and deliver the timeline before pursuing discovered leads. Candidate URLs/domains/paths/hashes retain evidence and parent-lead citations.

KAPE and Hindsight scan concurrently by default within this single command. Each source writes its own staging database and artifacts; the coordinator merges both into one case database and dashboard after the scans finish. `--workers 1` runs sequentially; `--workers N` sets the concurrency limit. The case lock still permits only one coordinator invocation per case. Scan concurrency can reduce elapsed time when sources are independent, although disk contention and CPU work can limit the gain.

For an agentic investigation, ask the agent to investigate a suspected FleetDeck download using both evidence roots. The agent reads investigation-orchestrator/SKILL.md and invokes the command above. Two Python workers search Windows CSV and browser JSONL at the same time; the agent then reviews their combined evidence and writes analysis.md. A discovered download URL can become a reviewed lead in the next round to connect browser activity with Windows artifacts. The helper supplies concurrent source scans without requiring separate model agents.

Reuse the case ID and pass a reviewed JSON lead list with `--leads-file`, or deliberately adopt all candidates with `--follow-candidates`. Each invocation completes one round and its deliverable. Run one writer per case. Previously searched leads are skipped per source root; `--rescan` is required after evidence or scope changes. Time bounds require ISO offsets; naive timestamps stay untimed unless `--assume-utc` has been verified. Display caps do not stop scans or truncate full event exports.

Standalone Hindsight:

```powershell
python incident-response/hindsight-orchestrator/scripts/hunt_hindsight.py "C:\case\Hindsight_Manual_Drops" --case incident-01 --lead fleetdeck
```

Standalone KAPE and its artifact helpers are documented in the [KAPE guide](kape_analysis/README.md). Future source orchestrators register through the [exchange contract](investigation_core/exchange.md). Preserve source/record citations, host/user/profile uncertainty and original timestamp semantics. Matching a hypothesis does not establish compromise.

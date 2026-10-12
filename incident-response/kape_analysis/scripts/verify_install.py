"""Verify installed KAPE skills and exercise routing, filtering, and timeline output."""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILLS = [
    "investigation-orchestrator", "hindsight-orchestrator",
    "kape-orchestrator", "ez-evtx-parser", "ez-prefetch-parser",
    "ez-registry-parser", "ez-filesystem-parser", "ez-fileaccess-parser",
    "ez-srum-parser", "ez-recyclebin-parser", "ez-activity-parser",
]

def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", required=True, type=Path,
                        help="Directory containing installed skill folders and kape_core")
    args = parser.parse_args()
    skills_root = args.skills_root.expanduser().resolve()
    missing = [name for name in SKILLS if not (skills_root/name/"SKILL.md").is_file()]
    if not (skills_root/"kape_core"/"cli.py").is_file():
        missing.append("kape_core")
    if not (skills_root/"investigation_core"/"workflow.py").is_file():
        missing.append("investigation_core")
    if missing:
        raise SystemExit("Missing installed components: " + ", ".join(missing))

    router = skills_root/"kape-orchestrator/scripts/route_artifacts.py"
    evtx = skills_root/"ez-evtx-parser/scripts/filter_csv.py"
    timeline = skills_root/"kape-orchestrator/scripts/correlate_timeline.py"
    with tempfile.TemporaryDirectory(prefix="kape-skill-check-") as temporary:
        work = Path(temporary)
        evidence = work/"evidence"
        evidence.mkdir()
        sample = evidence/"events.csv"
        with sample.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["EventId", "TimeCreated", "Provider", "Computer", "Payload"])
            writer.writerow(["4104", "2026-01-02T03:04:05Z", "PowerShell", "test-host", "powershell.exe"])
        inventory = work/"inventory.json"
        run([sys.executable, str(router), str(evidence), "--output", str(inventory)])
        profiles = json.loads(inventory.read_text(encoding="utf-8"))["files"]
        if len(profiles) != 1 or profiles[0]["family"] != "evtx":
            raise RuntimeError("Router did not identify the synthetic EvtxECmd schema")

        filtered = work/"filtered.md"
        run([sys.executable, str(evtx), str(evidence), "--keyword", "powershell.exe",
             "--output", str(filtered)])
        report = filtered.read_text(encoding="utf-8")
        if "matching rows: 1" not in report or "4104" not in report:
            raise RuntimeError("Installed EVTX filter did not return the expected matching row")

        ordered = work/"timeline.md"
        run([sys.executable, str(timeline), str(evidence), "--keyword", "powershell.exe",
             "--output", str(ordered), "--limit", "5"])
        report = ordered.read_text(encoding="utf-8")
        if "Events in time bounds: 1" not in report or "2026-01-02T03:04:05" not in report:
            raise RuntimeError("Installed timeline helper did not return the expected timestamp")

    run([sys.executable, str(Path(__file__).with_name('verify_orchestration.py')),
         '--skills-root', str(skills_root)])
    print(f"PASS: {len(SKILLS)} skills and shared helpers are installed at {skills_root}")
    print("PASS: schema routing, keyword filtering, and UTC timeline correlation")

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)

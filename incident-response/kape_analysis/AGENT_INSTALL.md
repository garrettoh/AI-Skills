# Agent installation instruction

Give this instruction to your coding agent after opening or cloning this repository:

> Install the KAPE analysis skills from incident-response/kape_analysis into this user's Codex skills directory. Read that directory's README.md and AGENT_INSTALL.md, choose scripts/install.ps1 on Windows or scripts/install.sh on macOS/Linux, run the installer, and confirm its verification passes. If you cannot tell the platform, inspect the shell and use the matching script. Keep the installation destination at the user's CODEX_HOME/skills or default .codex/skills; do not alter evidence data. Report the installed path and verification results.

## Agent procedure

1. Locate this repository and read incident-response/kape_analysis/README.md.
2. Run incident-response/kape_analysis/scripts/install.ps1 in PowerShell on Windows, or incident-response/kape_analysis/scripts/install.sh in a POSIX shell on macOS/Linux.
3. The installer chooses $CODEX_HOME/skills when CODEX_HOME is set, otherwise $HOME/.codex/skills (Windows uses %USERPROFILE%\.codex\skills). An explicit alternate directory can be passed to either installer.
4. Wait for the installer's verification. It checks all nine skill folders and shared kape_core, then exercises routing, EVTX filtering, and timeline correlation with temporary synthetic CSVs.
5. If installation verification fails, report the command, error, and destination. Do not claim success. To rerun verification, execute python3 incident-response/kape_analysis/scripts/verify_install.py --skills-root "$CODEX_HOME/skills" (use the resolved destination if CODEX_HOME is unset).

The scripts only copy these skill folders and kape_core into the skills directory. They do not install Python packages or read the case evidence directory.

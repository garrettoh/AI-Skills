#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACKAGE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
if [ "$#" -gt 1 ]; then
    printf '%s\n' "Usage: $0 [skills-directory]" >&2
    exit 2
fi
if [ "$#" -eq 1 ]; then
    SKILLS_ROOT=$1
elif [ -n "${CODEX_HOME-}" ]; then
    SKILLS_ROOT=${CODEX_HOME}/skills
else
    SKILLS_ROOT=${HOME:?HOME is not set}/.codex/skills
fi
mkdir -p "$SKILLS_ROOT"
SKILLS_ROOT=$(CDPATH= cd -- "$SKILLS_ROOT" && pwd)
SKILLS="kape-orchestrator
ez-evtx-parser
ez-prefetch-parser
ez-registry-parser
ez-filesystem-parser
ez-fileaccess-parser
ez-srum-parser
ez-recyclebin-parser
ez-activity-parser"
for name in $SKILLS; do
    source_dir=$PACKAGE_ROOT/$name
    if [ ! -f "$source_dir/SKILL.md" ]; then
        printf 'Missing skill source: %s\n' "$source_dir" >&2
        exit 1
    fi
    mkdir -p "$SKILLS_ROOT/$name"
    cp -R "$source_dir/." "$SKILLS_ROOT/$name/"
done
mkdir -p "$SKILLS_ROOT/kape_core"
cp -R "$PACKAGE_ROOT/kape_core/." "$SKILLS_ROOT/kape_core/"
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    printf '%s\n' "Python 3 is required to verify the installation." >&2
    exit 1
fi
"$PYTHON" "$PACKAGE_ROOT/scripts/verify_install.py" --skills-root "$SKILLS_ROOT"
printf 'KAPE skills installed and verified in %s\n' "$SKILLS_ROOT"

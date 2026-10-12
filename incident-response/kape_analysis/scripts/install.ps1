[CmdletBinding()]
param(
    [string]$SkillsRoot
)

$ErrorActionPreference = "Stop"
$packageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $SkillsRoot) {
    if ($env:CODEX_HOME) {
        $SkillsRoot = Join-Path $env:CODEX_HOME "skills"
    } else {
        $SkillsRoot = Join-Path $env:USERPROFILE ".codex\skills"
    }
}
$SkillsRoot = [System.IO.Path]::GetFullPath($SkillsRoot)
New-Item -ItemType Directory -Path $SkillsRoot -Force | Out-Null

$skillNames = @(
    "investigation-orchestrator",
    "hindsight-orchestrator",
    "kape-orchestrator",
    "ez-evtx-parser",
    "ez-prefetch-parser",
    "ez-registry-parser",
    "ez-filesystem-parser",
    "ez-fileaccess-parser",
    "ez-srum-parser",
    "ez-recyclebin-parser",
    "ez-activity-parser"
)

foreach ($name in $skillNames) {
    $source = Join-Path $packageRoot $name
    if (-not (Test-Path (Join-Path $source "SKILL.md"))) {
        throw "Skill source is missing: $source"
    }
    Copy-Item -Path $source -Destination $SkillsRoot -Recurse -Force
}
Copy-Item -Path (Join-Path $packageRoot "kape_core") -Destination $SkillsRoot -Recurse -Force
Copy-Item -Path (Join-Path $packageRoot "investigation_core") -Destination $SkillsRoot -Recurse -Force

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python 3 is required. Install Python, then run scripts/verify_install.py manually."
}
$verifier = Join-Path $packageRoot "scripts\verify_install.py"
& $python.Source $verifier --skills-root $SkillsRoot
if ($LASTEXITCODE -ne 0) {
    throw "Installation verification failed with exit code $LASTEXITCODE"
}
Write-Host "Investigation, Hindsight and KAPE skills installed and verified in $SkillsRoot"

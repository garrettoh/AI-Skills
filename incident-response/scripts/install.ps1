[CmdletBinding()]
param(
    [string]$SkillsRoot,
    [string]$Timezone,
    [string]$OutputDirectory,
    [switch]$ListTimezones,
    [Alias('Skill')][string[]]$Skills,
    [switch]$List,
    [switch]$Preview,
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3.10+ is required before installation.' }
$installerArgs = @((Join-Path $PSScriptRoot 'install.py'))
if ($OutputDirectory) { $installerArgs += @('--output-directory', $OutputDirectory) }
if ($Timezone) { $installerArgs += @('--timezone', $Timezone) }
if ($ListTimezones) { $installerArgs += '--list-timezones' }
if ($SkillsRoot) { $installerArgs += @('--skills-root', $SkillsRoot) }
if ($Skills) { $installerArgs += '--skills'; $installerArgs += $Skills }
if ($List) { $installerArgs += '--list' }
if ($Preview) { $installerArgs += '--preview' }
if ($Yes) { $installerArgs += '--yes' }
& $python.Source @installerArgs
if ($LASTEXITCODE -ne 0) { throw "Installer failed with exit code $LASTEXITCODE" }

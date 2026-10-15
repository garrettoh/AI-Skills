[CmdletBinding()]
param(
    [string]$SkillsRoot,
    [string]$Timezone,
    [switch]$ListTimezones,
    [Alias('Skill')][string[]]$Skills,
    [switch]$List,
    [switch]$Preview,
    [switch]$Yes
)
# Compatibility entry point for the shared installer.
& (Join-Path $PSScriptRoot '../../scripts/install.ps1') @PSBoundParameters

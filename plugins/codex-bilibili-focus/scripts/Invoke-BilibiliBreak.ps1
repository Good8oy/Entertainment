[CmdletBinding()]
param(
    [string]$Url = "https://www.bilibili.com/",
    [int]$ReturnDelaySeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "Open-BilibiliBreak.ps1") -Url $Url

if ($ReturnDelaySeconds -gt 0) {
    Start-Sleep -Seconds $ReturnDelaySeconds
    & (Join-Path $scriptDir "Focus-Codex.ps1")
}


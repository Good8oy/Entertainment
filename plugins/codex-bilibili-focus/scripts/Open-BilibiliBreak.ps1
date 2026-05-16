[CmdletBinding()]
param(
    [string]$Url = "https://www.bilibili.com/"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not ("CodexBilibiliFocus.OpenNative" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace CodexBilibiliFocus {
    public static class OpenNative {
        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll", SetLastError=true)]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    }
}
"@
}

$stateDir = Join-Path $env:LOCALAPPDATA "CodexBilibiliFocus"
$statePath = Join-Path $stateDir "state.json"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$foregroundWindow = [CodexBilibiliFocus.OpenNative]::GetForegroundWindow()
$foregroundProcessId = [uint32]0
[CodexBilibiliFocus.OpenNative]::GetWindowThreadProcessId($foregroundWindow, [ref]$foregroundProcessId) | Out-Null

$state = [ordered]@{
    startedAt = (Get-Date).ToString("o")
    url = $Url
    foregroundWindowHandle = $foregroundWindow.ToInt64()
    foregroundProcessId = [int]$foregroundProcessId
}

$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
Start-Process $Url
Write-Output "Opened $Url"

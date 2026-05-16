[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not ("CodexBilibiliFocus.FocusNative" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace CodexBilibiliFocus {
    public static class FocusNative {
        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        public static extern bool IsIconic(IntPtr hWnd);
    }
}
"@
}

function Get-CodexMainWindow {
    $windows = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.MainWindowHandle -ne 0 -and
            ($_.ProcessName -ieq "codex" -or $_.ProcessName -ieq "Codex")
        } |
        Sort-Object @{ Expression = { $_.MainWindowTitle -eq "Codex" }; Descending = $true },
                    @{ Expression = { $_.StartTime }; Descending = $true }

    return $windows | Select-Object -First 1
}

$target = Get-CodexMainWindow
if ($null -eq $target) {
    throw "Could not find a running Codex desktop window."
}

$handle = [IntPtr]$target.MainWindowHandle
if ([CodexBilibiliFocus.FocusNative]::IsIconic($handle)) {
    [CodexBilibiliFocus.FocusNative]::ShowWindowAsync($handle, 9) | Out-Null
} else {
    [CodexBilibiliFocus.FocusNative]::ShowWindowAsync($handle, 5) | Out-Null
}

Start-Sleep -Milliseconds 150
[CodexBilibiliFocus.FocusNative]::SetForegroundWindow($handle) | Out-Null
Write-Output "Focused Codex window from process $($target.Id)."

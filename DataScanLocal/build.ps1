$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    & (Join-Path $PSScriptRoot 'setup.ps1')
}
& uv pip install --python $taskPython --link-mode=copy -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
& $taskPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
New-Item -ItemType Directory -Path artifacts -Force | Out-Null
& $taskPython -c "from PySide6.QtWidgets import QApplication; from datascan.app import MainWindow; app=QApplication([]); assert MainWindow.icon().pixmap(64,64).save('artifacts/app.ico')"
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
$taskBasePython = & $taskPython -c "import sys; print(sys.base_prefix)"
$taskOriginalPath = $env:PATH
try {
    # Avoid copying unrelated application runtimes (Poppler/libheif/Conda) from PATH.
    $env:PATH = "$PSScriptRoot\.venv\Scripts;$taskBasePython;$taskBasePython\DLLs;$env:SystemRoot\System32;$env:SystemRoot"
    & $taskPython -m PyInstaller --noconfirm --clean --onefile --windowed --name DataScanLocal --icon artifacts/app.ico run.py
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
} finally {
    $env:PATH = $taskOriginalPath
}
$taskCheckOutput = Join-Path $PSScriptRoot 'artifacts\frozen-self-test.json'
$taskCheckProcess = Start-Process -FilePath (Join-Path $PSScriptRoot 'dist\DataScanLocal.exe') -ArgumentList @('--self-test', ('"{0}"' -f $taskCheckOutput)) -WindowStyle Hidden -Wait -PassThru
if ($taskCheckProcess.ExitCode -ne 0) { throw 'Frozen executable self-test failed.' }
$taskCheckResult = Get-Content -LiteralPath $taskCheckOutput -Raw | ConvertFrom-Json
if (-not $taskCheckResult.success -or -not $taskCheckResult.frozen) { throw 'Frozen-runtime verification did not pass.' }
Write-Host 'Built: dist\DataScanLocal.exe'

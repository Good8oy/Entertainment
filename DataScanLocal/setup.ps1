$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required for source setup. Install uv from https://docs.astral.sh/uv/ or use the portable DataScanLocal.exe.'
}
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    & uv venv .venv --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Could not create a Python 3.12 environment.' }
}
& $taskPython -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12 or later is required'"
if ($LASTEXITCODE -ne 0) { throw 'Unsupported Python version in .venv. Recreate this project environment with Python 3.12.' }
& uv pip install --python $taskPython --link-mode=copy -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Ready. Run: .\.venv\Scripts\python.exe run.py'

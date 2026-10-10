$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.python'
$env:UV_CONCURRENT_DOWNLOADS = '2'
$env:PYTHONUTF8 = '1'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv from https://docs.astral.sh/uv/getting-started/installation/ and retry.'
}
uv python install 3.12.10
if ($LASTEXITCODE) { throw 'Python download failed.' }
uv venv --allow-existing --python 3.12.10 .venv
if ($LASTEXITCODE) { throw 'Environment creation failed.' }
uv pip install --python '.venv\Scripts\python.exe' -r requirements-lock.txt
if ($LASTEXITCODE) { throw 'Package installation failed.' }
New-Item -ItemType Directory -Force models | Out-Null
if (-not (Test-Path -LiteralPath 'models\yolo11s.pt')) {
    Invoke-WebRequest 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt' -OutFile 'models\yolo11s.tmp'
    Move-Item -LiteralPath 'models\yolo11s.tmp' -Destination 'models\yolo11s.pt'
}
& '.\.venv\Scripts\python.exe' prepare_models.py
if ($LASTEXITCODE) { throw 'Model preparation failed.' }
Write-Host 'Ready. Configure your ROI with configure_roi.py, then drag a video onto run_yolo.bat.'

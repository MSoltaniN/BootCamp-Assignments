# Provisions the Python environment for assignment 3.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\provision.ps1
#
# Safe to re-run.
#
# Two quirks of this machine/environment shape this script:
#
# 1) Windows long paths are disabled (MAX_PATH = 260). torch ships license files
#    under a ~140-character deep third_party tree, so a venv inside the long
#    assignment folder overflows and pip fails with WinError 206. The venv is
#    therefore created at the *workspace root* (`..\.venv-day3`, short path) and
#    linked into the project as `.venv` with a directory junction, so every
#    command in the docs (`.\\.venv\\Scripts\\python.exe`) still works.
#
# 2) Under the DSH file sandbox, a directory created by tempfile.mkdtemp() is not
#    writable by its creator, which breaks ensurepip/pip/huggingface_hub. So pip
#    runs through scripts\\sandbox_pip.py and TMP points inside the project.
#    On a normal machine both are harmless.

$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $PSScriptRoot
$parent = Split-Path -Parent $root
$venvHome = Join-Path $parent ".venv-day3"
$venvPy   = Join-Path $venvHome "Scripts\python.exe"
Set-Location $root

$tmp = Join-Path $parent ".tmp-day3\pip"
New-Item -ItemType Directory -Force $tmp | Out-Null
$env:TMP = $tmp
$env:TEMP = $tmp
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

if (-not (Test-Path $venvPy)) {
    Write-Host "[1/5] creating venv at $venvHome (short path, without bundled pip) ..."
    python -m venv --without-pip $venvHome
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
} else {
    Write-Host "[1/5] venv already exists: $venvHome"
}

if (-not (Test-Path (Join-Path $root ".venv"))) {
    Write-Host "      linking .venv -> $venvHome"
    cmd /c mklink /J "$root\.venv" "$venvHome" | Out-Null
}

if (-not (Test-Path (Join-Path $venvHome "Lib\site-packages\pip"))) {
    Write-Host "[2/5] bootstrapping pip ..."
    python scripts\sandbox_pip.py install --quiet --no-cache-dir --target (Join-Path $venvHome "Lib\site-packages") pip
    if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed" }
} else {
    Write-Host "[2/5] pip already present"
}

Write-Host "[3/5] installing pinned requirements (binary wheels only) ..."
& $venvPy scripts\sandbox_pip.py install --quiet --no-cache-dir --only-binary :all: --retries 5 --timeout 60 -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "requirements install failed" }

if (-not (Test-Path (Join-Path $venvHome "Scripts\jupyter.exe"))) {
    Write-Host "[4/5] installing jupyterlab ..."
    & $venvPy scripts\sandbox_pip.py install --quiet --no-cache-dir --only-binary :all: jupyterlab huggingface_hub
    if ($LASTEXITCODE -ne 0) { throw "jupyterlab install failed" }
} else {
    Write-Host "[4/5] jupyterlab already present"
}

Write-Host "[5/5] downloading + verifying the pinned embedding model ..."
& $venvPy scripts\sandbox_run.py scripts\download_model.py
if ($LASTEXITCODE -ne 0) { throw "embedding model download failed" }

Write-Host ""
Write-Host "environment ready. Next:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python scripts\check_env.py --encode"
Write-Host "  jupyter lab"

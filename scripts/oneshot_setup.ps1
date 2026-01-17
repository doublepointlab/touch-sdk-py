Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# One-shot setup you can run from *any* folder (Windows PowerShell):
# - ensures git + uv (best-effort via winget)
# - clones/updates this repo
# - creates .venv (Python 3.11)
# - installs this repo editable + example deps
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\oneshot_setup.ps1
#   $env:PYTHON_VERSION="3.11"; powershell -ExecutionPolicy Bypass -File .\scripts\oneshot_setup.ps1

function Refresh-Path {
  $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"
}

function Ensure-Command {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$WingetId,
    [Parameter(Mandatory = $true)][string]$InstallHint
  )

  if (Get-Command $Name -ErrorAction SilentlyContinue) { return }

  Write-Host "$Name not found; attempting install via winget..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install -e --id $WingetId --accept-package-agreements --accept-source-agreements | Out-Host
    Refresh-Path
  } else {
    throw "winget not found. $InstallHint"
  }

  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is still not available on PATH. Open a new PowerShell and rerun."
  }
}

Ensure-Command -Name "git" -WingetId "Git.Git" -InstallHint "Install Git manually and rerun."

$RepoUrl = "https://github.com/doublepointlab/touch-sdk-py.git"
$PythonVersion = if ($env:PYTHON_VERSION) { $env:PYTHON_VERSION } else { "3.11" }

# If we're already inside the repo, reuse it. Otherwise clone/update into ./touch-sdk-py.
$RepoDir = (& git rev-parse --show-toplevel 2>$null)
if (-not $RepoDir -or -not (Test-Path (Join-Path $RepoDir "pyproject.toml"))) {
  $BaseDir = (Get-Location).Path
  $TargetDir = Join-Path $BaseDir "touch-sdk-py"
  if (Test-Path (Join-Path $TargetDir ".git")) {
    Write-Host "Repo already exists at $TargetDir; updating..."
    git -C $TargetDir pull --ff-only | Out-Host
  } else {
    Write-Host "Cloning into $TargetDir..."
    git clone $RepoUrl $TargetDir | Out-Host
  }
  $RepoDir = $TargetDir
}

Set-Location $RepoDir
Write-Host "Repo root: $RepoDir"

Ensure-Command -Name "uv" -WingetId "Astral.uv" -InstallHint "Install uv manually and rerun."

$VenvDir = Join-Path $RepoDir ".venv"

# Keep uv-managed Python installs + uv cache inside the repo to avoid permission issues
$env:UV_PYTHON_INSTALL_DIR = (Join-Path $RepoDir ".uv-python")
$env:UV_CACHE_DIR = (Join-Path $RepoDir ".uv-cache")
New-Item -ItemType Directory -Force -Path $env:UV_PYTHON_INSTALL_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR | Out-Null

# Best-effort: ensure Python exists. (On Windows, this typically works fine.)
try {
  uv python install $PythonVersion | Out-Host
} catch {
  Write-Host ""
  Write-Host "Warning: 'uv python install $PythonVersion' failed. Continuing if an existing Python is available..."
  Write-Host ""
}

uv venv --python $PythonVersion --clear $VenvDir | Out-Host

$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

# Install this repo + example deps (uses the venv python explicitly)
uv pip install --python $VenvPy -e "$RepoDir[examples]" | Out-Host

# Use repo-local cache dirs (avoids matplotlib/fontconfig writing to $HOME)
$env:XDG_CACHE_HOME = (Join-Path $RepoDir ".cache")
$env:MPLCONFIGDIR = (Join-Path $RepoDir ".mplconfig")
New-Item -ItemType Directory -Force -Path $env:XDG_CACHE_HOME | Out-Null
New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR | Out-Null

& $VenvPy -c "import touch_sdk, inspect; print('touch_sdk from:', inspect.getfile(touch_sdk))"

Write-Host ""
Write-Host "Next steps (manual):"
Write-Host "  - Activate venv:"
Write-Host "      . $((Join-Path $VenvDir 'Scripts\Activate.ps1'))"
Write-Host "  - Run examples:"
Write-Host "      & $VenvPy $((Join-Path $RepoDir 'examples\basic.py'))"
Write-Host "      & $VenvPy $((Join-Path $RepoDir 'examples\osc_client_server.py'))"
Write-Host "  - Plotter (opens a matplotlib window; runs until you close it):"
Write-Host "      & $VenvPy $((Join-Path $RepoDir 'examples\plotter.py'))"


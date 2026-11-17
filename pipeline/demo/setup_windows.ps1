<#
.SYNOPSIS
  One-time setup of the demo laptop (Windows 10/11): a Python venv with what the viewer and the question box need,
  and the settings (instance, SSH key, videos folder) that run_demo.ps1 uses.

.DESCRIPTION
  Run from the repository folder (the folder that holds pipeline\):

    powershell -ExecutionPolicy Bypass -File pipeline\demo\setup_windows.ps1 -Instance ubuntu@1.2.3.4 `
        -Key C:\keys\demo.pem -Media D:\demo\videos

  -Instance    user@address of the GPU instance (ec2_model_server.sh prints it)
  -Key         the instance's SSH private key (.pem). Its permissions are narrowed to you (Windows OpenSSH refuses
               a key other users can read)
  -Media       the folder holding the lecture videos L01.mp4 ... (optional: lectures without a file play from YouTube)
  -LocalEmbed  embed the questions on this laptop's CPU instead of on the instance (installs torch CPU and
               sentence-transformers, ~1 GB, and downloads the 1.2 GB embedding model at the first start)
  -Venv        where the venv goes (default: %USERPROFILE%\mtp-demo-venv)

  Safe to rerun. Needs Python 3.11 or newer (3.12 recommended: winget install -e --id Python.Python.3.12) and the
  OpenSSH client (built into Windows 10 1809 and later).
#>
param(
  [string]$Instance = "",
  [string]$Key = "",
  [string]$Media = "",
  [switch]$LocalEmbed,
  [string]$Venv = (Join-Path $env:USERPROFILE "mtp-demo-venv")
)
$ErrorActionPreference = "Continue"   # native commands report through $LASTEXITCODE (checked below)
$Pipeline = Split-Path -Parent $PSScriptRoot

function Say($text) { Write-Host $text }
function Stop-Setup($text) { Write-Host "STOP: $text" -ForegroundColor Red; exit 1 }

# 1. Python 3.11 or newer --------------------------------------------------------------------------------------
Say "== 1/5 Python"
$found = $null
foreach ($cand in @("py -3.12", "py -3.13", "py -3.11", "py -3", "python", "python3")) {
  $parts = $cand.Split(" ")
  $exe = $parts[0]
  $rest = @($parts | Select-Object -Skip 1)
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
  try {
    $v = (& $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null | Out-String).Trim()
  } catch { continue }
  if ($LASTEXITCODE -eq 0 -and $v -match '^\d+\.\d+$' -and ([version]$v -ge [version]"3.11")) {
    $found = @{ exe = $exe; rest = $rest; version = $v }
    break
  }
}
if (-not $found) {
  Stop-Setup "no Python 3.11 or newer. Install it: winget install -e --id Python.Python.3.12 (then open a new terminal)"
}
Say "  Python $($found.version) ($($found.exe) $($found.rest -join ' '))"

# 2. venv and packages -----------------------------------------------------------------------------------------
Say "== 2/5 venv $Venv"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
  & $found.exe @($found.rest) -m venv $Venv
  if ($LASTEXITCODE -ne 0) { Stop-Setup "could not create the venv" }
}
& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q -r (Join-Path $PSScriptRoot "requirements-local.txt")
if ($LASTEXITCODE -ne 0) { Stop-Setup "pip install -r requirements-local.txt failed" }
if ($LocalEmbed) {
  Say "  installing the local embedder (torch CPU, sentence-transformers: a few minutes)"
  & $Py -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
  & $Py -m pip install -q -r (Join-Path $PSScriptRoot "requirements-local-embed.txt")
  if ($LASTEXITCODE -ne 0) { Stop-Setup "pip install -r requirements-local-embed.txt failed" }
}

# 3. the SSH client --------------------------------------------------------------------------------------------
Say "== 3/5 OpenSSH client"
$ssh = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $ssh) {
  Stop-Setup ("no ssh. Install the OpenSSH client (PowerShell as administrator): " +
              "Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0")
}
Say "  $($ssh.Source)"

# 4. the key: readable by this user only (else ssh says UNPROTECTED PRIVATE KEY FILE and ignores it) --------
Say "== 4/5 SSH key"
if ($Key) {
  if (-not (Test-Path $Key)) { Stop-Setup "no key file $Key" }
  $Key = (Resolve-Path $Key).Path
  & icacls $Key /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null
  Say "  $Key (now readable by $($env:USERNAME) only)"
} else {
  Say "  none given (ssh then uses your default key, e.g. %USERPROFILE%\.ssh\id_ed25519, or ~/.ssh/config)"
}

# 5. settings and checks (in Python: python -m demo setup) -------------------------------------------------
Say "== 5/5 settings"
$a = @("-m", "demo", "setup")
if ($Instance) { $a += @("--instance", $Instance) }
if ($Key) { $a += @("--key", $Key) }
if ($Media) { $a += @("--media", $Media) }
if ($LocalEmbed) { $a += "--local-embed" }
$env:PYTHONUTF8 = "1"
Push-Location $Pipeline
try { & $Py @a; $code = $LASTEXITCODE } finally { Pop-Location }
if ($code -ne 0) { Stop-Setup "the checks above found a problem" }
Say ""
Say "Done. Start the demo with:  powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1"

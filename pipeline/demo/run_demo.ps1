<#
.SYNOPSIS
  Start the demo on the laptop: the SSH tunnel to the GPU instance, the viewer, the browser.

.DESCRIPTION
  Run from the repository folder, after setup_windows.ps1 (whose settings it uses; a parameter given here wins):

    powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1
    powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1 -Instance ubuntu@1.2.3.4 -Key C:\keys\demo.pem

  -Check       instead of starting: check a running demo (another window): tunnel, model, embedder vectors,
               viewer routes, one question with its timings
  -Bench       instead of starting: time the DEMO_PLAN questions through the running demo
  -Push        instead of starting: copy the instance's files to it and run ec2_model_server.sh there
               (-Engine llamacpp or vllm; asks when not given)
  -Port        the viewer's port on this laptop (default 8765; the next free one is used when it is taken)

  Ctrl+C in this window stops the viewer and the tunnel. The instance keeps serving the model: stop it there
  (bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --stop) and stop the instance in the AWS console.
#>
param(
  [string]$Instance = "",
  [string]$Key = "",
  [string]$Media = "",
  [int]$Port = 8765,
  [switch]$LocalEmbed,
  [switch]$NoBrowser,
  [switch]$Check,
  [switch]$Bench,
  [switch]$Push,
  [string]$Engine = "",
  [string]$Venv = (Join-Path $env:USERPROFILE "mtp-demo-venv")
)
$ErrorActionPreference = "Continue"   # native commands report through $LASTEXITCODE (checked below)
$Pipeline = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
  Write-Host "STOP: no venv at $Venv. Run first: powershell -ExecutionPolicy Bypass -File pipeline\demo\setup_windows.ps1" -ForegroundColor Red
  exit 1
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if ($Check) { $a = @("-m", "demo", "check", "--url", "http://127.0.0.1:$Port") }
elseif ($Bench) { $a = @("-m", "demo", "bench", "--url", "http://127.0.0.1:$Port", "--warmup") }
elseif ($Push) {
  $a = @("-m", "demo", "push")
  if ($Engine) { $a += @("--engine", $Engine) }
}
else {
  $a = @("-m", "demo", "run", "--port", "$Port")
  if ($Media) { $a += @("--media", $Media) }
  if ($NoBrowser) { $a += "--no-browser" }
}
if (-not $Bench) {
  if ($Instance) { $a += @("--instance", $Instance) }
  if ($Key) { $a += @("--key", $Key) }
  if ($LocalEmbed) { $a += "--local-embed" }
}
Push-Location $Pipeline
try { & $Py @a; $code = $LASTEXITCODE } finally { Pop-Location }
exit $code

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$config = Get-Content -LiteralPath (Join-Path $root '.local/runtime.json') -Raw | ConvertFrom-Json
foreach ($port in @(8000,5173)) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port occupied; no existing process will be stopped" }
}
$python = Join-Path $root 'backend/.venv/Scripts/python.exe'
$local = Join-Path $root '.local'
function Start-Api([string]$suffix) {
  Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $local "health-$suffix.out.log") -RedirectStandardError (Join-Path $local "health-$suffix.err.log")
}
function Wait-Health([string]$url) {
  $end = [DateTime]::UtcNow.AddSeconds(15)
  do {
    try { $data = Invoke-RestMethod -Uri $url -TimeoutSec 2; if($data.status -eq 'ok' -and $data.scope -eq 'api_process') { return $data } } catch { }
    Start-Sleep -Milliseconds 200
  } while ([DateTime]::UtcNow -lt $end)
  throw "Health check did not pass: $url"
}
function Stop-OwnedProcess($process) {
  if ($process -and !$process.HasExited) {
    # PID is returned by Start-Process in this script, never inferred from the port.
    & taskkill.exe /PID $process.Id /T /F | Out-Null
  }
}
$api = $null
$frontend = $null
try {
  $api = Start-Api 'first'
  $first = Wait-Health 'http://127.0.0.1:8000/health'
  $frontend = Start-Process -FilePath $config.node -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $local 'health-vite.out.log') -RedirectStandardError (Join-Path $local 'health-vite.err.log')
  $proxy = Wait-Health 'http://127.0.0.1:5173/api/health'
  Stop-OwnedProcess $api
  $api = $null
  $api = Start-Api 'restarted'
  $restart = Wait-Health 'http://127.0.0.1:8000/health'
  [pscustomobject]@{ checkedAt=[DateTime]::UtcNow.ToString('o'); direct=$first; frontendProxy=$proxy; afterRestart=$restart; ports=@(8000,5173); servicesStoppedOnExit=$true } | ConvertTo-Json -Depth 4
} finally {
  Stop-OwnedProcess $frontend
  Stop-OwnedProcess $api
}

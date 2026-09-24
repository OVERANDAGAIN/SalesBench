param(
  [ValidateSet('install','init-db','migrate','test','serve','recover','demo','create-manual','inspect','metrics','pg-start','pg-stop','pg-status')]
  [string]$Task = 'test',
  [string]$SessionId,
  [int]$Port = 8000,
  [ValidateSet('json','csv')][string]$Format = 'json',
  [string]$OutDir
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if ($OutDir) { $OutDir = [IO.Path]::GetFullPath($OutDir) }
$runtime = Get-Content -LiteralPath (Join-Path $root '.local/runtime.json') -Raw | ConvertFrom-Json
$platform = Get-Content -LiteralPath (Join-Path $root '.local/platform.json') -Raw | ConvertFrom-Json
$env:UV_CACHE_DIR = Join-Path $runtime.cache 'uv'
$env:UV_PYTHON_DOWNLOADS = 'never'
$env:PYTHONUTF8 = '1'
$env:SALESBENCH_DATABASE_URL = $platform.database_url
$env:SALESBENCH_ADMIN_TOKEN = $platform.admin_token

if ($Task -in @('pg-start','pg-stop','pg-status')) {
  if (!(Test-Path -LiteralPath (Join-Path $platform.pg_data 'PG_VERSION'))) { throw 'Configured PostgreSQL data directory is not initialized' }
  $pgCtl = Join-Path $platform.pg_bin 'pg_ctl.exe'
  if ($Task -eq 'pg-status') { & $pgCtl -D $platform.pg_data status; exit $LASTEXITCODE }
  $pgArgs = if ($Task -eq 'pg-start') { @('-D', $platform.pg_data, '-l', $platform.pg_log, '-w', 'start') } else { @('-D', $platform.pg_data, '-m', 'fast', '-w', 'stop') }
  # WaitForExit waits for pg_ctl itself; Start-Process -Wait also waits for the server child.
  $process = Start-Process -FilePath $pgCtl -ArgumentList $pgArgs -WindowStyle Hidden -PassThru
  $process.WaitForExit()
  exit $process.ExitCode
}

Push-Location (Join-Path $root 'backend')
try {
  switch ($Task) {
    'install' { & $runtime.uv sync --locked --python $runtime.python }
    'init-db' { & $runtime.uv run --locked --python $runtime.python python -m app.cli init-db }
    'migrate' { & $runtime.uv run --locked --python $runtime.python alembic upgrade head }
    'test' { $env:SALESBENCH_TEST_DATABASE_URL = $platform.database_url; & $runtime.uv run --locked --python $runtime.python pytest -q }
    'serve' { & $runtime.uv run --locked --python $runtime.python uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1 }
    'recover' { if (!$SessionId) { throw 'recover requires -SessionId' }; & $runtime.uv run --locked --python $runtime.python python -m app.cli recover --session-id $SessionId }
    'demo' { & $runtime.uv run --locked --python $runtime.python python -m app.cli demo }
    'create-manual' { & $runtime.uv run --locked --python $runtime.python python -m app.cli create-manual }
    'inspect' { if (!$SessionId) { throw 'inspect requires -SessionId' }; & $runtime.uv run --locked --python $runtime.python python -m app.cli inspect --session-id $SessionId }
    'metrics' {
      if (!$SessionId) { throw 'metrics requires -SessionId' }
      $metricArgs = @('--session-id',$SessionId,'--format',$Format)
      if ($OutDir) { $metricArgs += @('--out-dir',$OutDir) }
      & $runtime.uv run --locked --python $runtime.python python -m app.cli metrics @metricArgs
    }
  }
  $taskExit = $LASTEXITCODE
} finally { Pop-Location }
exit $taskExit

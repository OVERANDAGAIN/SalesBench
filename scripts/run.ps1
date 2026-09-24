param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('check','install-frontend','install-backend','frontend','backend','typecheck','build','test-frontend','test-backend','test-browser','test-preview','test-market','preview')]
  [string]$Task,
  [string]$EvidenceDir
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if ($EvidenceDir -and $Task -notin @('check','test-browser','test-preview','test-market')) { throw '-EvidenceDir is only for browser verification or check' }
if ($EvidenceDir) { $EvidenceDir = [IO.Path]::GetFullPath($EvidenceDir, $root) }
if ($Task -eq 'check') {
  # PostgreSQL must already be started/migrated. Fail fast; never install or replace tools.
  # test-market owns its API/preview, and restarts the configured development PG.
  $checks = @(
    @('engine.ps1','test'), @('platform.ps1','test'), @('run.ps1','typecheck'),
    @('run.ps1','test-frontend'), @('run.ps1','build'), @('run.ps1','test-preview'),
    @('run.ps1','test-market'), @('run.ps1','test-browser')
  )
  foreach ($check in $checks) {
    Write-Output "Checking $($check[0]) $($check[1])"
    $checkArgs = @('-NoProfile','-File',(Join-Path $PSScriptRoot $check[0]),$check[1])
    if ($EvidenceDir -and $check[1] -in @('test-preview','test-market')) { $checkArgs += @('-EvidenceDir',$EvidenceDir) }
    if ($check[1] -eq 'test-browser') { $env:SALESBENCH_EVIDENCE_DIR = $null }
    & (Get-Process -Id $PID).Path @checkArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
  Write-Output 'PASS complete system regression (Engine, Runner, PostgreSQL, Vue, real market, legacy UI)'
  exit 0
}
if ($EvidenceDir) { $env:SALESBENCH_EVIDENCE_DIR = $EvidenceDir }
$configPath = Join-Path $root '.local/runtime.json'
$config = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } else { $null }
function Resolve-Tool([string]$name) {
  if ($config -and $config.$name) { return $config.$name }
  $command = Get-Command $name -ErrorAction SilentlyContinue
  if (!$command) { throw "Missing $name; see docs/ENVIRONMENT.md and .local/runtime.json" }
  if ($name -eq 'python' -and $command.Source -match 'WindowsApps') { throw 'Select a real Python 3.12 interpreter in .local/runtime.json' }
  return $command.Source
}
$cache = if ($config -and $config.cache) { $config.cache } elseif ($env:SALESBENCH_CACHE) { $env:SALESBENCH_CACHE } else { Join-Path $root '.local/cache' }
$env:SALESBENCH_PNPM_STORE = Join-Path $cache 'pnpm-home/store'
$env:SALESBENCH_PNPM_CACHE = Join-Path $cache 'pnpm-cache'
$env:pnpm_config_store_dir = $env:SALESBENCH_PNPM_STORE
$env:pnpm_config_cache_dir = $env:SALESBENCH_PNPM_CACHE
$env:pnpm_config_state_dir = Join-Path $cache 'pnpm-state'
$env:UV_CACHE_DIR = Join-Path $cache 'uv'
$env:UV_PYTHON_DOWNLOADS = 'never'
$env:PNPM_HOME = Join-Path $cache 'pnpm-home'
if ($Task -in @('backend','install-backend','test-backend')) {
  $platformPath = Join-Path $root '.local/platform.json'
  if (Test-Path -LiteralPath $platformPath) {
    $platform = Get-Content -LiteralPath $platformPath -Raw | ConvertFrom-Json
    $env:SALESBENCH_DATABASE_URL = $platform.database_url
    $env:SALESBENCH_ADMIN_TOKEN = $platform.admin_token
    if ($Task -eq 'test-backend') { $env:SALESBENCH_TEST_DATABASE_URL = $platform.database_url }
  }
  $uv = Resolve-Tool 'uv'
  $python = Resolve-Tool 'python'
  Push-Location (Join-Path $root 'backend')
  try {
    switch ($Task) {
      'install-backend' { & $uv sync --locked --python $python }
      'backend' { & $uv run --locked --python $python uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 }
      'test-backend' { & $uv run --locked --python $python pytest -q }
    }
    $code = $LASTEXITCODE
  } finally { Pop-Location }
} else {
  $node = Resolve-Tool 'node'
  $pnpm = Resolve-Tool 'pnpm'
  # This process only; never changes the user's or machine's global PATH.
  $env:PATH = (Split-Path $node -Parent) + [IO.Path]::PathSeparator + $env:PATH
  $argsForPnpm = switch ($Task) {
    'install-frontend' { @('install','--frozen-lockfile') }
    'frontend' { @('run','dev') }
    'typecheck' { @('run','typecheck') }
    'build' { @('run','build') }
    'test-frontend' { @('run','test') }
    'test-browser' { @('run','test:browser') }
    'test-preview' { @('run','test:preview') }
    'test-market' { @('run','test:market') }
    'preview' { @('run','preview') }
  }
  Push-Location (Join-Path $root 'frontend')
  try {
    if ($pnpm -match '\.[cm]?js$') { & $node $pnpm @argsForPnpm } else { & $pnpm @argsForPnpm }
    $code = $LASTEXITCODE
  } finally { Pop-Location }
}
exit $code

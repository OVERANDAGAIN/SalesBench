param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('install-frontend','install-backend','frontend','backend','typecheck','build','test-frontend','test-backend','preview')]
  [string]$Task
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
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
$env:SALESBENCH_PNPM_STORE = Join-Path $cache 'pnpm-store'
$env:SALESBENCH_PNPM_CACHE = Join-Path $cache 'pnpm-cache'
$env:UV_CACHE_DIR = Join-Path $cache 'uv'
$env:UV_PYTHON_DOWNLOADS = 'never'
$env:PNPM_HOME = Join-Path $cache 'pnpm-home'
if ($Task -in @('backend','install-backend','test-backend')) {
  $uv = Resolve-Tool 'uv'
  $python = Resolve-Tool 'python'
  Push-Location (Join-Path $root 'backend')
  try {
    switch ($Task) {
      'install-backend' { & $uv sync --locked --python $python }
      'backend' { & $uv run --locked --python $python uvicorn app.main:app --host 127.0.0.1 --port 8000 }
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
    'preview' { @('run','preview') }
  }
  Push-Location (Join-Path $root 'frontend')
  try {
    if ($pnpm -match '\.[cm]?js$') { & $node $pnpm @argsForPnpm } else { & $pnpm @argsForPnpm }
    $code = $LASTEXITCODE
  } finally { Pop-Location }
}
exit $code

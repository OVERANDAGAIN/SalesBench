param(
  [ValidateSet('install','test','demo','build')]
  [string]$Task = 'test',
  [int]$Seed = 7
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $root '.local/runtime.json'
$config = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } else { $null }
function Resolve-EngineTool([string]$name) {
  if ($config -and $config.$name) { return $config.$name }
  $command = Get-Command $name -ErrorAction SilentlyContinue
  if (!$command -or ($name -eq 'python' -and $command.Source -match 'WindowsApps')) {
    throw "Configure a real $name in .local/runtime.json; see docs/ENVIRONMENT.md"
  }
  return $command.Source
}
$uv = Resolve-EngineTool 'uv'
$python = Resolve-EngineTool 'python'
$cache = if ($config -and $config.cache) { $config.cache } else { Join-Path $root '.local/cache' }
$env:UV_CACHE_DIR = Join-Path $cache 'uv'
$env:UV_PYTHON_DOWNLOADS = 'never'
Push-Location (Join-Path $root 'engine')
try {
  switch ($Task) {
    'install' { & $uv sync --locked --python $python }
    'test' { & $uv run --locked --python $python python -m unittest discover -s tests -v }
    'demo' { & $uv run --locked --python $python python -m salesbench_engine.scenario --seed $Seed }
    'build' { & $uv build --python $python }
  }
  $code = $LASTEXITCODE
} finally { Pop-Location }
exit $code

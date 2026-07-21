param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
if ($CliArgs.Count -gt 0) {
  python -m climate_agent.cli @CliArgs
  exit $LASTEXITCODE
}
python -m climate_agent.cli init
python -m climate_agent.cli serve --host 127.0.0.1 --port 8765

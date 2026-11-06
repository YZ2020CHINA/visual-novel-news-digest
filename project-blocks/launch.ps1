$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$runtimePython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $runtimePython) {
    & $runtimePython (Join-Path $PSScriptRoot 'start.py')
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 (Join-Path $PSScriptRoot 'start.py')
} else {
    python (Join-Path $PSScriptRoot 'start.py')
}

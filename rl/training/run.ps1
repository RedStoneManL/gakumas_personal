# Development launcher. It does not install packages or alter either environment.
$ErrorActionPreference = 'Stop'
$trainingRoot = $PSScriptRoot
$workspaceRoot = (Get-Item -LiteralPath $trainingRoot).Parent.Parent.FullName
$trainingPython = Join-Path $trainingRoot '.venv\Scripts\python.exe'
$entryScript = Join-Path $trainingRoot 'scripts\local_entry.py'

if (Test-Path -LiteralPath $trainingPython) {
    & $trainingPython -B -X utf8 $entryScript -- @args
} else {
    $arenaPython = Join-Path $workspaceRoot 'third_party\gakumas_arena\.venv\Scripts\python.exe'
    $torchPackages = Join-Path $workspaceRoot 'rl\round2\.venv\Lib\site-packages'
    if (-not (Test-Path -LiteralPath $arenaPython)) {
        throw 'No training/.venv or Arena Python environment found. Follow README.md to create an independent environment.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $torchPackages 'torch'))) {
        throw 'The existing PyTorch dependency was not found. Follow README.md to install dependencies into training/.venv.'
    }
    & $arenaPython -B -X utf8 $entryScript --extra-site-packages $torchPackages -- @args
}
exit $LASTEXITCODE

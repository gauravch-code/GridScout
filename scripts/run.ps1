param([ValidateSet('setup','demo','data','app','test','sources','memos')][string]$Task='app')
$ErrorActionPreference = 'Stop'
$GridScoutRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $GridScoutRoot
$GridScoutPython = Join-Path $GridScoutRoot '.venv/Scripts/python.exe'
if ($Task -eq 'setup') {
    if (-not (Test-Path -LiteralPath $GridScoutPython)) { python -m venv .venv }
    & $GridScoutPython -m pip install -r requirements.txt
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath $GridScoutPython)) { throw 'Run ./scripts/run.ps1 setup first.' }
switch ($Task) {
    'demo' { & $GridScoutPython -m gridscout demo }
    'data' {
        & $GridScoutPython -m gridscout pipeline --download
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $GridScoutPython -m gridscout features
    }
    'app' { & $GridScoutPython -m streamlit run app.py }
    'test' { & $GridScoutPython -m pytest -q }
    'sources' { & $GridScoutPython -m gridscout verify-sources }
    'memos' { & $GridScoutPython -m gridscout memos --top 3 }
}
exit $LASTEXITCODE

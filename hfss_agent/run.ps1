param(
    [string]$Script = "smoke_test.py",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArguments
)
$ErrorActionPreference = 'Stop'

# Repo root is the parent of this script (pyproject.toml, uv.lock, .venv live there).
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Uv = 'E:\uv\uv.exe'
if (-not (Test-Path $Uv)) { $Uv = 'uv' }

$env:UV_CACHE_DIR = Join-Path $RepoRoot '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $RepoRoot '.python'
$env:PYAEDT_USE_PRE_GRPC_ARGS = 'True'
$env:ANSYSEMSV_ROOT252 = 'E:\Program Files\ANSYS Student\v252\AnsysEM'

# Resolve a bare script name (e.g. smoke_test.py) inside hfss_agent first.
if (-not [System.IO.Path]::IsPathRooted($Script)) {
    $Candidate = Join-Path $PSScriptRoot $Script
    if (Test-Path $Candidate) { $Script = $Candidate }
}

Push-Location $RepoRoot
try {
    & $Uv run --locked --project $RepoRoot python $Script @ScriptArguments
    $scriptExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $scriptExitCode

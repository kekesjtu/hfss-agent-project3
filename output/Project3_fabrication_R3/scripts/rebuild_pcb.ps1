param(
    [string]$BuildDirectory = '',
    [string]$KiCadBin = 'E:\Program Files\KiCad\10.0\bin'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
if (-not $BuildDirectory) {
    $BuildDirectory = Join-Path $repoRoot ('tmp/' + (Get-Date -Format 'yyyy-MM-dd') + '-r3-pcb/' + (Get-Date -Format 'HHmmss_ffff'))
}
$buildPath = [IO.Path]::GetFullPath($BuildDirectory)
$tmpRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'tmp'))
if (-not $buildPath.StartsWith($tmpRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'BuildDirectory must be a task subdirectory under this repository tmp/.'
}
if (Test-Path -LiteralPath $buildPath) { throw 'BuildDirectory must not exist.' }
$python = Join-Path $repoRoot '.venv/Scripts/python.exe'
$kicadPython = Join-Path $KiCadBin 'python.exe'
$cli = Join-Path $KiCadBin 'kicad-cli.exe'
foreach ($exe in @($python, $kicadPython, $cli)) {
    if (-not (Test-Path -LiteralPath $exe)) { throw "Missing executable: $exe" }
}
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
$previousBuild = $env:PROJECT3_BUILD_DIR
$env:PROJECT3_BUILD_DIR = $buildPath
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed with exit code $LASTEXITCODE" }
}
Push-Location -LiteralPath $buildPath
try {
    Invoke-Checked $kicadPython @((Join-Path $PSScriptRoot 'build_pcb.py'), '--revision', 'R3', '--extension', '12.26', '--match-width', '3', '--launch-match-width', '1.276', '--launch-match-length', '5.266')
    $board = Join-Path $buildPath 'Project3_array_R3.kicad_pcb'
    Invoke-Checked $cli @('pcb','drc','--refill-zones','--save-board','--format','json','--exit-code-violations','-o',"$buildPath/drc.json",$board)
    Invoke-Checked $cli @('pcb','export','gerbers','-o',"$buildPath/Gerber/",'-l','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts','--disable-aperture-macros',$board)
    Invoke-Checked $cli @('pcb','export','drill','--format','excellon','--excellon-units','mm','-o',"$buildPath/Gerber/",$board)
    Invoke-Checked $cli @('pcb','export','pos','--format','csv','--units','mm','-o',"$buildPath/placement.csv",$board)
    Invoke-Checked $cli @('pcb','export','ipcd356','-o',"$buildPath/Project3_array_R3.ipc",$board)
    Invoke-Checked $cli @('pcb','export','step','--board-only','--cut-vias-in-body','--force','-o',"$buildPath/board_mechanical.step",$board)
    Invoke-Checked $cli @('pcb','export','step','--cut-vias-in-body','--force','-o',"$buildPath/assembly.step",$board)
    Invoke-Checked $kicadPython @((Join-Path $PSScriptRoot 'check_vendor_footprint.py'),'R3')
    Invoke-Checked $kicadPython @((Join-Path $PSScriptRoot 'export_native.py'),'R3')
    & $cli pcb drc --format json --exit-code-violations -o "$buildPath/diagnostics/edge_rule_negative_control.json" "$buildPath/diagnostics/Project3_array_R3.kicad_pcb"
    if ($LASTEXITCODE -eq 0) { throw 'Negative control unexpectedly passed.' }
    Invoke-Checked $python @((Join-Path $PSScriptRoot 'check_cam.py'),'R3')
    Invoke-Checked $python @((Join-Path $PSScriptRoot 'register_hfss_copper.py'),(Join-Path $PSScriptRoot '../HFSS_full_SMA'),'R3')
    Invoke-Checked $python @((Join-Path $PSScriptRoot 'package_gerber.py'),$buildPath)
    Write-Output "BUILD=$buildPath"
} finally {
    Pop-Location
    $env:PROJECT3_BUILD_DIR = $previousBuild
}

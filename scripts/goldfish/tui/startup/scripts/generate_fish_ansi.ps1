param(
    [string]$SourceImage = "assets\fish.png",
    [string]$Output = "internal\art\fish.ansi",
    [string]$Symbols = "vhalf",
    [string]$Size = "64x24",
    [switch]$BraillePreview
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$inputPath = if ([System.IO.Path]::IsPathRooted($SourceImage)) { $SourceImage } else { Join-Path $projectRoot $SourceImage }
$outputPath = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $projectRoot $Output }
$outputDir = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$chafa = Get-Command chafa -ErrorAction SilentlyContinue
if (-not $chafa) {
    $chafa = Get-ChildItem -Path $env:LOCALAPPDATA\Microsoft\WinGet\Packages -Recurse -Filter Chafa.exe -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $chafa) {
    throw "chafa is not installed or not discoverable. Install it with: winget install --id hpjansson.Chafa"
}

$chafaPath = if ($chafa.Source) { $chafa.Source } else { $chafa.FullName }

function Invoke-ChafaToFile {
    param(
        [string]$SymbolsArg,
        [string]$SizeArg,
        [string]$TargetPath
    )

    $rawPath = "$TargetPath.raw"
    $cmd = '"' + $chafaPath + '" -f symbols --colors=full --relative=off --symbols=' + $SymbolsArg + ' --size=' + $SizeArg + ' "' + $inputPath + '" > "' + $rawPath + '"'
    cmd /c $cmd
    if ($LASTEXITCODE -ne 0) {
        throw "chafa failed with exit code $LASTEXITCODE"
    }

    $cleaner = @"
from pathlib import Path
import re

raw = Path(r"$rawPath")
target = Path(r"$TargetPath")
data = raw.read_bytes()
data = data.replace(b"\xef\xbb\xbf", b"")
data = data.replace(b"\x1b[?25l", b"")
data = data.replace(b"\x1b[?25h", b"")
data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

# Keep SGR color sequences, but remove cursor movement and terminal-control
# sequences that would disturb Bubble Tea layout.
data = re.sub(rb"\x1b\[[0-9;?]*[A-HJKSTfhlnsu]", b"", data)
target.write_bytes(data.rstrip() + b"\n")
raw.unlink(missing_ok=True)
"@
    $cleaner | python -
}

Invoke-ChafaToFile -SymbolsArg $Symbols -SizeArg $Size -TargetPath $outputPath

if ($BraillePreview) {
    $brailleOutput = Join-Path $outputDir "fish.braille.ansi"
    Invoke-ChafaToFile -SymbolsArg "braille" -SizeArg "70x28" -TargetPath $brailleOutput
    Write-Output "braille preview: $brailleOutput"
}

Write-Output "fish ansi: $outputPath"

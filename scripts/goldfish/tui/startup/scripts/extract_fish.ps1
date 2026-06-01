param(
    [string]$Source = "C:\Users\59521\Desktop\ed553656-4a89-40b5-baad-8f41c125ea4f.png",
    [string]$Output = "assets\fish.png"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputPath = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $projectRoot $Output }
$outputDir = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$python = @"
from PIL import Image
from pathlib import Path

source = Path(r"$Source")
output = Path(r"$outputPath")

if not source.exists():
    raise SystemExit(f"source image not found: {source}")

image = Image.open(source).convert("RGB")

# Crop only the fish artwork region from the reference image.
# Includes fish body, bubbles, seaweed, rocks, and ground shadow.
# Excludes logo, tagline, welcome text, panels, borders, and command bar.
left, top, right, bottom = 90, 180, 820, 500
crop = image.crop((left, top, right, bottom))
crop.save(output)
print(output)
"@

$python | python -

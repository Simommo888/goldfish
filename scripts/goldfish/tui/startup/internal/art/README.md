# Goldfish Fish Artwork Pipeline

This subsystem handles only the fish artwork used by the Goldfish CLI startup hero panel.

It does not render the whole dashboard image, rasterize UI text, or replace the Bubble Tea layout.

## Directory Structure

```text
scripts/goldfish/tui/startup/
  assets/
    fish.png
  scripts/
    extract_fish.ps1
    generate_fish_ansi.ps1
  internal/art/
    fish.ansi
    fish.braille.ansi
    fish.go
    README.md
```

## Extraction Workflow

`assets/fish.png` is cropped from the reference design and contains only:

- fish body
- bubbles
- seaweed
- rocks and underwater decoration

It excludes:

- logo
- text
- status panels
- sessions
- tools
- tips
- borders

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/extract_fish.ps1
```

## ANSI Generation

Primary Chafa output:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate_fish_ansi.ps1
```

This generates:

```text
internal/art/fish.ansi
```

The script uses the equivalent of:

```powershell
chafa -f symbols --colors=full --relative=off --symbols=vhalf --size=64x24 assets/fish.png
```

To compare braille output:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate_fish_ansi.ps1 -BraillePreview
```

This generates:

```text
internal/art/fish.braille.ansi
```

## Go Embed

`fish.go` embeds `fish.ansi`:

```go
package art

import _ "embed"

//go:embed fish.ansi
var Fish string
```

## Hero Panel Integration

The startup renderer imports the embedded artwork:

```go
import "goldfish/startup/internal/art"
```

The hero panel keeps real text for the logo, tagline, and welcome message, and inserts only the fish artwork from `art.Fish`:

```go
welcome := center(orange.Render(". +")+" "+cyan.Render("welcome to your intelligence companion")+" "+orange.Render("+ ."), w)
lines = append(lines, fishArtwork(w, max(0, h-len(lines)-1))...)
lines = append(lines, welcome)
```

`fishArtwork` falls back to handcrafted Unicode art if the embedded ANSI file is empty.

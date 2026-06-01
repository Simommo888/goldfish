package art

import _ "embed"

// Fish is the terminal-native ANSI TrueColor fish artwork generated from
// assets/fish.png with Chafa. It intentionally contains only the fish scene:
// fish body, bubbles, seaweed, rocks, and underwater decoration.
//
// Regenerate with:
// powershell -ExecutionPolicy Bypass -File scripts/generate_fish_ansi.ps1
//
//go:embed fish.ansi
var Fish string

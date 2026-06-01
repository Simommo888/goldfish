# goldfish Terminal-Native Startup UI Spec

This page defines the default `goldfish` startup screen for the Python conversation entrypoint.

The primary implementation is a Go Bubble Tea / Lip Gloss renderer. It preserves the supplied reference layout while rendering every visible element as terminal-native UI: Unicode box drawing, Unicode block characters, ANSI TrueColor, and real text.

It must not render a screenshot, convert a PNG to ANSI, rasterize text, depend on emoji-width glyphs, or use Kitty/Sixel/image protocols.

## layout

- Minimum terminal size: `150 columns x 42 rows`.
- Ideal terminal size: `160 columns x 45 rows`.
- Outer frame: full screen border.
- Top area: large left hero region and right status/session column.
- Hero area: roughly 60% width.
- Right column: roughly 40% width.
- Bottom area: three panels in one row.
- Footer: horizontal separator and `gf >` prompt.

## composition

- Left hero panel:
  - large `goldfish` block logo
  - `small agent, sharp memory`
  - handcrafted Unicode block goldfish
  - bubbles, seaweed, rocks
  - `. + welcome to your intelligence companion + .`
- Right top panel: `STATUS`
- Right middle panel: `RECENT SESSIONS`
- Bottom left panel: `QUICK START`
- Bottom middle panel: `AVAILABLE TOOLS`
- Bottom right panel: `TIPS`
- Footer command prompt: `gf >`

## colors

- Background: `#02070a`
- Border gray: `#5d6264`
- Dim border/shadow: `#33393b`
- Orange primary: `#ff941f`
- Orange soft: `#ffb35a`
- Cream text: `#f1e5d0`
- Aqua text: `#8eeeff`
- Green ready/commands: `#73d86b`
- Muted text: `#8a8f92`
- Plant green: `#6f9a35`
- Rock brown: `#6d5b3e`
- Fish highlight: `#ffe1a0`

## typography

- The `goldfish` wordmark is terminal block text.
- Section titles are uppercase and orange.
- Commands and ready values are green.
- Body text is cream/white.
- Secondary guidance is cyan.
- Borders use Unicode box drawing.

## component tree

```text
PythonChatStartup
|-- GoNativeRenderer(Bubble Tea + Lip Gloss)
|   |-- OuterFrame
|   |-- TopArea
|   |   |-- HeroPanel
|   |   `-- RightColumn
|   |       |-- StatusPanel
|   |       `-- RecentSessionsPanel
|   |-- BottomArea
|   |   |-- QuickStartPanel
|   |   |-- AvailableToolsPanel
|   |   `-- TipsPanel
|   `-- FooterPrompt
`-- PythonAnsiFallback
```

## implementation rules

- Keep Python startup orchestration in `scripts/goldfish/modules/startup_page.py`.
- Keep the Go native renderer in `scripts/goldfish/tui/startup`.
- Build the renderer to `scripts/goldfish/output_cache/bin/goldfish-startup.exe`.
- The Go renderer supports resize through Bubble Tea.
- The Python entrypoint calls the Go renderer in `--once` mode for startup.
- Non-interactive scripts and tests use Python ANSI fallback.
- Do not use Bubble Tea to redesign the page into a different Hermes layout.
- Preserve the supplied image composition.

## renderer selection

- Default: `GOLDFISH_STARTUP_RENDERER=go`
- Force Go native renderer: `GOLDFISH_STARTUP_RENDERER=go`
- Force Python ANSI fallback: `GOLDFISH_STARTUP_RENDERER=ansi`
- Optional development fallback: `GOLDFISH_STARTUP_GO_RUN=1`

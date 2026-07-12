# Schematic Terminal Layout Validation - 2026-07-12

## Purpose

This record covers the KiCad terminal-label readability repair. The target was
to ensure that generated terminal/node names do not overlap component bodies,
reference/value text, other terminal labels, or a physically coincident pin.

## Implemented Rules

- Terminal labels extend away from the actual source-backed pin side, including
  vertical alignment for top and bottom pins.
- Terminal stubs use multiple outward escape offsets and parallel label lanes
  before accepting a fallback location.
- Every multi-unit symbol uses a shared 25.4 mm vertical pitch in the emitter,
  pin resolver, body model, and visible-text model.
- The placer uses all source-backed symbol body bounds and all physical pin tips
  as its layout envelope. The wire geometry validator still uses only symbol
  bodies, so an electrical wire may leave a pin but cannot pass through a body.
- Dense/deep graph layouts switch to the arrangement decider's deterministic
  square-fill algorithm. The project writer emits a KiCad `User` sheet sized
  to the actual generated content when A3 would clip it.
- Placement settlement now rejects both body overlaps and coincident pin tips.
  It deterministically nudges the smaller component by 10.16 mm when a
  source-backed pin contact would merge otherwise unrelated nets.
- The final validator blocks output for terminal-label visual overlaps and
  source-pin-coordinate overlaps, in addition to the existing netlist/body/
  geometry checks.

## Evidence

The final immutable terminal-only visual regression is:

`kicad/examples/schematic_terminal_visual_run_2026_07_12_071500_final_complex20_v19/`

It generated these 20 complex canonical inputs:

`MJ003`, `MJ004`, `MJ008`, `MJ009`, `MJ010`, `MJ016`, `MJ019`, `MJ020`,
`MJ024`, `MJ025`, `MJ026`, `MJ030`, `MJ032`, `MJ035`, `N07`, `N107`,
`N127`, `N147`, `N167`, and `N187`.

Its `run_manifest.json` reports:

- 20/20 static and final validation passes.
- Zero component-body overlaps.
- Zero source-pin-coordinate overlaps.
- Zero terminal-label visual overlaps.
- Zero wire-geometry violations.
- Zero local-netlist failed or merged nets.

KiCad 10.0.4 exported and rendered the final `N187` project. The inspected
PNG was generated from the real KiCad SVG export at
`/tmp/progen-schematic-v19-renders/n187.png` during validation. It showed the
content-sized sheet, square-like placement, and separate terminal labels.

## Earlier Attempts

The fresh immutable experiment directories
`schematic_terminal_visual_run_2026_07_12_041200_label_clearance_v1` through
`schematic_terminal_visual_run_2026_07_12_071000_pin_envelope_v18` are retained
under `kicad/examples/`. They record the progression from initial text-body
collisions, through side-aware labels, multi-unit spacing, label lanes,
square-fill layout, pin-contact detection, and finally full source-pin layout
envelopes. They are diagnostic records only; v19 is the accepted result.

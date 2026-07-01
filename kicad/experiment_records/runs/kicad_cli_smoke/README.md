# KiCad CLI Smoke

Date: 2026-07-01

## What Was Tested

Generated/opened a small source-backed KiCad project:

- Project: `OPEN_THIS_PROJECT__vdc_resistor_op__PROJECT_FILE.kicad_pro`
- Components: VDC source, resistor, ground
- Purpose: prove that local KiCad CLI can load generated `.kicad_sch` files and run ERC.

## Previous State

This came before the placer architecture work. It tested the older project writer path, not the new component-only placer.

## Outcome

Passed.

- KiCad CLI quality report: 1 schematic checked, 1 passed, 0 failed.
- Evidence:
  - `kicad_quality_report.json`
  - `kicad_erc_reports/OPEN_THIS_PROJECT__vdc_resistor_op__PROJECT_FILE.erc.json`
  - `manifest.json`

## Known Limits

This run only covers a tiny pin-aware circuit. It does not prove the 100-component practical placer pack.

## Next

Use this as the baseline CLI sanity check before running larger generated project packs.

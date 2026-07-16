# Unified all-family 15x terminalized `totalmix`

This is one compact mixed circuit containing every current 49-family
`totalmix` scope: IC and non-IC components are placed and terminalized in the
same Proteus project.

## Outputs

- `ALL_TOTALMIX_49F_15X_HC00_8X_HC02_12X_NO_TERMINAL.pdsprj` — the locked-mega
  component-placer control.
- `ALL_TOTALMIX_49F_15X_HC00_8X_HC02_12X_TERMINAL_sa.pdsprj` — the unified
  terminalized candidate.
- `family_capacity_at_or_below_15.json` — actual complete-packet selection
  evidence for the requested scale.
- `generation_result.json` and `terminal_report.json` — placement and
  terminal/WIRE/link audits.

## Scope and verified limits

- 725 placed components.
- Every family has 15 instances except `74HC00` (8) and `74HC02` (12).
  These are locked-mega complete-package selector limits, recorded in the
  capacity artifact; they are not layout-row limits.
- 4,650 active terminals and 4,650 nonzero short WIREs.
- All terminal contacts are grid aligned, every WIRE reaches its exact pin, and
  every active terminal/component link is rebased from its final ROOT.DSN WIRE
  address.

## Local Proteus gate

A disposable copy normal-opened and cold-reopened in Proteus after the delayed
check. Both passes reached the schematic window with no Bad Object Record,
LXLCORE, fatal, or library dialog; its SHA-256 hash was unchanged. No Ctrl+S
was used. The screenshots are retained in `local_proteus_gate/`; the
disposable copy itself is intentionally not a tracked artifact.

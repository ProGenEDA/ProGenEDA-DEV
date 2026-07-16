# Unified all-family 9x terminalized `totalmix`

This is one mixed circuit containing the current 49-family `totalmix` scope:
both IC and non-IC families are present in the same placed/terminalized design.

## Outputs

- `ALL_TOTALMIX_49F_9X_HC00_8X_NO_TERMINAL.pdsprj` — locked-mega placement
  control.
- `ALL_TOTALMIX_49F_9X_HC00_8X_TERMINAL_sa.pdsprj` — terminalized candidate.
- `generation_result.json` — placement and terminal summary.
- `terminal_report.json` — full terminal/WIRE/link audit.

The request has nine of every current `totalmix` family except `74HC00`, which
uses the eight safe complete package groups available through the locked mega's
accepted selector. A fresh nine-package HC00 probe raised a local Proteus
fatal error, so this is recorded as donor-packet evidence rather than an
invented placement cap.

## Verified result

- 440 placed components.
- 2,850 active terminals and 2,850 nonzero WIREs.
- Every terminal contact is on the Proteus grid; every WIRE reaches its exact
  component pin; all terminal/component links are rebased from final
  ROOT.DSN WIRE addresses.
- The disposable candidate copy normal-opened and cold-reopened in local
  Proteus with no Bad Object Record, LXLCORE, fatal, or library dialog and no
  SHA-256 mutation. No Ctrl+S was used.

The normal/cold screenshots are in `local_proteus_gate/`. They establish loader
acceptance; user visual layout acceptance remains the final manual check.

# 74HC76 fresh locked-mega solo revalidation

This is a fresh, Proteus-only revalidation of `74HC76` using the locked
component-placer donor and the authoritative accepted terminalized donor:

- placer donor: `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`;
- terminal authority: `proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/74HC76/74HC76_terminalized_primary.pdsprj`;
- terminal implementation: the existing shared
  `src/proteusgen/component_terminal_placer.py` only.

No donor packets were copied into a generated circuit. The locked-mega
component placer produced each no-terminal project, then the shared catalogue
profile emitted terminals, short WIREs, and final-address links from the final
ROOT.DSN addresses.

## Attachment contract

The accepted donor has an asymmetric multipart object stream:

`12 terminal records -> U:A -> 7 WIREs -> 2 terminal records -> U:B -> 7 WIREs -> FF`.

For this family an inactive terminal-only partial stream is not a valid native
Proteus attachment unit. The fresh `NATIVE_CONTACT_STAGE` and
`GRID_CONTACT_STAGE` diagnostics both stop with the captured
`VGDVC.DLL [000190DA]` fatal. The direct locked-mega control, authoritative
donor, and complete active shared-placer output all normal-open. The final
route is therefore the donor-proven atomic unit: grid-aligned terminal contact,
proper left/right angle, nonzero short WIRE to the exact pin, and matching
final-address terminal/component link suffixes.

## Generated packs

| Scale | Control | Terminalized output | Terminal/WIRE units | Local Proteus result |
| ---: | --- | --- | ---: | --- |
| 1x | `01_staged_1x/S01_74HC76_1X/S01_74HC76_1X_NO_TERMINAL.pdsprj` | `01_staged_1x/S01_74HC76_1X/S01_74HC76_1X_CATALOGUE_TERMINAL_sa.pdsprj` | 14 | complete active and cold reopen normal |
| 9x | `03_solo_scales/S01_74HC76_9X/S01_74HC76_9X_NO_TERMINAL.pdsprj` | `03_solo_scales/S01_74HC76_9X/S01_74HC76_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 126 | normal open and cold reopen |
| 15x | `03_solo_scales/S01_74HC76_15X/S01_74HC76_15X_NO_TERMINAL.pdsprj` | `03_solo_scales/S01_74HC76_15X/S01_74HC76_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 210 | normal open and cold reopen |

The 15x normal/cold-reopen captures are in
`04_local_proteus_gate/G03_74HC76_15X_before_close.png` and
`04_local_proteus_gate/G04_74HC76_15X_cold_reopen_before_close.png`.
All normal-opening disposable copies retained their SHA-256 values; none were
Ctrl+S-saved. User visual acceptance remains separate from this loader gate.

## Regression evidence

`python -m pytest tests/test_component_placer.py -q -k "hc76"` passed all four
focused tests, including the 9x/15x progressive-scale assertion. The frozen
two-pin accepted-route regression passed 28 tests, and JSON validation plus
`compileall` passed. The broader existing catalogue suite still has unrelated
failures for out-of-locked-mega/older-expectation families (including `4017`),
so it is recorded as negative unrelated baseline evidence rather than repaired
by touching another family. Mixed output is intentionally not generated until
every remaining group has 1x, 9x, and 15x solo evidence.

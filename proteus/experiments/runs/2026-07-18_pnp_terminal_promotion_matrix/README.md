# PNP terminal promotion matrix — 2026-07-18

This is the donor-first validation record for the additive `PNP` non-IC
terminal route. It uses the unified
`proteus/active/src/proteusgen/component_terminal_placer.py` route; no
component-specific terminal generator was created.

## Authoritative evidence and mechanics

The authority is
`proteus/active/evidence/donors/terminalized_catalogue_evidence/three_pin_transistor/PNP/PNP_terminalized_primary.pdsprj`.
It proves the `BASE`, `COLLECTOR`, `EMITTER` order, B/C/E link locations,
left/right terminal orientation, and immediate WIRE grammar. The generated
route deliberately moves contacts one 254,000-unit grid step outward, then
emits a nonzero WIRE back to the donor-proven exact pin.

The first `D01_native_pin_contact` detached-terminal diagnostic failed with a
Proteus library dialog and is retained. It established that a PNP terminal,
active component link, and WIRE must be emitted as one indivisible unit.

## Accepted loader matrix

Every listed accepted project had two local 12-second cold opens, a title-bar
check, dialog scan, unchanged disposable gate-copy hash, and retained PNG
screenshots.

| Folder | Coverage | Result |
| --- | --- | --- |
| `D02_grid_contact_active_unit_v2` | loader-gated grid/nonzero diagnostic | passed twice |
| `S01_complete_nonzero_grid_v3` | PNP `1x` | passed twice |
| `S02_PNP_9X` | PNP `9x` | passed twice |
| `S03_PNP_15X` | PNP `15x` | passed twice |
| `M01_PNP_RESISTOR_CAP_1X` | minimal native mix | passed twice |
| `M02_PNP_DIODE_ASYMMETRIC` | asymmetric PNP/diode/R/C mix | passed twice |
| `M03_PNP_HETEROGENEOUS_NON_IC_1X` | PNP/NPN/NMOSFET/control/R/C/diode mix | passed twice |
| `M04_PNP_DIODE_RESISTOR_CAP_15X` | 60-component `15x` stress mix | passed twice |
| `EXE_M10_PNP_DIODE15X_RELEASE` | final rebuilt executable 60-component stress mix | passed twice |
| `EXE_M09_PNP_HET1X` | latest executable heterogeneous non-IC mix | passed twice |

`EXE_M10` reports 60 terminalized components and 135 terminal/WIRE pairs;
`EXE_M09` reports nine terminalized components and 24 terminal/WIRE pairs.
Both report grid-aligned terminal contacts, nonzero WIREs, valid link rebasing,
and a single explicit finalizer.

## Preserved diagnostics

- `D01_native_pin_contact`: rejected detached-terminal stage; required active
  attachment unit discovered.
- `EXE_M07_PNP_HETEROGENEOUS_NON_IC_1X_REBUILT`: retained path-budget failure
  evidence. Its manifest path reached 260 characters because the temporary
  work directory repeated the output stem. The active executable now uses
  `.progen_` instead.

This provides loader/persistence acceptance, not a simulation or user visual
layout acceptance claim. The next family remains a separate donor-first
non-IC addition; IC work stays last.

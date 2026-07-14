# 74HC00 terminal revalidation — 2026-07-14

This pack uses only the locked mega component placer and the shared
`src/proteusgen/component_terminal_placer.py` route. The authoritative
terminal donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC00/74HC00_user_terminalized_july04.pdsprj`.

## 1x evidence

- `C01_74HC00_LOCKED_MEGA_NO_TERMINAL.pdsprj`: component-placer control.
- `C02_74HC00_NATIVE_PIN_CONTACT.pdsprj`: correctly oriented terminal-only
  diagnostic stage.
- `C03_74HC00_GRID_CONTACT.pdsprj`: grid-contact terminal-only diagnostic
  stage.
- `C04_74HC00_COMPLETE.pdsprj`: final active 12-terminal/12-WIRE route.

The authoritative order is `3, 8, 6, 11, 1, 2, 10, 9, 4, 5, 13, 12`. The
complete route retains every donor WIRE point: point counts are
`2,2,2,2,3,3,2,3,3,2,3,3`; all 12 attaching contacts are on the 254,000-unit
grid; all 12 WIREs are nonzero; and each active terminal/component pin-link
suffix is rebased from its final ROOT.DSN WIRE address.

## Local Proteus gate

Each control/stage opened after a cold launch, remained open for 12 seconds,
had no `Bad Object Record`, fatal, LXLCORE, or device-library title, and its
disposable copy hash remained unchanged. `C04` was cold-reopened as `G05` with
the same result. No normally opening project was Ctrl+S saved.

Screenshots were captured immediately before each process close in
`02_local_proteus_gate/`; `G04_C04_74HC00_COMPLETE.png` visibly shows all four
gates and their three terminal attachments.

## Next gate

The 1x route is loader-passed. The profile still records only one
donor-proven terminalized package while 9x/15x are generated separately. The
locked mega has eight previously safe HC00 packages after the rejected early
offsets, so scale work must establish availability rather than invent a
terminal limit.

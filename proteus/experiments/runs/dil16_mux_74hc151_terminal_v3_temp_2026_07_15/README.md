# 74HC151 terminal revalidation - 2026-07-15

Placement source (locked for this sweep):
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.

Terminal evidence source:
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC151/74HC151_user_terminalized_july04.pdsprj`.

All terminal emission used the shared
`src/proteusgen/component_terminal_placer.py`; no component-specific terminal
script was introduced.

## Generated evidence

- `01_solo_1x/C01_...`: locked-mega no-terminal control.
- `01_solo_1x/C02_...`: native-pin-contact diagnostic, 14 terminals.
- `01_solo_1x/C03_...`: grid-contact diagnostic, 14 terminals.
- `01_solo_1x/C04_...`: final 1x, 14 grid-aligned terminals and 14 nonzero
  terminal-contact-to-exact-pin WIREs.
- `03_scale_9x_15x/S09_...`: final 9x, 126 terminal/WIRE pairs.
- `03_scale_9x_15x/S15_...`: final 15x, 210 terminal/WIRE pairs.

The final terminal symbols preserve the authoritative donor's labels,
orientations and component-relative grid contacts. The final WIREs are direct
two-point paths from those contacts to the exact current pin coordinates; this
avoids the verified zero-length collapse caused by donor-polyline retargeting.

## Local Proteus result

On 2026-07-15, C02, C03, C04, S09 and S15 each normal-opened and cold-reopened
after the delayed window check. No `Bad Object Record`, fatal, LXLCORE, or
library dialog appeared, and disposable-copy hashes did not change. The
large-output capture is
`03_scale_9x_15x/S15_74HC151_15X_COMPLETE_GATE_INITIAL_before_close.png`.

This records loader/persistence acceptance only. User visual acceptance remains
separate.

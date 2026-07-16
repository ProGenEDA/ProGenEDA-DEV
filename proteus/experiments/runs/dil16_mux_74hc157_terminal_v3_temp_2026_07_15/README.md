# 74HC157 terminal revalidation - 2026-07-15

The locked placement donor is
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
The authoritative terminal donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj`.

All outputs use the shared component placer and
`src/proteusgen/component_terminal_placer.py`; no terminal behavior changed.

`01_solo_1x` contains the no-terminal control, native-contact diagnostic,
grid-contact diagnostic, and complete terminalized 1x. `03_scale_9x_15x`
contains no-terminal controls and complete 9x/15x finals.

The complete files have 14/126/210 grid-aligned terminal contacts and nonzero
two-point WIREs to the exact pins. All 1x diagnostics and final 1x/9x/15x
files normal-opened and cold-reopened locally with no loader dialog or copy
mutation. The 15x capture is
`03_scale_9x_15x/S15_74HC157_15X_COMPLETE_GATE_INITIAL_before_close.png`.

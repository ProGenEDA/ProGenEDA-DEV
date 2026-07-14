# 4511 terminal revalidation - 2026-07-15

The locked placement donor is
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
The authoritative terminal donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_decoder_driver/4511/4511_user_terminalized_july04.pdsprj`.

All files were emitted with the shared component placer and
`src/proteusgen/component_terminal_placer.py`; no source/profile behavior was
changed.

`01_solo_1x` contains the locked-mega control, native-contact/grid-contact
diagnostics, and final 1x. `03_scale_9x_15x` contains controls and final 9x/
15x files. The finals contain 14/126/210 grid-aligned terminal contacts and
nonzero exact-pin WIREs.

All staged 1x and final 1x/9x/15x files normal-opened and cold-reopened after
the delayed local gate with no loader dialog or copy mutation. The large-output
capture is `03_scale_9x_15x/S15_4511_15X_COMPLETE_GATE_INITIAL_before_close.png`.

# NE555 terminal revalidation - 2026-07-15

Placement uses the locked mega donor
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
Terminal evidence is
`proteus_ic/donors/terminalized_catalogue_evidence/dil8_analog_ic/NE555/NE555_terminalized_primary.pdsprj`.

All files use the shared component placer and
`src/proteusgen/component_terminal_placer.py`. `01_solo_1x` contains the
control, native/grid diagnostics, and complete 1x; `03_scale_9x_15x` contains
controls and complete 9x/15x files. Final routes contain 8/72/120
grid-aligned nonzero terminal-to-exact-pin WIREs respectively.

Every 1x diagnostic and complete 1x/9x/15x final passed normal/cold local
Proteus gates with unchanged disposable copies. The 15x capture is
`03_scale_9x_15x/S15_NE555_15X_COMPLETE_GATE_INITIAL_before_close.png`.

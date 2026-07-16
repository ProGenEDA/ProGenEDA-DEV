# 74HC157 donor preflight and 1x repair

This evidence pack is generated from the locked component-placement mega donor
and the shared `src/proteusgen/component_terminal_placer.py`; it does not copy
the terminalized 74HC157 donor as an output.

`S01_74HC157_1X_NO_TERMINAL.pdsprj` is the locked-mega placement control.
`S01_74HC157_1X_CATALOGUE_TERMINAL_sa.pdsprj` has fourteen catalogue-driven,
grid-contact `$TERBIDIR` records and fourteen nonzero native WIREs to the exact
pin positions.

The authoritative donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_mux/74HC157/74HC157_terminalized_primary.pdsprj`.
Its terminal-leading stream and link slots are recorded in
`knowledge/hc157_donor_preflight_2026_07_13.md`.

The first two candidates were rejected with a visible `VGDVC.DLL` fatal and
were not saved. The final repair removes the raw component-placer finalizer
byte before appending the donor-native WIRE sequence. Static checks prove the
first WIRE marker is donor offset plus the one-byte U33/U1 reference delta.

Local Proteus 8.13 gate: the final 1x copy opened normally after a 12-second
wait, then cold-opened normally again. Screenshots are in
`local_proteus_gate/G05_74HC157_1X_finalizer_trim_initial_before_close.png`
and `local_proteus_gate/G06_74HC157_1X_finalizer_trim_cold_reopen_before_close.png`.
The normal copy was not Ctrl+S-saved and its SHA-256 remained
`D97AB3CF99A9B1C558C54D488AFCE24AE71B207984D4BC7A78EC5A139134C64C`.

Status: 1x local loader and persistence acceptance passed. The same frozen
route also passed 9x and 15x evidence under `10_hc157_scale_finalizer_trim/`.
User visual acceptance remains authoritative for layout.

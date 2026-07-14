# 74HC08 terminal revalidation — 2026-07-14

The source is the actual accepted HC08 donor under
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC08/`.
The pack uses the locked mega component placer plus the shared catalogue
terminal placer only.

`01_solo_1x/` contains the no-terminal control, native-contact diagnostic,
grid-contact diagnostic, and complete active output. The 12 terminal/WIRE units
follow donor order `8,11,3,6,1,2,4,5,9,10,12,13`; all use a grid-aligned
contact and a nonzero two-point wire to the current exact pin.

Control, native, grid, complete, and complete-cold-reopen copies all reached
normal Proteus windows after the 12-second wait. No modal error was detected,
copy hashes stayed unchanged, and no normal project was Ctrl+S saved. The
pre-close complete capture is `02_local_proteus_gate/G04_C04_74HC08_COMPLETE.png`.

`03_scale_9x_15x/` contains the independently generated 9x and 15x
no-terminal controls and complete active outputs. Their static audits found
108/180 grid contacts, nonzero exact-pin WIREs, and the full donor label/order
per package. Both outputs normal-opened and cold-reopened after the delayed
window gate; the 15x pre-close captures are retained in
`04_local_proteus_scale_gate/`.

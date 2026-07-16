# 74HC02 terminal revalidation — 2026-07-14

This pack was generated only through the locked mega component placer and
shared component terminal placer. The accepted donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC02/74HC02_user_terminalized_july04.pdsprj`.

`01_solo_1x/` contains the no-terminal control, native-contact diagnostic,
grid-contact diagnostic, and final complete active output. The exact active
unit order is `10,13,4,1,2,3,5,6,8,9,11,12`. The final output has twelve
grid-attached terminal contacts and twelve nonzero exact-pin WIREs; pins 5 and
6 retain their donor-proven three-point input polylines.

The five local copies (control, native, grid, complete, and complete cold
reopen) all reached normal Proteus schematic windows after 12 seconds with no
Bad Object Record, fatal, LXLCORE, or library dialog. Their hashes were
unchanged, so no normal project was Ctrl+S saved. `G04_C04_74HC02_COMPLETE.png`
is the pre-close visual record showing all four gate subparts terminalized.

`03_scale_9x_12x/` contains the complete 9x and 12x controls/terminalized
outputs. They have 108 and 144 grid-attached nonzero WIREs respectively, and
both their initial cold opens and cold reopens were normal. A fresh 15x
component-placer control fails before terminal attachment because the locked
mega has only twelve complete HC02 packages. This is a source availability
boundary, not an emitter limit.

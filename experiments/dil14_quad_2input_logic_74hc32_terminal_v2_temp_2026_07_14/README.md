# 74HC32 terminal revalidation — 2026-07-14

The actual accepted donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC32/74HC32_user_terminalized_july04.pdsprj`.
This pack uses the locked mega component placer and the shared catalogue
terminal placer only.

`01_solo_1x/` contains the locked-mega no-terminal control, native-pin-contact
diagnostic, grid-contact diagnostic, and complete active output. The donor
order is `8,11,3,6,1,2,4,5,9,10,12,13`; it has four right-side 0-degree
outputs, eight left-side 1800-degree inputs, and twelve nonzero two-point
short wires from grid contacts to exact current pins.

All staged files and a cold reopen of the complete active file reached a normal
Proteus window after the 12-second delayed gate. No modal error appeared, no
normally opening copy was Ctrl+S-saved, and copy hashes were unchanged. The
complete active captures are retained under `02_local_proteus_gate/`.

The locked mega has fifteen complete HC32 packages. Its 9x and 15x routes must
be independently generated and loader-gated before this profile is promoted
beyond its 1x donor proof.

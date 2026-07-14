# 74HC86 terminal revalidation — 2026-07-14

The actual accepted donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_quad_2input_logic/74HC86/74HC86_user_terminalized_july04.pdsprj`.
This pack uses the locked mega component placer plus the shared catalogue
terminal placer only.

`01_solo_1x/` contains the locked-mega no-terminal control, native-pin-contact
diagnostic, grid-contact diagnostic, and complete active output. Its donor
attachment order is `6,3,8,11,4,5,1,2,9,10,12,13`; WIRE point counts are
`3,3,2,3,3,2,2,2,3,3,3,2`. The seven former profile truncations are restored
as full donor polylines, not synthesized alternative wires.

All staged files and a cold reopen of the complete output reached a normal
Proteus window after the 12-second gate. No modal error appeared, normal copies
were not Ctrl+S-saved, and hashes stayed unchanged. The complete active
captures are retained under `02_local_proteus_gate/`.

`03_scale_9x_15x/` contains independently generated 9x and 15x controls and
complete active outputs. Static audits found 108/180 grid contacts, full
two/three-point exact-pin WIREs, and the donor order per package. Both
normal-opened and cold-reopened after the delayed gate; 15x captures are under
`04_local_proteus_scale_gate/`.

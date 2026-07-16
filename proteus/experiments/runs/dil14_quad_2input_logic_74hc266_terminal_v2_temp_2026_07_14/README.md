# 74HC266 donor-grounded terminal route

The component base is generated only by the locked
`new_components_5x_mega.pdsprj` placer. Terminal facts come only from the
user-accepted `74HC266_user_terminalized_july04.pdsprj` donor and are emitted
by the shared `component_terminal_placer.py` path.

`01_solo_1x/` contains the required diagnostic sequence: bare locked-mega
control, native pin-contact terminals, grid-contact terminals, and the final
active terminal/link/WIRE output. The final output has twelve grid-aligned
terminals and twelve active short WIREs in donor order
`3,4,10,11,1,2,5,6,8,9,12,13`. It preserves the donor's nine routed
three-point paths, three two-point paths, and its literal `Pin5I4` label for
physical pin 6.

The local Proteus 8 gate passed the control, native, grid, complete, and
complete cold-reopen launches after the required delayed check. No modal error
appeared and all disposable copies retained their original hashes. See
`loader_results.json`; `independent_static_audit_1x.json` independently
records labels, WIRE point counts, suffix links, component pin links, and the
normalized selected-package CDB.

`03_scale_9x_15x/` contains independent locked-mega controls and complete
terminalized 9×/15× outputs. They preserve 108/180 active terminal/WIRE units,
the exact donor order and three/two-point mix for every package, grid contacts,
and normalized 9/15-package CDBs. Both scales normal-opened and cold-reopened
without a dialog or copy mutation; the retained 15× normal/cold captures are
under `04_local_proteus_scale_gate/`.

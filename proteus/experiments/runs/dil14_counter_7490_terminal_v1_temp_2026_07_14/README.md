# 7490 terminalized solo sweep

Placement controls use only the locked `new_components_5x_mega.pdsprj` donor;
the terminal grammar comes from the authoritative accepted 7490 donor under
`proteus_ic/donors/terminalized_catalogue_evidence/dil14_counter/7490/`.

`01_solo_1x/` contains the bare control, native-contact diagnostic,
grid-contact diagnostic, and final catalogue output. `03_scale_9x_15x/`
contains bare controls and complete 9x/15x terminalized outputs. All final
outputs use the shared `component_terminal_placer.py` path: ten grid-contact,
nonzero terminal-to-pin WIREs per component, active final-address links, and
the donor's terminal-leading packet order.

The initial native candidate had a one-byte stale component tail and raised a
Proteus Fatal Error. The recorded catalogue finalizer trim corrected the full
evidence-backed boundary set. Native, grid, complete, 9x, and 15x outputs then
normal-opened and cold-reopened without a modal error or save mutation. See
the accompanying reports for exact counts and loader results.

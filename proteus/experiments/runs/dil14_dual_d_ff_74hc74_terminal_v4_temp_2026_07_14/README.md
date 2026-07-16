# 74HC74 donor-grounded terminal route

The bare dual flip-flop is placed solely through the locked
`new_components_5x_mega.pdsprj` component placer. The shared catalogue terminal
placer then emits the two donor-proven subpart blocks; no component-specific
terminal script or runtime donor copy is used.

The actual accepted donor proves that each subpart is one indivisible loader
unit: terminal records, its component record with matching active pin links,
then its WIRE records. An earlier inactive-terminal-only diagnostic raised a
`VGDVC.DLL` fatal error. The corrected shared path retains the complete unit
for diagnostics as well: native contact uses zero-length on-pin WIREs, while
grid and final stages use nonzero short WIREs from grid-aligned terminal
contacts to the exact current pins.

`01_solo_1x/` contains the locked-mega control and native, grid, and complete
stages. The final project has twelve terminal/WIRE pairs, left-side `1800` and
right-side `0` orientation, a single `FF` finalizer, active final-address
suffix links, and the exact A/B donor block order. Its complete project was
cold-reopened after the delayed local Proteus gate. See `loader_results.json`
and `independent_static_audit_1x.json`.

`03_scale_9x_15x/` contains locked-mega controls and complete terminalized
outputs for nine and fifteen packages. They retain 108 and 180 grid-aligned,
nonzero terminal/WIRE pairs, respectively, with the same A/B block order,
final-address suffix rebasing, and normalized 9/15-package CDBs. Both scales
normal-opened and cold-reopened without a modal dialog or copy mutation; see
`loader_results_scale.json` and `independent_static_audit_scale.json`.

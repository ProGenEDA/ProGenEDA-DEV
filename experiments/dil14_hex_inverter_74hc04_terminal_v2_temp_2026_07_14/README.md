# 74HC04 donor-grounded terminal route

The bare 74HC04 package is placed solely through the locked
`new_components_5x_mega.pdsprj` component placer.  Terminal labels, pin
contacts, routed WIRE shapes, active link fields, and record order come from
the accepted E04 donor and are emitted only through the shared catalogue
terminal placer.

The E04 donor reveals one non-obvious Proteus packet fact: internal record D
owns pins 13/12 and internal record F owns pins 9/8.  The catalogue records
that binary mapping separately from the normal logical gate-letter metadata.
This prevents the previously reversed D/F terminal links and coordinates.

`01_solo_1x/` contains the required loader-gated progression: locked-mega
control, native pin-contact terminals, grid-contact terminals, and the final
active terminal/link/WIRE project.  The final project has 12 grid-aligned
terminals, left-side `1800` inputs, right-side `0` outputs, 12 nonzero routed
short WIREs, and the exact E04 point-count pattern
`3,3,3,3,3,3,4,3,4,4,4,4`.

Every stage normal-opened in local Proteus after the delayed check; the final
project then cold-reopened cleanly.  See `loader_results.json` and
`independent_static_audit_1x.json`.

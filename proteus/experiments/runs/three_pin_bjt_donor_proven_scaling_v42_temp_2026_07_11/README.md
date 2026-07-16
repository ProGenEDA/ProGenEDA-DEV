# Donor-proven BJT scaling — 2026-07-11

This pack extends only `NPN` and `PNP` from the recovered 1x route to the
actual donor-proven 2x and 4x limits. The supporting native donors are
`2_NPN.pdsprj`, `4_NPN.pdsprj`, `2_PNP.pdsprj`, and `4_PNP.pdsprj` under
`proteus_ic/donors/manual_downloads_20260611/New folder (7)`.

Those donors prove repeated terminal-leading blocks: three ordered terminals,
one placed component, three WIRE records, then the next block; exactly one FF
terminates the final block. The shared terminal placer implements that pattern
without a family-specific runner.

All four generated terminalized outputs passed the delayed local Proteus
open/Ctrl+S/cold-reopen gate. `9x`, `15x`, and `23x` are intentionally not
emitted: no accepted donor currently proves those larger terminal-leading BJT
streams. `2N3904` and `2N4401` remain limited to their separately verified 1x
route because their available terminal evidence is an NPN alias, not a native
numbered-transistor scaling donor.

# 4027 reference-width scale repair

These packs use the locked mega component placer and the same shared
catalogue-driven terminal placer as the accepted 1x reference-width repair.
No donor packet is copied into the generated project.

| Scale | Terminalized file | Physical 4027 halves | Terminal/WIRE units |
| ---: | --- | ---: | ---: |
| 9x | `S02_4027_9X/S02_4027_9X_REFERENCE_WIDTH_DONOR_CONTACT_sa.pdsprj` | 18 | 126 |
| 15x | `S02_4027_15X/S02_4027_15X_REFERENCE_WIDTH_DONOR_CONTACT_sa.pdsprj` | 30 | 210 |

Independent ROOT.DSN parsing confirms each physical A/B half is followed by
exactly seven native attachment WIREs, all WIRE endpoints are equal and on the
Proteus grid, and no WIRE suffix is duplicated.

Visible loader evidence was captured before closing every normal-opened
project. Neither normal open was Ctrl+S-saved:

- 9x open/reopen: `G12_4027_9X_BEFORE_CLOSE.png`,
  `G13_4027_9X_COLD_REOPEN_BEFORE_CLOSE.png`;
- 15x open/reopen: `G14_4027_15X_BEFORE_CLOSE.png`,
  `G15_4027_15X_COLD_REOPEN_BEFORE_CLOSE.png`.

All four launches reached Proteus Schematic Capture without a Bad Object
Record, fatal, or library dialog.

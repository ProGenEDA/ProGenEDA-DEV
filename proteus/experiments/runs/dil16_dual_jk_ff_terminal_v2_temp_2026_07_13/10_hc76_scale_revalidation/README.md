# 74HC76 scale revalidation

Both packs are generated through the locked mega component placer followed by
the same shared 74HC76 catalogue profile as the revalidated 1x pack.

| Scale | Terminalized output | Physical halves | Terminal/WIRE units |
| ---: | --- | ---: | ---: |
| 9x | `S03_74HC76_9X/S03_74HC76_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 18 | 126 |
| 15x | `S03_74HC76_15X/S03_74HC76_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 30 | 210 |

Independent DSN parsing verifies every physical A/B half has seven native
active WIRE units, all endpoints are equal and grid-aligned, all suffixes are
unique, and each stream ends with one `FF` finalizer.

Visible loader screenshots captured before closure:

- 9x: `G18_74HC76_9X_BEFORE_CLOSE.png`,
  `G19_74HC76_9X_COLD_REOPEN_BEFORE_CLOSE.png`;
- 15x: `G20_74HC76_15X_BEFORE_CLOSE.png`,
  `G21_74HC76_15X_COLD_REOPEN_BEFORE_CLOSE.png`.

All normal opens and cold reopens completed without a Bad Object Record,
fatal, or library dialog. Normal opens were not Ctrl+S-saved.

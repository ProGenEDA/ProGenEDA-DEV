# NPN terminal promotion matrix v2 — 2026-07-18

This is the accepted fresh regeneration for the additive `NPN` executable
terminal route. It supersedes neither the original donor evidence nor the v1
failure pack: v1 remains retained as the record of the malformed NPN-tail to
later-diode boundary.

## Repair under test

The authoritative mixed donor proves the NPN attachment tail belongs after the
ordinary component packet stream and ends with one explicit `FF`. The shared
placer now applies that rule only to NPN's non-IC tail profile. It leaves the
accepted diode serializer and frozen IC/display routes unchanged.

## Matrix

| Folder | Purpose | Loader gate |
| --- | --- | --- |
| `S01_NPN_1X` | NPN `1x` | passed twice |
| `S02_NPN_9X` | NPN `9x` | passed twice |
| `S03_NPN_15X` | NPN `15x` | passed twice |
| `M01_NPN_RESISTOR_CAP_1X` | minimal native mix | passed twice |
| `C02_NPN_DIODE_ASYMMETRIC_NO_VSOURCE` | exact former failure isolation | passed twice |
| `M02_NPN_NATIVE_ASYMMETRIC` | diode/source asymmetric native mix | passed twice |
| `M03_NPN_CURRENT_CATALOGUE_NATIVE_1X` | existing catalogue-backed non-IC mix | passed twice |
| `M04_NPN_RESISTOR_CAP_15X` | `15x` NPN/R/C stress mix | passed twice |
| `M05_NPN_DIODE_15X` | `15x` NPN/diode/R/C stress mix | passed twice |

Each case contains the input JSON, a freshly generated `_sa.pdsprj`, its
application report, and two local-Proteus gate screenshots. Disposable
`_GATE.pdsprj` copies are excluded from retained evidence; their unchanged
SHA-256 values are captured by the gate output during verification.

## Validation

- Complete component placer: `215 passed, 5 xfailed`.
- Application/executable source tests: `14 passed`.
- All emitted NPN attachment wires in the executable/mixed matrix are nonzero
  and their terminal contacts are grid-aligned.
- No modal error, Bad Object Record, library dialog, or LXLCORE dialog was
  observed during either 12-second cold open for any matrix case.

The next family must be audited as a separate non-IC addition; IC family work
remains out of scope until all remaining non-IC routes are independently
locked.

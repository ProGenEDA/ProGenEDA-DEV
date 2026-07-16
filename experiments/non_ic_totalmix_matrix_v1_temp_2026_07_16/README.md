# Non-IC mixed terminal matrix — 2026-07-16

## Scope

This is an error-screening matrix only. IC work was explicitly put on hold.
`FUSE` and `SWITCH` are excluded from the active totalmix route by the shared
terminal placer's explicit blocker.

## Native two-pin result

The 18-family set (`VSOURCE`, `CSOURCE`, `VSINE`, `VPULSE`, `CAP`, `CAP-ELEC`,
`REALIND`, `RESISTOR`, diode/zeners/LED) uses active grid-contact terminals and
short native WIREs. It had already passed local loader screening at 1x, 3x,
9x, and 15x. This run repaired and accepted the larger uneven packs:

| Pack | Count per family | Placed components | Terminals / WIREs | Local Proteus gate |
| --- | --- | ---: | ---: | --- |
| `N10` | 30; `CAP-ELEC` 21 | 531 | 1,062 / 1,062 | normal open + cold reopen, no modal error |
| `N12` | 45; `CAP-ELEC` 21 | 786 | 1,572 / 1,572 | normal open + cold reopen, no modal error |
| `N14` | 58; `CAP-ELEC` 21 | 1,007 | 2,014 / 2,014 | normal open + cold reopen, no modal error |

The final accepted maximum for one uniform 18-family native mix in the locked
mega is **58 per non-`CAP-ELEC` family**, with `CAP-ELEC` held at its independent
21-packet component-placer ceiling. A 60x request was rejected before output
because the locked mega has only 58 CDB-backed `CSOURCE` packets. This is a
donor inventory limit, not a terminal geometry or Proteus-loader limit.

The repair has two constrained parts:

- Direct parsed body markers may now read valid signed grid coordinates through
  2,000,000,000, while the broad packet scanner remains capped at 700,000,000.
  R24 at y=702,950,080 was the first valid body marker previously excluded.
- If two donor-derived temporary suffix progressions meet at a large scale, the
  later occurrence is assigned an unused `0x7A00+` temporary value before final
  WIRE-address rebasing. Final active links still come solely from the final
  WIRE addresses. 15x output from the shared placer is byte-identical to the
  pre-change backup, proving no-collision routes are unchanged.

`N10`, `N12`, and `N14` each include a bare control, terminalized project,
machine-readable report, and summary. The `*_COLD_GATE_COPY.pdsprj` files are
disposable copies used for loader checks and retain the generated file hash.

Static placement validation reports the historic full-donor-CDB orphan pin and
property rows (`E_ORPHAN_CDB_*`) while `RawPlacementResult.valid` is true; this
run intentionally preserves the locked full CDB and made no CDB mutation.

## Quick varied-combination screen

Six uneven mixes generated statically with all expected attachments:

| Combination | Placed components | Terminals / WIREs | Temporary remaps |
| --- | ---: | ---: | ---: |
| `Q01_SOURCES_RCL_7X` | 38 | 76 / 76 | 0 |
| `Q02_DIODE_LED_CLUSTER` | 68 | 136 / 136 | 0 |
| `Q03_FULL18_UNEVEN_SMALL` | 90 | 180 / 180 | 0 |
| `Q04_FULL18_UNEVEN_9X` | 114 | 228 / 228 | 0 |
| `Q05_FULL18_UNEVEN_30X` | 426 | 852 / 852 | 1 |
| `Q06_FULL18_UNEVEN_58X` | 906 | 1,812 / 1,812 | 15 |

Proteus normal-open checks passed with no modal error for Q03, Q04, Q05, and
Q06; Q06 also cold-reopened normally. Q01 and Q02 are static structural
screens, included to cover source/RCL and diode/LED-specific paths quickly.

## Non-IC multi-pin screen

At 3x, each of these groups was generated against the same 18-family native
baseline and raised the same Proteus parser-derived library dialog:

- CONTROL3: `POT-HG`, `LM317T`, `OPAMP`
- BJT4: `NPN`, `PNP`, `2N3904`, `2N4401`
- MOS3: `NMOSFET`, `2N7000`, `BS170`
- FOURPIN2: `BRIDGE`, `TRAN-2P2S`

No per-family block, geometry adjustment, or serializer change was made after
that screen; the user directed these routes be left unchanged.

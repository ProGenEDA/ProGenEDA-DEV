# NMOSFET terminal promotion matrix — 2026-07-18

This is the retained evidence pack for the executable-owned `NMOSFET`
terminal route. The shared terminal placer was not changed; this promotion
corrected the NMOSFET profile to name its real terminalized donor and to state
that every diagnostic stage requires one complete active terminal/link/WIRE
unit.

## Donor and scope

- Authoritative donor:
  `proteus/active/evidence/donors/terminalized_catalogue_evidence/three_pin_transistor/NMOSFET/NMOSFET_user_terminalized_july04.pdsprj`
- Fresh bare control: `00_bare/NMOSFET_1X_BARE_COMPONENT_PLACER.pdsprj`
- Frozen routes not changed: two-pin families, `2N7000`, `BS170`, `NPN`, and
  `PNP`.

## Evidence matrix

| Directory | Output | Purpose | Result |
| --- | --- | --- | --- |
| `D01_native_pin_contact` | `D01_NMOSFET_1X_NATIVE_PIN_CONTACT_sa.pdsprj` | Active-unit native pin diagnostic | Both cold opens passed; native pin contact is intentionally not a grid contact. |
| `D02_grid_contact` | `D02_NMOSFET_1X_GRID_CONTACT_sa.pdsprj` | Grid-contact diagnostic | Static-valid; both cold opens passed. |
| `S01_complete_1x` | `EXE_S01_NMOSFET_1X_RELEASE_sa.pdsprj` | 1× executable output | 3 terminals / 3 nonzero wires; both opens passed. |
| `S02_9x` | `EXE_S02_NMOSFET_9X_RELEASE_sa.pdsprj` | 9× executable output | 27 terminals / 27 nonzero wires; both opens passed. |
| `S03_15x` | `EXE_S03_NMOSFET_15X_RELEASE_sa.pdsprj` | 15× executable output | 45 terminals / 45 nonzero wires; both opens passed. |
| `M01_ratio_mix` | `EXE_M01_NMOSFET_RATIO_MIX_RELEASE_sa.pdsprj` | Asymmetric non-IC mix | 30 terminal/WIRE units; both opens passed. |
| `M02_heterogeneous_mix` | `EXE_M02_NMOSFET_HETEROGENEOUS_MIX_RELEASE_sa.pdsprj` | Cross-family non-IC mix | 54 terminal/WIRE units; both opens passed. |
| `M03_dense_15x` | `EXE_M03_NMOSFET_DENSE_15X_RELEASE_sa.pdsprj` | Dense 15× stress mix | 180 terminal/WIRE units; both opens passed. |

Each gated directory has its disposable `*_GATE_COPY.pdsprj`,
`local_proteus_gate.json`, and two post-launch screenshots. Each executable
output has a `.progen_report.json` showing valid grid contacts, nonzero WIREs,
and active terminal/component links.

## Release linkage

The rebuilt `proteus/active/release/ProgenProteus.exe` used for the fresh
outputs hashes to:

`F278F4E6E1B4A2EA34309B30B6914F73331110CDBD7864806CCA2495F77776FB`

After that rebuild, `S01_complete_1x/EXE_S01_NMOSFET_1X_RELEASE_FINAL_sa.pdsprj`
was generated again from `input.json` and passed another two 12-second cold
opens with an unchanged disposable-copy hash. Its saved loader screenshots are
in `S01_complete_1x/screenshots/release_final/`.

For the byte-level donor audit and precise pin/WIRE evidence, see
[`proteus/active/knowledge/nmosfet_terminal_promotion_preflight_2026_07_18.md`](../../../active/knowledge/nmosfet_terminal_promotion_preflight_2026_07_18.md).

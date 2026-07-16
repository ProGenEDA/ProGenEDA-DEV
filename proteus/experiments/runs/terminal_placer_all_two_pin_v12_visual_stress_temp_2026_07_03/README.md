# Terminal Placer All Two-Pin V12 Visual Stress Temp

## Scope

This pack contains one requested stress circuit: 20 of every currently profiled
two-pin family, passed through component placement, beautification, and the
shared terminal placer.

- Donor: `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
- Donor SHA256: `1222561d29622193d4eaa34aa830a341dee47abe376d1b971390dd6baad7958c`
- Runtime circuit donor dependency: false
- Component count: 380
- Bidirectional terminals: 760
- Short WIRE records: 760
- Final WIRE-address link allocations: 760
- Label jitters for low-16 WIRE-address uniqueness: 7
- Proteus status: static checks passed locally; manual Proteus open/render/sim
  check pending

## Families

RESISTOR, CAP, DIODE, VSINE, VSOURCE, CSOURCE, VPULSE, LED-RED, 1N4733A, 40EPS08, BZY88C, 1N4007, 1N4148, 1N6000B, BZX55C5V1, BZX79C5V1, FUSE, REALIND, CAP-ELEC

## V12 Focus

- LED-RED, 40EPS08, and FUSE now place terminal contacts one extra Proteus grid
  step outward while still using short WIRE records back to the exact component
  pins. This addresses the three crowded visuals reported after V11.
- Large mixed projects use deterministic final WIRE-address allocation with
  collision-safe terminal-label jitter. This keeps active terminal suffixes
  unique even when the serialized object stream exceeds 64 KiB.
- DIODE repeated selection skips the donor infrastructure key `D20`.
- FUSE repeated selection keeps the donor-native anonymous packets; validation
  no longer treats the repeated anonymous `FUSE` marker as a duplicate visible
  component reference.

## Proteus Check

Open:

`M01_ALL_TWO_PIN_20X_EACH_NATIVE_V12_VISUAL_STRESS/M01_ALL_TWO_PIN_20X_EACH_NATIVE_V12_VISUAL_STRESS.pdsprj`

Check for:

1. No Bad Object Record.
2. Exactly 20 components for each listed family.
3. Every component has two nearby bidirectional terminals.
4. LED-RED, 40EPS08, and FUSE terminals are visually less crowded than V11.
5. Every terminal has a short wire from the grid contact to the exact pin.
6. Netlist/simulation does not report detached terminal links.

# Terminal Placer All Two-Pin V11 Temp

## Scope

This pack uses the shared `src/proteusgen/component_terminal_placer.py` native
unit route for every currently profiled two-pin family.

- Donor: `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`
- Donor SHA256: `1222561d29622193d4eaa34aa830a341dee47abe376d1b971390dd6baad7958c`
- Terminal route: active `$TERBIDIR` + patched component pin-link field + donor
  schema 50-byte short `WIRE`, rebased from final `ROOT.DSN` addresses
- Runtime circuit donor dependency: false
- Component coordinate mutation in terminal stage: false
- Status: static validation passed locally; Proteus acceptance pending

## Families

RESISTOR, CAP, DIODE, VSINE, VSOURCE, CSOURCE, VPULSE, LED-RED, 1N4733A, 40EPS08, BZY88C, 1N4007, 1N4148, 1N6000B, BZX55C5V1, BZX79C5V1, FUSE, REALIND, CAP-ELEC

## Cases

- Solo cases: 19
- Mixed cases: 2
- Total generated cases: 38

## Scaled Solo Limits

Two families are intentionally 1x-only in this checkpoint because their repeated
selection is blocked before terminal placement:

- DIODE: 3x selection reaches D20, which is a display bridge/sentinel packet; 1x/2x remain valid from this donor.
- FUSE: Repeated FUSE packets are anonymous in the donor, so repeated refs are not a valid terminal-placer checkpoint until the component catalogue exposes stable unique FUSE identities.

## Proteus Test Order

1. Open every `S*_1X_NATIVE_V11.pdsprj` solo first.
2. Open the `S*_3X_NATIVE_V11.pdsprj` scaled solos next.
3. Open `M01_MIXED_ALL_TWO_PIN_19C_NATIVE_V11.pdsprj`.
4. Open `M02_MIXED_ALL_TWO_PIN_SAFE_SCALE_NATIVE_V11.pdsprj`.

For each case, check for Bad Object Record, missing rendered wires, detached
terminals, wrong endpoint orientation, and netlist/simulation terminal errors.

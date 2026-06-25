# Component Placer Pipeline

The component placer remains a removal-only donor-packet route. It selects
complete packets from trusted Proteus projects and emits them without synthetic
component construction, generated terminals, or generated wires.

Pipeline order:

1. User payload and count normalization
2. Component placer donor-packet selection
3. Component packet validation
4. Value-change planning
5. Wiring-intent planning
6. Beautifier/layout planning
7. Final `.pdsprj` binary emission

The post-placement stages are recorded in the sidecar manifest at
`<output>.pdsprj.manifest.json`.

## Current Binary Policy

- Value mutation is planned only; binary DSN/CDB value patching is not enabled.
- Wiring planning emits logical net intent only; Proteus wire records are not
  synthesized yet.
- `SWITCH` and `POT-HG` use the exact requested count. No dummy packet is
  generated or hidden. Under `layout.strategy=beautify`, every requested
  control is translated through its proven linked family coordinate plan.
- The rejected V3 runaway coordinate experiment used a `1,500,000,000`
  displacement; do not reintroduce that as a default.
- D20 display infrastructure is immutable. It retains its exact donor bytes and
  coordinates even when a legacy payload requests bridge hiding.
- When `layout.strategy` is `beautify`, visible packets, including controls, are
  translated by the shared packet-grid beautifier and recorded under
  `layout_plan.actual_binary_placements`.

## Controls

`SWITCH` and `POT-HG` requests select exactly the requested number of donor
packets. Legacy dummy strategy names remain accepted as compatibility aliases,
but normalize to exact-count placement. The placer does not add terminals or
wires for these controls. The beautifier moves the complete linked control
packet; it does not leave controls at donor coordinates.

## Display Bridge

When seven-segment display packets require the donor bridge record, the D20
bridge is selected as infrastructure and is not counted as a user-requested
diode. The current policy preserves D20 packet geometry and donor coordinates
exactly. Relocation and removal attempts remain rejected.

## Testing Notes

Every generated test pack should include a short human-readable description of
what the user is looking at and what should be checked in Proteus. This is now a
standing rule after the coordinate changer test feedback on 2026-06-21.

Each experiment folder must also contain a Markdown record. The record should
start with the test purpose, generation command/input, output file list, and
expected Proteus inspection. After user feedback, update the same file with
pass/fail results, exact Proteus errors, visual issues, observations, and the
next correction.

## Iteration Rule

Do not restart test generators from scratch after each failure. Keep the current
`.py` behavior under test as the baseline, copy it before changes, update the
copied behavior, and only promote/lock it after user Proteus acceptance. This
keeps the failure history traceable and prevents reintroducing already-fixed
packet handling bugs.

Beautifier work is family-specific. Reuse the shared arrangement algorithm, but
learn coordinate mutation per component/family and record the proven coordinate
fields before applying the method broadly.

## Rejected Passive Coordinate Attempt

`BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23` is rejected. User reported all
six passive-family cases failed with `LXLCORE.dll`.

Cause found by byte inspection: the fixed passive offset table moved packet
constants, not component coordinates. For main-mega passive packets, coordinate
mutation must parse length-prefixed text coordinate pairs and marker-body
coordinate pairs. Do not reintroduce the rejected fixed offsets as a fallback.

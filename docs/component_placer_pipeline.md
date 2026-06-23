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
- Control dummy coordinate mutation defaults to `hidden_coordinate_mode: none`.
- The rejected V3 runaway coordinate experiment used a `1,500,000,000`
  displacement; do not reintroduce that as a default.
- The current V4 beautifier experiment moves D20 display bridge infrastructure
  by a small `350,000` relative coordinate offset when explicitly requested.
- When `layout.strategy` is `beautify`, non-control visible packets are
  translated by the shared packet-grid beautifier and recorded under
  `layout_plan.actual_binary_placements`.

## Hidden Controls

`SWITCH` and `POT-HG` requests select one extra donor packet. The first packet is
marked as a hidden dummy control in the manifest. The beautifier owns long-term
dummy hiding, but current V4 tests do not send these controls to runaway
coordinates. The placer must not add terminals or wires for these controls.

## Display Bridge

When seven-segment display packets require the donor bridge record, the D20
bridge is selected as infrastructure and is not counted as a user-requested
diode. V4 moves D20 only by the explicit `display_small_relative` policy, which
uses a `350,000` coordinate-unit offset rather than a far hidden zone.

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

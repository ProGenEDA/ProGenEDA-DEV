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
- Beautifier coordinate mutation defaults to `hidden_coordinate_mode: none`.
- Focused coordinate tests may explicitly set `hidden_coordinate_mode` to
  `linked_relative` or `linked_absolute`.

## Hidden Controls

`SWITCH` and `POT-HG` requests select one extra donor packet. The first packet is
marked as a hidden dummy control in the manifest. The beautifier owns long-term
dummy hiding. The placer must not add terminals or wires for these controls.

## Display Bridge

When seven-segment display packets require the donor bridge record, the D20
bridge is selected as infrastructure and is not counted as a user-requested
diode. Any future D20 coordinate hiding must stay behind explicit beautifier
tests until Proteus acceptance.

## Testing Notes

Every generated test pack should include a short human-readable description of
what the user is looking at and what should be checked in Proteus. This is now a
standing rule after the coordinate changer test feedback on 2026-06-21.

# Circuit 180 OPAMP terminal-attachment trial

Purpose: test terminal attachment for the four generic `OPAMP` symbols that
were deliberately left bare by the accepted terminal route in Circuit 180.
This is an attachment-only experiment: it does not attempt logical circuit
routing or invent hidden supply pins.

## Inputs and evidence

- Placement request:
  `proteus/active/examples/proteus_200_circuits/placement_controls/circuit_180_op_amp_led_level_indicator.json`
- Authoritative OPAMP evidence:
  `proteus/active/evidence/donors/terminalized_catalogue_evidence/three_pin_regulator_control_symbol/OPAMP/OPAMP_user_terminalized_july04.pdsprj`
- Shared implementation:
  `proteus/active/src/proteusgen/component_terminal_placer.py`,
  `attach_mixed_component_and_catalogue_bidir_terminals_to_project`.

## Generated artifacts

- `C180_OPAMP_4X_MIXED_NATIVE_CATALOGUE_BARE.pdsprj` is the component-placer
  control, with no terminals.
- `C180_OPAMP_4X_MIXED_NATIVE_CATALOGUE_TERMINALIZED.pdsprj` is a fresh shared
  placer emission. It retains the existing native attachments and adds the
  donor-derived `IN+`, `IN-`, and `OUT` terminal-to-pin wire units for each of
  `U107`, `U108`, `U109`, and `U110`.

## Mechanical result

The shared terminal report passed before handoff:

- 19 terminalized components: 8 resistors, 3 voltage sources, 4 LEDs, and 4
  OPAMPs.
- 42 `$TERBIDIR` records and 42 nonzero short `WIRE` records.
- All terminal contacts grid-aligned.
- Every OPAMP input is oriented `1800`; every OPAMP output is oriented `0`.
- Object stream ends with the donor-proven double `FF` finalizer.

Proteus was launched with the terminalized file for user visual verification.
No shared terminal-route source code was changed by this experiment.

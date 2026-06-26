# Current Limits, Bridges, Costs, and Roadmap

This document is the compact operational truth for the current Progen
component-placer pipeline. It records what is accepted, what is merely under
test, and what technical cost each workaround introduces.

## Current Architecture

The active raw-component route is removal-only donor mutation:

```text
user request
  -> input/specification validator
  -> donor and packet selector
  -> component placer
  -> generated-output validator
  -> value changer
  -> beautifier
  -> wiring-intent planner
  -> later binary wiring/terminal stages
  -> final validator
```

The component placer does not synthesize components. It keeps complete packets
from a trusted mega donor and removes everything else.

## Accepted Limits

- Resistor-heavy placement has an accepted ceiling of `R91`. The donor contains
  more resistor evidence, but counts above 91 are not accepted as safe.
- `SWITCH` and `POT-HG` use exactly the requested count. No hidden or extra
  dummy control is generated.
- Seven-segment display requests carry one donor-derived `D20` bridge packet.
  `D20` is infrastructure and never counts toward a requested diode quantity.
- `D20` is immutable. The beautifier must not alter any of its coordinate
  fields. Its visible donor position is a known current limitation.
- Full donor `ROOT.CDB` is the accepted safe policy for current mega-donor
  component placement. CDB pruning is not the default.
- Component placement currently emits bare components only. It does not emit
  terminals, wires, or junctions.
- Value changing is currently proven only for same-length ASCII value tokens in
  selected packets and matching CDB property rows. `RESISTOR`, `CAP`,
  `CAP-ELEC`, `REALIND`, `POT-HG`, `VSOURCE`, and `CSOURCE` have static probe
  packs. `VSINE` and `VPULSE` value mutation is blocked until their property
  model is decoded.
- Bidirectional terminal placement is now a separate experimental stage. It can
  append donor-derived `$TERBIDIR` records beside proven two-pin packets, but it
  does not emit Proteus wires or guarantee electrical connection yet.
- Coordinate mutation is accepted only for families with a recorded parser.
  Rejected broad scans and guessed fixed offsets must not be used.

## Structural Bridges

### D20 display bridge

`D20` is the packet boundary that allows the accepted seven-segment rows to
coexist with ordinary component packets. Removing it or relocating it has
produced bad-object, DLL, or visual failures. Current policy: preserve its bytes
and donor coordinates exactly.

### Common-cathode final-row sentinel

Common-cathode display output currently retains a donor-final common-anode row
as stream-final infrastructure. It is not a user-requested display. This is a
format requirement discovered through controlled donor comparison.

### Full CDB/device skeleton

The mega route keeps the full donor CDB and device metadata because aggressive
row deletion repeatedly produced missing-model, duplicate-ID, and loader
failures. This is robust but increases output size.

### Passive power bridge

The older locked passive generators use a donor-derived power bridge and
ground endpoint records. That is separate from the current bare component
placer. Power and ground terminal placement will be reintroduced as its own
post-wiring stage.

### Same-name terminal bridge

Proteus connects same-name input, output, and bidirectional terminals. A later
fallback stage will exploit this when direct binary wire placement is unsafe or
when modular composition is preferable.

## Technical Costs

- **Output size:** full donor CDB metadata makes small generated projects much
  larger than their visible component count suggests.
- **Visible artifacts:** D20 and the common-cathode sentinel can remain visible
  until a proven hiding/removal method exists.
- **Donor ceiling:** generation cannot exceed the usable packet inventory of
  the selected donor.
- **Per-family research:** coordinate fields are learned and validated per
  family. This costs analysis time but prevents LXLCORE/VGDVC/ISIS failures
  caused by guessed byte offsets.
- **No arbitrary wiring yet:** the current placer proves component survival and
  movement, not complete electrical behavior.
- **Proteus remains authoritative:** static validators catch known structural
  failures, but final open/render/simulation acceptance still requires Proteus
  8.13 testing.
- **Legacy routes coexist:** older locked resistor/RCL/source/combinational
  generators remain useful while the unified placer pipeline matures.

## Validator Contract

Every pipeline stage must have two technical validators:

1. **Stage-output validator:** verifies the direct output of that stage.
2. **Cumulative regression validator:** verifies the stage plus every accepted
   rule from earlier stages.

Every stage also participates in:

- a user-specification validator;
- an information-completeness pass that decides whether missing information is
  safely auto-filled or must be asked from the user;
- a final whole-project validator before delivery.

The component placer now writes `generated_output_validator` into every
manifest. It verifies container members, exact counts, CDB/ref integrity,
full-CDB parity, coordinate-parser policy, reference preservation, and immutable
D20 behavior.

## Roadmap

1. Prove every IC family separately at 1x, 3x, 15x, and 25x.
2. Combine all accepted IC families at 3x, 15x, and 25x.
3. Combine all accepted IC and non-IC families at the same stress levels.
4. Implement arrangement-decision logic and the wiring architecture.
5. Expand the family-specific value/property changer beyond same-length tokens.
6. Promote bidirectional terminal placement after Proteus testing.
7. Emit actual Proteus wire records.
8. Place power and ground terminals with attached bidirectional terminals.
9. Place ordinary bidirectional terminals as a modular fallback to wires.
10. Add a connection decider that chooses direct wiring or same-name terminals
   per pin unless the user explicitly chooses.
11. Complete stage validators, user-intent validators, the information
    completer, and the final project validator.

The design goal is not merely “a file that opens.” It is a deterministic
compiler whose decisions can be inspected, validated, reproduced, and improved
without forgetting earlier failures.

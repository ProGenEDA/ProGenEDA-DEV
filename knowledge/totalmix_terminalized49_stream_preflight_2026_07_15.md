# All-49 totalmix stream repair preflight — 2026-07-15

## Authority and scope

The current authority is the user-resaved, visually working project:

`experiments/totalmix_gate_manual_terminal_donor_v1_temp_2026_07_15/terminalized49.pdsprj`

Its `ROOT.DSN` SHA-256 is
`3837d6d4d20e69ab0e9092d002e561213563eda1956f5562ea31724eccd4ffd7`.

The older `experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`
is **rejected stream evidence** for this repair. It has the same faulty post-U37
shape as the newly emitted wide candidate and therefore must not define the
runtime serializer.

No ROOT.CDB conclusion is made here; the user directed this diagnosis to ROOT.DSN.

## Complete relevant comparison

Both the rejected old `totalmix` and the rejected wide candidate serialize the
post-U37 cluster as one component run followed by large deferred attachment
zones:

```text
U37 → U66 → U69 → U73 → U77 → U198 → U476
    → all six quad-gate terminal/WIRE units
    → U202 → all 74HC04 units
    → U9 → U49 → their deferred units → U13
```

The user-resaved working donor does not have that shape. Its component-only
stream after U37 is:

```text
U37 → U9 → U69 → U77 → U66 → U476 → U198
    → U202:A/E/B/F/D → U13:B/A → U202:C → U73 → U49
```

It also proves that attachment records stay adjacent to their owning packet or
subpart boundary, rather than being collected as one all-gate tail. For example,
the working donor has a 74HC32 subpart reference followed by its associated
short WIRE and active terminal record before the next 74HC32 subpart. The
rejected stream instead emits all four 74HC32 subparts, then all twelve
terminal/WIRE pairs many bytes later.

The rejected wide candidate is inside the working donor's coordinate envelope
(for example U476 is around -6M,+45M), so distance is ruled out for the missing
gates/4511/74HC151 bodies.

## Unexplained differences collected before implementation

1. The mixed placer rewrites the placed-design component order through
   `backend_component_family_order`. This conflicts with the replaceable-stage
   contract and reproduces the rejected old stream.
2. The six DIL14 gate families and 74HC151 use a global tail zone even though
   their accepted solo routes prove packet-local component-plus-terminal/WIRE
   emission.
3. The all-family route therefore puts active terminal/link/WIRE structures far
   from the owning multi-part component packet, despite the loader/link suffixes
   being internally numerically consistent.
4. The old `totalmix` evidence was incorrectly treated as accepted. It is not
   sufficient to prove the current combined output; only the user-resaved donor
   is authoritative for this repair.

## Evidence-backed repair

Keep the existing shared terminal placer and all frozen two-pin/accepted solo
paths unchanged. For the all-49 combined route only:

1. preserve the incoming component-placer stream order;
2. serialize the affected clean-packet logic families immediately after their
   own patched packet using their already accepted solo terminal+short-WIRE
   units;
3. retain the existing terminal-leading (4511) and subpart-block (4027)
   mechanisms as local blocks; and
4. retain existing non-logic tail routes until their specific donor evidence
   requires a change.

This is catalogue/profile-driven behavior in the shared placer, not donor
packet copying or a component-specific generator.

## Required regression gate

Before handoff, regenerate one all-49 1x project from the locked mega donor and
mechanically prove: source component order is preserved; every 74HC00/02/04/08/
32/86/266/151 attachment is locally adjacent to its packet; every active link
is inside its owning packet; all 318 terminal contacts are grid aligned; every
short WIRE is nonzero and joins its terminal contact to the target pin. Then
run the delayed local Proteus open/cold-reopen gate on a disposable copy.

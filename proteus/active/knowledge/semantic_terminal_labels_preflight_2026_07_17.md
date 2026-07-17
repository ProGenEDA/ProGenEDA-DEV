# Semantic terminal-label preflight — 2026-07-17

## Scope

This change adds an optional logical-node label override to the existing shared
terminal placer. It does not alter pin geometry, terminal orientation, short
WIRE geometry, component link offsets, suffix allocation, packet order, or
final ROOT.DSN address rebasing.

## Authoritative evidence reviewed

- `C180_NATIVE_PLUS_OPAMP_TERMINALIZED.pdsprj` opened normally in local
  Proteus after the shared native-plus-catalogue route attached 42 terminals
  and 42 short WIREs.
- Its terminal report records the actual mismatch: OPAMP `U107` used generated
  labels `U107OUT`, `U107INP`, and `U107INN`, while the canonical Circuit 180
  specification assigns the corresponding visible pins to `O1`, `VIN`, and
  `GND`.
- The canonical Circuit 180 JSON preserves every source pin-to-net assignment.
  The source OPAMP supply pins `V+` and `V-` are intentionally absent from the
  present visible OPAMP catalogue geometry, so no terminal is invented for
  them.

## Required implementation invariants

1. Terminal labels are chosen before serializing the terminal record, never by
   post-hoc byte replacement.
2. The final existing ROOT.DSN rebasing stage continues to allocate active
   terminal/component-link suffixes from the final WIRE addresses.
3. A missing optional label override retains the exact existing label and
   serializer path for every accepted family.
4. The executable control contains only label metadata, never `nets`,
   `connections`, `wires`, or a claim of physical routing.
5. The projection maps source components to placed components by family-local
   source order and fails on a cardinality mismatch rather than guessing.
6. The regression checks must cover native two-pin labels, catalogue OPAMP
   labels, grid/nonzero-WIRE validation, and the Circuit 180 source mapping.
7. The catalogue-only writer must consume the same optional override map before
   it serializes labels, so a one-family OPAMP/LM317T/NMOSFET/POT-HG circuit
   cannot silently fall back to a donor label.

## Expected Circuit 180 visible OPAMP labels

`U1`: `IN+ -> VIN`, `IN- -> G0`, `OUT -> O1`; later OPAMP instances use the
same canonical nets (`VIN`, `T1`/`T2`/`T3`, `O2`/`O3`/`O4`). `G0` is the
existing normalized terminal name for canonical `GND`.

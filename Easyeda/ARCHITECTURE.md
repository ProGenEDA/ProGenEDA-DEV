# EasyEDA Pro Architecture

```text
Canonical JSON
  -> input normalizer and validator
  -> exact donor resolver
  -> source-pin resolver
  -> square-like schematic placer
  -> wire / terminal / combination planner
  -> donor-native schematic emitter
  -> footprint and pad mapper
  -> basic two-layer PCB placer/router
  -> native SQLite project writer
  -> structural/net/geometry/source/PCB validator
  -> .eprj + internal audit ZIP
  -> installed EasyEDA open/render acceptance
```

## Replaceable Contracts

`ir.py` owns the backend-neutral circuit contract. `donor_source.py` owns
read-only source extraction. Geometry stages consume only normalized
components, source body bounds, and source pin descriptors. The SQLite writer
does not infer electrical pin roles.

`geometry.py` places and routes schematic records. Physical wires may cross
other wires, but may not enter component bodies away from their intended pins.
Terminalized nets use copied source `netport-in` or `netport-out` components
and short orthogonal wire stubs. Combination-mode power nets are attempted as
physical routes first, then receive exactly one shared named terminal at the
route root. Only a failed power route falls back to endpoint terminals.

`native.py` clones a valid donor `.eprj`, removes unrelated example content,
copies only required source rows, and writes generated project/document rows.
The raw standard library and application are never placed in a generated
project or output archive.

`validator.py` reopens the emitted SQLite file and independently proves:

1. SQLite integrity and required native documents.
2. Exact component references, devices, values, and source pin existence.
3. Expected net membership from actual `WIRE`/`ATTR NET` and native net-port
   records.
4. No schematic component overlap or wire/body contact away from pins.
5. Source symbol and footprint payload hashes are unchanged.
6. When PCB is present: footprint instances, `PAD_NET`, nets, tracks, vias,
   outline, and pad-level physical connectivity.

The donor manifest records terminal packet types separately from terminal
instances. This keeps donor reuse deduplicated while preserving every emitted
net, endpoint, coordinate, and rotation for audit.

## PCB Scope

PCB generation is intentionally bounded to 24 physical components in the
first hardened profile. Power and ground use opposite bottom-layer rails with
native via pads; signal routes use obstacle-aware top-layer Manhattan routing
and may use the bottom layer when valid. Output is withheld on missing pad
mapping, footprint overlap, unroutable copper, or same-layer cross-net contact.

This is a useful MVP board generator, not a universal autorouter or production
manufacturing sign-off. EasyEDA DRC and human board review remain acceptance
steps.

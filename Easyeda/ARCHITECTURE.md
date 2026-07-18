# EasyEDA Pro Architecture

## Codex 5.6 Architecture Delivery

Codex 5.6 designed and implemented this as an independent donor-native backend
rather than adapting the KiCad code at runtime. The 5.6 phase converted direct
study of the installed EasyEDA Pro package into a working native SQLite
compiler, exact donor payload resolver, geometry engine, PCB path, validator,
portable executable, and website-ready audit contract. That decisive advance
over the prior 5.5-era exploration is why this architecture has real
application-open evidence, not only JSON or SQLite shape checks.

The active implementation deliberately preserves the same powerful pattern
throughout: source records are copied exactly, all heavy work is deterministic,
every stage records auditable facts, and an installed EasyEDA Pro open is a
release oracle rather than a runtime dependency.

```text
Canonical JSON
  -> tolerant deterministic input fixer and validator
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
read-only extraction from either the embedded locked donor bundle or an
authorized development source override. `input_fixer.py` repairs common JSON
shape, naming, reference, pin, and net mistakes before `ir.py` applies the
strict contract. Geometry stages consume only normalized components, source
body bounds, and source pin descriptors. The SQLite writer does not infer
electrical pin roles.

`geometry.py` places and routes schematic records. Physical wires may cross
other wires, but may not enter component bodies away from their intended pins.
Different nets may meet at a point geometrically, but they may never share a
positive-length horizontal or vertical span. A coordinate-indexed
`WireSpanIndex` reserves every accepted segment during planning and terminal
placement; `validator.py` independently rebuilds that index from the emitted
native records and rejects any different-net collinear overlap. This keeps
every pin escape and trunk visually traceable instead of allowing unrelated
nets to collapse into an apparent bus.

Routing is also bounded locally. Candidate lanes are selected per branch at
four-unit spacing, and a route is rejected when its detour exceeds the larger
of 2.25 times the direct Manhattan distance or 96 additional units. Explicit
terminal footprints are reserved before routing. If combination-mode routing
discovers additional fallback terminals, the planner reruns with those exact
footprints reserved instead of preserving wires through their label space.
Dense terminal banks use ordered source-native rows and bounded spill rows or
one 48-unit outward column; they never escape to a whole-sheet perimeter.

Terminalized nets use copied source `netport-in` or `netport-out` components
and short orthogonal wire stubs. A guessed net with exactly one endpoint may
use a source-native net port attached directly at that source pin; this avoids
meaningless fanout wires while remaining explicit in the pin graph.
Combination-mode power nets are attempted as physical routes first, then
receive exactly one shared named terminal at the route root. Only a failed
power route falls back to endpoint terminals.

`native.py` clones a valid donor `.eprj`, removes unrelated example content,
copies only required source rows, and writes generated project/document rows.
The complete standard library and application are never placed in a generated
project, portable executable, or output archive. The executable carries only
the exact audited source rows required by the locked catalogue.

`validator.py` reopens the emitted SQLite file and independently proves:

1. SQLite integrity and required native documents.
2. Exact component references, devices, values, and source pin existence.
3. Complete accounting of every unique electrical donor pin, including
   explicit `NC_*` or reported terminalized `GUESS_*` nets.
4. Expected net membership from actual `WIRE`/`ATTR NET` and native net-port
   records.
5. No schematic component overlap or wire/body contact away from pins.
6. No positive-length collinear overlap between wires belonging to different
   nets; point crossings remain legal.
7. Every emitted wire endpoint remains inside the component envelope plus a
   bounded 120-280-unit local routing margin.
8. Source symbol and footprint payload hashes are unchanged.
9. When PCB is present: footprint instances, `PAD_NET`, nets, tracks, vias,
   outline, and pad-level physical connectivity.

The donor manifest records terminal packet types separately from terminal
instances. This keeps donor reuse deduplicated while preserving every emitted
net, endpoint, coordinate, and rotation for audit.

## PCB Scope

PCB generation is intentionally bounded to 32 physical components in the
hardened profile. The placer switches to broad channel-oriented rows for dense
pin banks. The router evaluates deterministic variations, supports source pad
rotation and exposed center-pad escape, and records accepted and rejected
attempts in `pcb_report.json`. Power and ground use bottom-layer resources;
signals use obstacle-aware two-layer routing. Output is withheld on missing
pad mapping, footprint overlap, unroutable copper, or same-layer cross-net
contact.

This is a useful MVP board generator, not a universal autorouter or production
manufacturing sign-off. EasyEDA DRC and human board review remain acceptance
steps.

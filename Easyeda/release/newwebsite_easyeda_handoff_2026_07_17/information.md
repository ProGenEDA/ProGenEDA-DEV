# ProGenEDA EasyEDA Pro Information

## Current Product Scope

ProGenEDA EasyEDA Pro consumes one canonical circuit JSON and emits one native
`.eprj`. The same project contains the validated schematic and, when the
bounded physical contract passes, a basic two-layer PCB. The backend uses 59
logical catalogue names backed by 57 audited physical source families plus
native `GND` and `VCC` terminal families.

- Schematic input limit: 80 placed physical components.
- Basic PCB limit: 32 physical components.
- Routing modes: `combination`, `wire`, and `terminal`.
- Default routing mode: `combination`.
- Public output: one native `.eprj`.
- Private output: one audit ZIP containing every deterministic intermediate.
- Hosted generation and primary validation do not require EasyEDA installed.

## Architecture

```text
natural-language prompt or direct canonical JSON
-> deterministic input fixer and validator
-> catalogue and donor-source resolution
-> value editor
-> component placement and compact beautification
-> wire / terminal / combination planner
-> donor-native SQLite .eprj writer
-> optional bounded two-layer PCB compiler
-> source hash, SQLite, pin, netlist, geometry, and PCB validators
-> public .eprj + private audit ZIP
```

The website streams the executable's real eight stages. It does not estimate
completion from an animation. Direct JSON generation and the advanced JSON Lab
remain restricted to demo/admin accounts; guided editing exposes project names,
references, and catalogue-approved values while proving topology unchanged.

## Source Fidelity

Symbols, pins, devices, footprints, pads, terminals, and the blank project are
copied from the authorized EasyEDA Pro source package. The portable embeds only
the compact locked donor bundle needed by the supported catalogue, not the
desktop application or complete standard library. Generated outputs contain
the same project-native records a hand-authored EasyEDA project uses, together
with source payload hashes in the private manifest.

## Validation

Acceptance requires all of the following:

1. Input repair completes without unresolved structure.
2. Every component resolves to an exact locked source payload.
3. Every unique source electrical pin is assigned to a requested, `NC_*`, or
   explicitly reported guessed terminal net.
4. Native SQLite integrity and project/member relationships pass.
5. The parsed native pin graph exactly matches the expected input netlist.
6. Components do not overlap and wires avoid component bodies and foreign pins.
7. Different nets do not share collinear wire spans.
8. PCB output, when offered, passes pin-to-pad, placement, route, outline, and
   connectivity checks.

The locked corpus has 300 unique, descriptively named circuits: 30 practical
archetypes across 10 deployment profiles. It exercises all 59 logical entries,
4,670 component instances, and 11,440 nets. The shipping portable passed all
300 without input fixes, guessed nets, netlist failures, pin omissions, or PCB
withholding.

## Current PCB Boundary

The PCB stage proves shared-JSON schematic-plus-board generation. It is not a
universal production autorouter. Current output is bounded to source-backed
footprints, at most 32 physical parts, a closed two-layer board outline, and
routes that pass the internal physical validator. No copper pours, controlled
impedance, differential-pair constraints, length matching, thermal analysis,
or manufacturing sign-off are claimed.

## Future Direction

Future releases can add source-audited component families, larger physical
limits, stronger dense-board routing, board-rule profiles, pours, differential
pairs, impedance and length constraints, Gerber/BOM/position export policies,
and direct native Altium support. The canonical circuit JSON and replaceable
backend stage contracts remain stable so those additions do not replace the
input model.

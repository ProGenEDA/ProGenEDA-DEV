# Altium Architecture

## Product Path

The product path is direct and backend-independent:

```text
canonical JSON
  -> input fixer / AltiumCircuit IR / value editor
  -> source catalogue resolution / component selector
  -> placed-design contract
  -> arrangement decider / beautifier
  -> wire planner / terminal placer / routing validator
  -> direct native ASCII SchDoc writer
  -> output packager / PCB decision
  -> saved-file graph, geometry, and ZIP package final validator
```

No stage generates or consumes EasyEDA `.eprj` data. The Chameleon bridge is
kept outside this path as a local research utility only.

## Implemented Contracts

| Stage | Input | Output | State |
| --- | --- | --- | --- |
| Input fixer | loose JSON | canonical JSON, explicit `GUESS_TERMINAL_*` repairs | implemented |
| Canonical JSON validator | fixed canonical JSON | normalized `AltiumCircuit` | implemented |
| Value editor / validator | component values | normalized safe values and report | implemented |
| File name decider | normalized project identity | safe `.PrjPcb` / `.SchDoc` names | implemented |
| Source catalogue | locked native seed | source templates, aliases, pins, directions, bounds | implemented |
| Component selector | `AltiumCircuit` + source catalogue | resolved native pin/net contract | implemented |
| User specification validator | canonical request + source selection | intent-preservation report | implemented |
| Component placer | resolved templates | deterministic non-overlapping placed-design contract | implemented |
| Placement validator | placed-design contract | collision/pin/net report | implemented |
| Arrangement decider | placed-design contract | connectivity-aware square coordinate plan | implemented |
| Beautifier | coordinate plan | moved placed-design contract | implemented |
| Beautifier validator | beautified placed design | post-edit placement report | implemented |
| Routing decider | routing mode + source facts | explicit wire/terminal/combination policy | implemented |
| Wire planner | pins, bounds, nets | orthogonal source-pin escape routes | implemented bounded baseline |
| Terminal planner | unresolved or selected nets | stem wires plus native `RECORD=25` labels | implemented |
| Routing validator | pure routing contract | geometry, graph, terminal-policy report | implemented |
| Schematic writer | source records + plan | fresh ASCII `.SchDoc` | implemented |
| Direct validator | saved `.SchDoc` + expected contract | pin/net/geometry validation report | implemented |
| Project writer | schematic metadata | `.PrjPcb` and ZIP project artifact | implemented baseline |
| Output packager | project + stage evidence | user ZIP and private internal ZIP | implemented |
| PCB decision | resolved source/pin facts | explicit qualified/unqualified PCB outcome | implemented boundary |
| PCB compiler | schematic pin/pad contract | `.PcbDoc` | not implemented |
| Desktop acceptance | disposable project copy | open/render/compile evidence | pending Altium installation |

## Source Catalogue

`source_catalogue.py` loads
`source_pack/donors/logic_trainer_ascii_seed.SchDoc` and pins it to SHA-256:

```text
bfc862eff7dc73bcc787fde8d6fdfc37e283b6249a6e029ee946abf681c2dde8
```

The catalogue extracts complete `RECORD=1` component blocks and rejects a
template if a sheet, wire, or net-label record leaked into that block. For each
template it derives:

- library reference and complete native record payload;
- source owner/index relationships required for rebasing;
- native pin designator and human-readable pin aliases;
- pin location and direct escape direction from `PINCONGLOMERATE`;
- visible component bounds from source geometry; and
- source-native sheet, wire (`RECORD=27`), and net-label (`RECORD=25`) records.

The writer copies those records into a fresh document, changes only safe
identity/value/coordinate fields, and allocates fresh owner and sheet indexes.
It never draws a replacement symbol or guesses a pin map.

## Routing Policy

Every input source pin must be assigned to an explicit net. `NC_*` names are
intentional no-connect pins. All other nets use one of three policies:

1. **Wire**: source-direction pin escapes plus deterministic orthogonal lanes.
   The generator rejects a candidate if it enters a component body, overlaps
   another net, or creates an unsafe endpoint/T contact. A pure interior
   perpendicular crossing is permitted because this pilot does not emit a
   junction record.
2. **Terminal**: each endpoint gets a short source-direction stem and a native
   Altium net label at its end.
3. **Combination**: route each net atomically. If any branch cannot be routed,
   discard that net's partial route and terminalize the entire net. A strict
   `wire` request never silently changes mode.

The validator replays the emitted wire graph. For terminalized nets it also
requires the exact count of labels, proves each label lies on a physical stem,
and merges only labels with the declared same net name.

## Validation Layers

1. JSON references, pins, and declared net membership agree.
2. Every logical pin resolves to a source-native physical pin.
3. Every source pin is explicitly connected or marked `NC_*`.
4. Saved `.SchDoc` record count, component references, pins, and indexes match
   the expected contract.
5. Component bodies do not overlap and wires do not cross/touch bodies except
   their source-directed pin escape.
6. Saved wire/label graph exactly covers expected nets without shorts.
7. ZIP package structure and `.PrjPcb` document references are valid.
8. Altium Designer open/render/compile is required before a desktop-qualified
   release claim.

## Conversion Engine

The installed Chameleon package exposes Altium encoder/decoder registrations,
so `conversion_engine.py` remains useful for inspecting the local registry and
researching source formats. It is intentionally not imported by the direct
generator.

Its raw ASCII `.SchDoc` round-trip was found to be lossy: it emitted a
schematic fragment with wire records but omitted component records and a
project descriptor. It cannot therefore validate, substitute for, or rewrite
the direct generator's output.

## Expansion Rules

Adding an Altium family requires one source-backed catalogue entry and focused
tests, not a component-specific writer. A future direct PCB stage requires
separate donor evidence for the actual `.PcbDoc` grammar, board outline,
stackup, rules, footprints, pad mapping, and track/pour semantics. No PCB file
will be emitted before that evidence and a matching validator exist.

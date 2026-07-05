# Main JSON Catalog 100 Lock - 2026-07-05

## Purpose

This report records the first locked 100-circuit main-JSON catalogue for the
KiCad pipeline and the proof runs that consumed it through terminal-only and
combination generation.

The main JSON is now treated as the only generator input. Current supported
components must not need extra side files from the caller. Future stages should
read the stage contracts, expected netlist, routing policy, component summaries,
and layout intent from the same JSON document.

## Locked Input

Final accepted locked catalogue:

```text
kicad/examples/final_json_run_2026_07_05_204653_main_json_catalog_100_v3_locked
```

Contents:

- 100 deterministic main JSON files, `MJ001` through `MJ100`.
- 8,416 requested components.
- 6,694 compiled expected nets.
- 26,293 expected endpoints.
- All records use `routing.mode = "combination"`.
- Combination high-fanout policy is 6 or more endpoints, matching the
  user-requested "over 5" rule.
- Each JSON includes `main_json_contract`, `routing`, `layout_intent`,
  `expected_netlist`, and `stage_contracts`.

The earlier folder below is intentionally kept as a failed record:

```text
kicad/examples/final_json_run_2026_07_05_195612_main_json_catalog_100_v1_locked
kicad/examples/final_json_run_2026_07_05_201238_main_json_catalog_100_v2_locked
```

It exposed invalid catalogue assumptions: unresolved connector-style aliases,
LM358 virtual bias endpoints, and repeated logical Arduino aliases that mapped
multiple different nets onto the same physical pins. These were fixed in later
catalogue records instead of editing the v1 record. The v2 record was
electrically correct but still carried a stale high-fanout policy value of 5;
the v3 record is the accepted lock because its JSON policy matches the
combination generator behavior.

## Terminal Proof

Final accepted terminal-only project run:

```text
kicad/examples/final_json_terminal_project_run_2026_07_05_204701_main_json_catalog_100_terminal_v6_threshold6_contract
```

Result:

- 100 generated KiCad projects.
- 9,540 schematic symbol instances.
- 26,293 terminal/local-label objects.
- 0 wire objects, by design for terminal-only mode.
- 0 unresolved pins.
- 0 component body overlaps.
- 0 geometry violations.
- 0 deferred, unrouted, or partial nets.
- 0 strict-wire violations.
- 0 local expected-net failures.
- 0 merged nets.
- 0 power/ground shorts.

Terminal placement now prefers direct labels at the exact pin point. Short
stubs are only a collision fallback, so terminal mode stays terminal-like
instead of becoming hidden wire mode.

Intermediate terminal records are kept as evidence:

```text
kicad/examples/final_json_terminal_project_run_2026_07_05_200317_main_json_catalog_100_terminal_v2_fast
kicad/examples/final_json_terminal_project_run_2026_07_05_201245_main_json_catalog_100_terminal_v3_fixed
kicad/examples/final_json_terminal_project_run_2026_07_05_201731_main_json_catalog_100_terminal_v4_clean
kicad/examples/final_json_terminal_project_run_2026_07_05_202139_main_json_catalog_100_terminal_v5_direct_labels
```

The v2 run proved the terminal fast path but failed because the v1 catalogue
still requested unsupported aliases and conflicting physical pins. The v3 run
fixed pin resolution but still had body overlaps and one label collision. The
v4 run fixed body overlaps but showed that long terminal stubs can create
unnecessary geometry violations. The v5 run was electrically clean from the v2
catalogue. The v6 run supersedes it because it consumes the accepted v3
main-JSON contract.

## Combination Proof

Final accepted combination project run:

```text
kicad/examples/final_json_combination_project_run_2026_07_05_204835_main_json_catalog_100_combination_v5_threshold6_contract
```

Result:

- 100 generated KiCad projects.
- 9,540 schematic symbol instances.
- 2,784 KiCad wire objects.
- 25,348 terminal/local-label objects.
- 0 unresolved pins.
- 0 component body overlaps.
- 0 deferred, unrouted, or partial nets.
- 0 geometry violations.
- 0 strict-wire violations.
- 0 local expected-net failures.
- 0 merged nets.
- 0 power/ground shorts.

Combination policy:

- Honor `routing.mode` from main JSON when no CLI override is supplied.
- Terminalize power and ground nets before wire planning.
- Terminalize high-fanout nets with 6 or more endpoints.
- Route a capped visible-wire subset first.
- Convert route-limit leftovers, invalid emitted routes, and failed routes to
  terminal labels instead of emitting disconnected or faulty circuits.
- Place terminal labels after wiring, so wiring can still drive component
  movement and arrangement decisions.

The default combination cap for this proof is 8 physical routed nets per
circuit. This keeps combination mode fast and reliable while preserving a small
visible-wire sample in each generated schematic.

The earlier clean combination run below is kept as a superseded record because
it consumed the v2 catalogue with the stale high-fanout policy metadata:

```text
kicad/examples/final_json_combination_project_run_2026_07_05_203134_main_json_catalog_100_combination_v4_route_cap_8
```

## Validation Commands

Focused checks used for this lock:

```text
PYTHONPATH=. .venv/bin/python -m pytest \
  kicad/tests/test_final_circuit_builder.py::FinalCircuitBuilderTests::test_main_json_catalog_100_compiles_to_locked_combination_inputs \
  kicad/tests/test_kicad_wire_maker.py::KiCadWireMakerTests::test_generate_terminal_projects_from_final_json_uses_terminal_placer_and_passes_netlist \
  -q
```

Compile checks:

```text
PYTHONPATH=. .venv/bin/python -m compileall -q \
  kicad/pipeline/final_circuit_builder.py \
  kicad/pipeline/kicad_wire_maker.py \
  kicad/pipeline/wire_planner.py \
  kicad/pipeline/terminal_placer.py
```

Full 100-project evidence is stored in each run's `run_manifest.json`.

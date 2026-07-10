# Input JSON Validator/Fixer

Canonical module:

```text
kicad/pipeline/input_json_validator_fixer.py
```

This stage is backend-neutral where possible and deterministic. It is not
special-cased to the 500-circuit stress file. Its job is to accept loose main
JSON, repair safe structural problems, and emit canonical CircuitIR main JSON.

The 500-circuit stress file is only a test corpus. The fixer itself is a
general rules engine backed by:

- the supported component catalogue and aliases,
- KiCad source-backed symbol pin names/numbers where available,
- explicit electronics rail rules for GND/AGND/DGND/VSS/COM, 3V3/VDDIO,
  5V/VCC/VBUS, VIN/VBAT/VRAW, and VOUT,
- component-family pin-role rules for common MCUs, sensors, logic ICs,
  interfaces, power devices, sources, connectors, and passives,
- endpoint and pin-normalization rules that keep electrically different pins
  distinct, including case-sensitive source-symbol pins such as 7447 `A`
  versus `a`.

## Repair Rules

- Normalize project/circuit metadata.
- Normalize component `id`/`ref`/`kind`/`type`/`value`/`role`/`block`.
- Infer unsupported or missing component kinds from catalogue aliases,
  component reference names, and observed pins.
- Add missing component records when nets reference a known `REF.PIN`.
- Normalize `nets`, `expected_netlist`, and component `pins` into one net map.
- Convert dict-style endpoints into `REF.PIN` form.
- Merge duplicate endpoint/net ownership through the same compiler repair path
  used by the final JSON builder.
- Drop singleton nets instead of pretending they are valid multi-endpoint
  connectivity.
- Build `components[].pins`, `expected_netlist`, `stage_contracts`,
  `generation_notes`, and `validation`.

## Guess-Terminal Rule

If the fixer invents or renames a net, the net must be visibly marked as a
guess and terminalized:

```text
GUESS_TERMINAL_*
```

The fixer also uses the component catalogue pin model plus common electronics
rules to infer missing power/ground rail endpoints. These inferred rails are
only kept when at least two endpoints exist, and they are always listed under:

```json
{
  "routing": {
    "terminal_policy": {
      "terminal_nets": ["GUESS_TERMINAL_GND"],
      "guessed_terminal_nets": ["GUESS_TERMINAL_GND"]
    }
  }
}
```

That means the router and wire maker must treat them as terminal/local-label
nets in combination or terminal mode. The generator must not silently draw
guessed nets as confidently planned user wires.

If a guessed rail exists, ordinary rail-like names such as `GND`,
`NET_BOARD_GND`, `VCC`, `NET_USB_5V`, or `NET_SENSOR_3V3` are merged into the
matching `GUESS_TERMINAL_*` net. This prevents a repaired circuit from carrying
two separate names for the same inferred rail and makes the guess visible to
the downstream metadata and terminal policy.

The fixer also checks alias-equivalent physical pins. If an inferred
`GUESS_TERMINAL_*` endpoint and an explicit net both claim the same physical pin
through aliases such as `S` and `SOURCE`, the guessed endpoint is dropped and
the explicit net wins. Multiple explicit nets on the same physical pin are
reported rather than guessed away.

## Variation Metadata

`generation_variation` is preserved when present. This lets the executable
variation runner validate/fix cloned JSON without losing the selected profile,
seed, source circuit id, or `disable_adaptive_cap` marker. The field changes
layout behavior only; it does not change component identity or expected nets.

## CLI

Fix one JSON file:

```bash
PYTHONPATH=. python -m kicad.pipeline.input_json_validator_fixer fix-json input.json --output fixed.json --report report.json
```

Compile arrow-node text:

```bash
PYTHONPATH=. python -m kicad.pipeline.input_json_validator_fixer compile-node-spec 500_complex_circuit_netlists.txt --output-dir fixed_json --report report.json
```

The arrow-node compiler is allowed to infer components from names and pins, but
the validator/fixer itself remains general and should be used for arbitrary
main JSON before generation.

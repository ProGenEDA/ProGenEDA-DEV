# Mixed R/C/L JSON Input

The locked mixed resistor/capacitor/inductor generator reads strict group-based JSON. It does not parse free-form English.

Run:

```powershell
proteusgen generate-mixed-rcl path\to\mixed_rcl.json --outdir out\mixed_rcl
```

## Contract

```json
{
  "schema_version": "mixed-rcl-circuit-ir/v0.1",
  "generator_target": "proteus-8.13-mixed-rcl-locked",
  "project": {
    "name": "MY_RCL_CIRCUIT",
    "output_basename": "MY_RCL_CIRCUIT",
    "base": "E001_EMPTY_BASE",
    "units": "proteus_internal"
  },
  "groups": [
    {"mode": "RCL", "start": "V0", "end": "N1"},
    {"mode": "RC", "start": "N1", "end": "G0"}
  ],
  "component_values": {
    "R1": "10k",
    "C1": "1uF",
    "L1": "5mH"
  },
  "metadata": {
    "description": "Optional notes from the planner."
  }
}
```

## Rules

- `mode` must be one of `RCL`, `RC`, `LC`, `RL`, `C`, `R`, or `L`.
- `start` and `end` must be exactly two ASCII characters, for example `V0`, `G0`, `N1`, `M0`.
- `V0` is the power net. The generator emits one donor-derived `$TERPOWER -> $TERBIDIR(V0)` bridge.
- `G0` is the ground net. Supported group endpoints to `G0` emit ground terminals.
- Every ordinary group endpoint uses a role-oriented bidirectional terminal.
- Omitted layout defaults to the deterministic compact `beautify` strategy.
- By default the generator uses accepted donor values: resistors `10k`, capacitors `1uF`, inductors `5mH`.
- `component_values` is optional. Keys are generated two-character refs such as `R1`, `C1`, and `L1`.
- Current value overrides must fit the existing donor record sizes. Use exactly 3 ASCII characters for resistors, capacitors, and inductors.
- Use compact Proteus value text when needed: `10R` for 10 ohm, `50R` for 50 ohm, `4u7` for 4.7 uF, `10u` for 10 uF, and `10m` for 10 mH.
- Geometry is donor-derived horizontal group blocks; electrical topology is expressed by repeated terminal labels.

The accepted 21-rule topology is encoded as:

```json
[
  {"mode": "RCL", "start": "V0", "end": "D1"},
  {"mode": "RC", "start": "D1", "end": "D2"},
  {"mode": "LC", "start": "D2", "end": "M0"},
  {"mode": "RCL", "start": "V0", "end": "E1"},
  {"mode": "RL", "start": "E1", "end": "E2"},
  {"mode": "RC", "start": "E2", "end": "M0"},
  {"mode": "RCL", "start": "M0", "end": "F1"},
  {"mode": "LC", "start": "F1", "end": "F2"},
  {"mode": "RL", "start": "F2", "end": "G0"}
]
```

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
  "metadata": {
    "description": "Optional notes from the planner."
  }
}
```

## Rules

- `mode` must be one of `RCL`, `RC`, `LC`, `RL`, or `C`.
- `start` and `end` must be exactly two ASCII characters, for example `V0`, `G0`, `N1`, `M0`.
- `V0` is the power net. The generator emits one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge.
- `G0` is the ground net. Supported group endpoints to `G0` emit ground terminals.
- The generator uses fixed accepted values in this scope: resistors `10k`, capacitors `1uF`, inductors `5mH`.
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

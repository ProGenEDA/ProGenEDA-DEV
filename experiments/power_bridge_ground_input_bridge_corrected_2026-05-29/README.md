# Corrected Power Bridge + Ground Input-Bridge Attempts

## Status

Experimental for T03/T04. T01/T02 are included as known-good references.

## Reason

The previous improved T03/T04 likely used the wrong attached-terminal record. It converted a donor output-terminal record into an input-terminal record. This corrected pack uses a real V9 input-terminal template for the attached ground-node terminal.

## Corrected method

```text
Power bridge:
exact working POWER_T10 donor bridge core

Ground bridge:
real V9 input terminal labelled G0
real V9/output-family ground terminal labelled G0
donor bridge wire patched between them
```

Actual ground bridge order:

```text
input terminal G0
ground terminal G0
wire
```

## Location correction

```text
6R ground bridge anchor:  x=-4572000, y=-2032000
R21 ground bridge anchor: x=10668000, y=1016000
```

## Generated attempts

```text
REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
REF_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
CORRECTED_T03_6R_GROUND_INPUT_BRIDGE_V9_TEMPLATES
CORRECTED_T04_R21_GROUND_INPUT_BRIDGE_V9_TEMPLATES
```

## Output ZIP

```text
filename: POWER_BRIDGE_GROUND_INPUT_BRIDGE_CORRECTED_ATTEMPTS_2026_05_29.zip
size_bytes: 166086
sha256: 69f0e2e479841805fd38947be39e788009b6528013d16cb5840382c34741c483
```

## Generator script

```text
filename: generate_power_bridge_ground_input_bridge_corrected_attempts.py
size_bytes: 10558
sha256: 0469ba5c3ccacff59e7fb62837dec1836293b7a579aab141f829f11d9c074d27
```

## Test order

```text
1. REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/CONTROL_E001_EMPTY_BASE.pdsprj
2. REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
3. REF_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE/REF_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
4. CORRECTED_T03_6R_GROUND_INPUT_BRIDGE_V9_TEMPLATES/CORRECTED_T03_6R_GROUND_INPUT_BRIDGE_V9_TEMPLATES.pdsprj
5. CORRECTED_T04_R21_GROUND_INPUT_BRIDGE_V9_TEMPLATES/CORRECTED_T04_R21_GROUND_INPUT_BRIDGE_V9_TEMPLATES.pdsprj
```

## Decision rule

If corrected T03/T04 work, lock ground input-bridge method. If they fail, stop bridge work and keep the locked power-bridge plus ground-shortwire method.

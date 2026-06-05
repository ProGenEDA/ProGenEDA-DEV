# Appended Power Bridge + Ground Input-Bridge Attempts

## Status

Experimental for T03/T04, pending Proteus test.

T01/T02 are included again as known-good references.

## Why this exists

The previous corrected T03/T04 showed only terminals and no resistor network. The problem was not just terminal type. The experimental ground bridge was placed before the normal resistor stream:

```text
00 + power bridge + ground bridge + normal resistor stream
```

Proteus displayed the bridge objects but did not continue into the resistor network correctly.

## New correction

This attempt preserves the known-good object order first:

```text
00 + exact working power bridge + normal resistor stream + experimental ground input bridge
```

So the resistor network is parsed before the experimental ground bridge.

## Ground bridge structure

The experimental ground bridge uses:

```text
real V9 input terminal labelled G0
real output-family ground terminal labelled G0
donor compact bridge wire between them
```

Object order at the end of the stream:

```text
$TERINPUT(G0)
$TERGROUND(G0)
WIRE
```

## Generated attempts

```text
REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
REF_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
APPEND_T03_6R_GROUND_INPUT_BRIDGE_AFTER_NETWORK
APPEND_T04_R21_GROUND_INPUT_BRIDGE_AFTER_NETWORK
```

## Output ZIP

```text
filename: POWER_BRIDGE_GROUND_INPUT_BRIDGE_APPENDED_ATTEMPTS_2026_05_29.zip
size_bytes: 167614
sha256: 06fe152f2ff477875de3af5432f2c76bf6305be0d71bf2201859a8689617a8d1
```

## Generator script

```text
filename: generate_power_bridge_ground_input_bridge_appended_attempts.py
size_bytes: 16643
sha256: 2eda013c1dd69841344a209b2ae527ec5993ddfa0bf82911d57d3c17ff84c1f0
```

## Test order

```text
1. REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/CONTROL_E001_EMPTY_BASE.pdsprj
2. REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/REF_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
3. REF_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE/REF_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
4. APPEND_T03_6R_GROUND_INPUT_BRIDGE_AFTER_NETWORK/APPEND_T03_6R_GROUND_INPUT_BRIDGE_AFTER_NETWORK.pdsprj
5. APPEND_T04_R21_GROUND_INPUT_BRIDGE_AFTER_NETWORK/APPEND_T04_R21_GROUND_INPUT_BRIDGE_AFTER_NETWORK.pdsprj
```

## Decision rule

```text
If APPEND_T03/T04 work: lock appended ground input bridge.
If APPEND_T03/T04 fail: stop ground bridge work and use final/power_bridge_ground_shortwire_method.md only.
```

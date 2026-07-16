# Clean Power-Bridge + Ground-Terminal Attempts

## Status

Experimental, pending user test in Proteus.

## Why this exists

The previous fixed terminal-bridge pack still gave VGDVC errors. A closer comparison against the user-confirmed working `POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT` showed the real issue was not only the missing leading `00` byte.

## Root cause from byte comparison

The user-confirmed working power donor bridge has this object-stream pattern:

```text
OBJECT DATA
00
<exact 255-byte donor bridge core>
<normal first V9 terminal record starts here>
```

In the working file, the first normal `$TERINPUT` marker appears at offset:

```text
270
```

The broken fixed pack placed the first normal `$TERINPUT` marker at offset:

```text
283
```

That means the donor bridge area was 13 bytes too long / the bridge boundary was wrong. Proteus then parsed object records incorrectly and produced VGDVC errors.

## Corrected clean method

This clean pack extracts the exact reusable bridge core from the already working `POWER_T10` generated project:

```text
bridge_core = object_stream[1:256]
```

Then builds new object data as:

```text
00 + exact_bridge_core + normal_v9_object_stream[1:]
```

For the risky ground-bridge experiment:

```text
00 + exact_power_bridge_core + experimental_ground_bridge_core + normal_v9_object_stream[1:]
```

## Generated attempts

```text
CLEAN_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
CLEAN_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
CLEAN_T03_6R_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
CLEAN_T04_R21_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
```

## Recommended test order

Test T01/T02 first.

```text
T01/T02:
Power = exact donor bridge core from working POWER_T10
Ground = locked short-wire endpoint
```

T03/T04 are still risky.

```text
T03/T04:
Power = exact donor bridge core from working POWER_T10
Ground = experimental bridge made by reusing the power-layout bridge core with $TERGROUND
```

## Output ZIP

```text
filename: POWER_BRIDGE_GROUND_TERMINAL_CLEAN_ATTEMPTS_2026_05_29.zip
size_bytes: 150097
sha256: 12e253bbb9112778883b3103479f074346ad5fdbf0aeb8090c37a243d87d2aaf
```

## Generator script

```text
filename: generate_power_bridge_ground_terminal_clean_attempts.py
size_bytes: 9909
sha256: 69fc401880de135d85025d9eb6a17ad9ded7ebd7afd5d61fa6fd83c1ea11d5eb
```

Stored as:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_power_bridge_ground_terminal_clean_attempts.py.b64.txt
```

## Decision rule

```text
If CLEAN_T01/T02 work, lock power donor bridge + ground short-wire as the preferred visual method.
If CLEAN_T03/T04 fail, reject ground bridge and keep ground short-wire only.
```

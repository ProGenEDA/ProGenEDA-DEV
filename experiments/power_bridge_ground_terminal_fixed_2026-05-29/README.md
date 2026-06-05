# Fixed Power-Bridge + Ground-Terminal Attempts

## Status

Experimental, pending user test in Proteus.

## Why this fixed pack exists

The earlier `POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip` opened as blank / missing circuit.

Root cause:

```text
The OBJECT DATA section was missing the required leading 00 byte before the donor bridge cluster.
```

Correct object stream prefix:

```text
OBJECT DATA 00 <donor bridge cluster> <normal resistor object stream without its own leading 00>
```

Broken object stream prefix:

```text
OBJECT DATA <donor bridge cluster> <normal resistor object stream without leading 00>
```

## Fix applied

The script now does:

```text
object_chunk = 00 + power_bridge_cluster + normal_resistor_chunk[1:]
```

or, for the experimental ground bridge:

```text
object_chunk = 00 + power_bridge_cluster + ground_bridge_cluster + normal_resistor_chunk[1:]
```

## Generated attempts

```text
TERM_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
TERM_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
TERM_T03_6R_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
TERM_T04_R21_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
```

## Recommended tests

Test T01/T02 first.

```text
T01/T02 = likely useful method:
Power uses donor bridge.
Ground uses locked short-wire endpoint.
```

T03/T04 are still risky:

```text
T03/T04 = experimental ground bridge using power bridge layout with $TERGROUND.
```

## Output ZIP

```text
filename: POWER_BRIDGE_GROUND_TERMINAL_FIXED_ATTEMPTS_2026_05_29.zip
size_bytes: 171585
sha256: 425147074434f122c917fefaf2783688b9beee2468dec2f80ef547337a8a43cb
```

Reconstruct from GitHub Base64 chunks:

```bash
cat experiments/power_bridge_ground_terminal_fixed_2026-05-29/artifacts/POWER_BRIDGE_GROUND_TERMINAL_FIXED_ATTEMPTS_2026_05_29.zip.b64.part*.txt | base64 -d > POWER_BRIDGE_GROUND_TERMINAL_FIXED_ATTEMPTS_2026_05_29.zip
sha256sum POWER_BRIDGE_GROUND_TERMINAL_FIXED_ATTEMPTS_2026_05_29.zip
```

## Generator script

```text
filename: generate_power_bridge_ground_terminal_fixed_attempts.py
size_bytes: 15686
sha256: 72ce8c7ad06daf984839b806716481cab5b5032dda969df1deac9edb2fadf171
```

Stored as:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_power_bridge_ground_terminal_fixed_attempts.py.b64.txt
```

## Test order

```text
1. TERM_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/CONTROL_E001_EMPTY_BASE.pdsprj
2. TERM_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/TERM_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
3. TERM_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE/TERM_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
4. TERM_T03_6R_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE/TERM_T03_6R_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE.pdsprj
5. TERM_T04_R21_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE/TERM_T04_R21_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE.pdsprj
```

## Decision rule

```text
If T01/T02 work: lock power donor bridge + ground short-wire endpoint.
If T03/T04 work: investigate ground bridge further.
If T03/T04 fail: reject ground bridge and keep ground short-wire only.
```

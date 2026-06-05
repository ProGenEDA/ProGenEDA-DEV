# Power + Ground Short-Wire Endpoint Attempts

## Status

Experimental until user tests in Proteus.

This attempt uses only the two methods already confirmed as working:

```text
Power:  $TERPOWER(V0)  -> short wire -> resistor pin
Ground: $TERGROUND(G0) -> short wire -> resistor pin
```

No terminal bridge method is used.

## Why this should be the proper combined attempt

Previous terminal-bridge attempts for ground produced bad object records or blank sheets. Those bridge methods are rejected.

This pack instead combines only the locked endpoint methods:

```text
$TERPOWER replaces $TERINPUT at powered left endpoints.
$TERGROUND replaces $TEROUTPUT at grounded right endpoints.
```

Both replacements are marker-length safe in the known endpoint families:

```text
$TERINPUT  = 9 bytes
$TERPOWER  = 9 bytes

$TEROUTPUT = 10 bytes
$TERGROUND = 10 bytes
```

## Generated attempts

```text
BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT
BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT
```

## 6R topology

```text
R1: V0 - N1   power endpoint
R2: N1 - N2
R3: V0 - N2   power endpoint
R4: N2 - N3
R5: N3 - G0   ground endpoint
R6: V0 - G0   power endpoint + ground endpoint
```

Power terminal count:

```text
3
```

Ground terminal count:

```text
2
```

## R21 topology summary

```text
Branch A starts at V0 through R1.
Branch B starts at V0 through R8.
Tail ends at G0 through RL.
```

Power terminal count:

```text
2
```

Ground terminal count:

```text
1
```

## Output ZIP

```text
filename: POWER_GROUND_SHORTWIRE_ATTEMPTS_2026_05_29.zip
size_bytes: 84980
sha256: c441556fc4eb53a41bfb957283609444b547b7bba4b4f5f0d71635ceb28762e6
```

Reconstruction from GitHub Base64 chunks:

```bash
cat experiments/power_ground_shortwire_2026-05-29/artifacts/POWER_GROUND_SHORTWIRE_ATTEMPTS_2026_05_29.zip.b64.part*.txt | base64 -d > POWER_GROUND_SHORTWIRE_ATTEMPTS_2026_05_29.zip
sha256sum POWER_GROUND_SHORTWIRE_ATTEMPTS_2026_05_29.zip
```

## Generator script

```text
filename: generate_power_ground_shortwire_attempts.py
size_bytes: 13904
sha256: 219869e11db356fbc576ec35985d866806f62b811039cfc595a401ec8179d4f5
```

The script is preserved as Base64 at:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_power_ground_shortwire_attempts.py.b64.txt
```

## Test order

```text
1. BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT/BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT.pdsprj
3. BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT/BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT.pdsprj
```

## What to check

```text
Does it open without bad object record / VGDVC / blank sheet?
Do power and ground terminal symbols appear at their endpoints?
Are they short-wired directly to resistor pins?
Does save-as/reopen preserve them?
Any model/netlist/simulation warnings?
```

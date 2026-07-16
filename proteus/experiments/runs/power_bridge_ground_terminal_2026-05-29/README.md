# Power-Bridge + Ground-Terminal Attempts

## Status

Experimental, pending user test in Proteus.

## Why this exists

The combined short-wire power + ground circuit worked, but the user correctly noted that replacing every shared power/ground endpoint with separate visible terminals changes the visual circuit, especially in the 6R fixture.

This experiment reduces those visual changes by using a terminal bridge where possible.

## Methods tested

### Safer terminal-style improvement

Use the already-working donor-derived power bridge for the power node, while keeping the locked short-wire method for ground:

```text
Power side:
$TERPOWER(V0) donor bridge -> $TEROUTPUT(V0)
matching V0 endpoint terminals in resistor network

Ground side:
$TERGROUND(G0) -> short wire -> resistor pin
```

This should avoid multiple separate power symbols at every powered endpoint.

### Experimental ground terminal bridge

Also test the user's idea:

```text
Take the working power terminal bridge layout.
Replace the power terminal marker with ground terminal marker.
Use it as a ground bridge.
```

This is experimental and not locked. If it fails, the generator should keep ground as short-wire endpoint only.

## Generated attempts

```text
TERM_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
TERM_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
TERM_T03_6R_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
TERM_T04_R21_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
```

## Output ZIP

```text
filename: POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip
size_bytes: 171499
sha256: 21ef0a82bf1e3bf2877b265b890f3cbc5a1ba1d38bf73882831a23dfca56a401
```

The ZIP is preserved in GitHub as Base64 chunks:

```text
experiments/power_bridge_ground_terminal_2026-05-29/artifacts/POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip.b64.part00.txt
...
experiments/power_bridge_ground_terminal_2026-05-29/artifacts/POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip.b64.part04.txt
```

Reconstruct:

```bash
cat experiments/power_bridge_ground_terminal_2026-05-29/artifacts/POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip.b64.part*.txt | base64 -d > POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip
sha256sum POWER_BRIDGE_GROUND_TERMINAL_ATTEMPTS_2026_05_29.zip
```

## Generator script

```text
filename: generate_power_bridge_ground_terminal_attempts.py
size_bytes: 15648
sha256: 3e37389193f3041a105e439e867cb4b3d4edc25bc6e6ce1aeb50051ca677f36c
```

Stored as Base64 at:

```text
tools/proteus_generation/2026-05-29/scripts_b64/generate_power_bridge_ground_terminal_attempts.py.b64.txt
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
If T01/T02 work, lock: power donor bridge + ground short-wire endpoint.
If T03/T04 work, ground bridge can be investigated further.
If T03/T04 fail, reject ground bridge and keep ground short-wire only.
```

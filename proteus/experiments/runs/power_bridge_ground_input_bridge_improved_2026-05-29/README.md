# Power Bridge + Improved Ground Input-Bridge Attempts

## Status

Experimental for T03/T04. T01/T02 are locked working references.

## User feedback being addressed

The user confirmed:

```text
CLEAN_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE works
CLEAN_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE works
```

The user requested improvement for T03/T04:

```text
1. fix location because ground bridge was on top of power bridge
2. use an attached input terminal for ground, because ground receives current
```

## Locked references included

```text
LOCKED_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
LOCKED_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
```

These use:

```text
Power = exact working POWER_T10 donor bridge core
Ground = locked short-wire endpoint
```

## New improved experiments

```text
IMPROVED_T03_6R_POWER_BRIDGE_GROUND_INPUT_BRIDGE
IMPROVED_T04_R21_POWER_BRIDGE_GROUND_INPUT_BRIDGE
```

These use:

```text
Power = exact working POWER_T10 donor bridge core
Ground = shifted bridge near the ground endpoint, using attached $TERINPUT(G0)
```

The ground bridge structure is:

```text
$TERGROUND(G0) -- donor bridge wire -- $TERINPUT(G0)
```

Object order follows the working power bridge style:

```text
attached named terminal first
terminal symbol second
wire third
```

## Location fix

The ground bridge is shifted away from the power bridge and placed near the actual ground endpoint.

For 6R:

```text
ground_bridge_target_xy: x=-4572000, y=-1778000
```

For R21:

```text
ground_bridge_target_xy: x=10668000, y=1270000
```

## Output ZIP

```text
filename: POWER_BRIDGE_GROUND_INPUT_BRIDGE_IMPROVED_ATTEMPTS_2026_05_29.zip
size_bytes: 167820
sha256: ff9ae239fe5abdf1366018dcd8de03e02158095e3e83ac8a0bb52a1a3f1ca9b6
```

## Generator script

```text
filename: generate_power_bridge_ground_input_bridge_improved_attempts.py
size_bytes: 17467
sha256: 8f79c97ea3241016af5e7f1e4a1df10297f459099d784b9dd2912a916ea8a4f7
```

## Test order

```text
1. LOCKED_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/CONTROL_E001_EMPTY_BASE.pdsprj
2. LOCKED_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE/LOCKED_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
3. LOCKED_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE/LOCKED_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE.pdsprj
4. IMPROVED_T03_6R_POWER_BRIDGE_GROUND_INPUT_BRIDGE/IMPROVED_T03_6R_POWER_BRIDGE_GROUND_INPUT_BRIDGE.pdsprj
5. IMPROVED_T04_R21_POWER_BRIDGE_GROUND_INPUT_BRIDGE/IMPROVED_T04_R21_POWER_BRIDGE_GROUND_INPUT_BRIDGE.pdsprj
```

## Decision rule

```text
T01/T02 are already locked.
If T03/T04 work, lock ground input-bridge method.
If T03/T04 fail, do not continue terminal bridge experiments for ground; use the locked power-bridge + ground-shortwire method.
```

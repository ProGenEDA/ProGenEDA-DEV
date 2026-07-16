# Power Terminal Attempt: 6R and R21 with V0 Power Node

## Status

Experimental, not locked.

This run tests whether a power terminal can be added to the existing V9 resistor-terminal method by cloning a known `$TERINPUT` terminal record and changing its marker to `$TERPOWER`.

## Why this is experimental

The repository already records that Proteus terminal markers include `$TERPOWER`, and `knowledge/component_db.json` lists `POWER_TERMINAL` as a partially supported terminal marker. However, no controlled donor project for a real power terminal has yet been validated. This attempt therefore tests a hypothesis, not a final method.

## Experimental method

For each generated circuit:

```text
1. Start from CONTROL_E001_EMPTY_BASE.pdsprj.
2. Generate resistor network using the locked V9 linked group method.
3. Rename the selected power-connected node to V0.
4. Add one extra terminal object before the resistor object groups.
5. Build that terminal by cloning a known $TERINPUT record and replacing the marker with $TERPOWER.
6. Keep the power terminal label two characters: V0.
7. Copy PROJECT.XML and SCRIPTS/PWRRAILS.DAT unchanged from blank E001.
8. Generate ROOT.CDB and ROOT.DSN.
```

## Attempts generated

### Attempt 01: corrected 6R + V0 power terminal

```text
folder: POWER_T01_6R_V0_ATTEMPT
project: POWER_T01_6R_V0_ATTEMPT.pdsprj
power node: V0
original node replaced: N0 -> V0
resistor_count: 6
power_terminal_count: 1
static_validation_issues: []
project_sha256: fb8ab4c7bb8e1fdf6febe26acd656d76fd9fc14b4b0c42f64c9a9c91fad37793
```

Topology:

```text
R1: V0 - N1
R2: N1 - N2
R3: V0 - N2
R4: N2 - N3
R5: N3 - N4
R6: V0 - N4
```

### Attempt 02: V9 R21 + V0 power terminal

```text
folder: POWER_T02_R21_V0_ATTEMPT
project: POWER_T02_R21_V0_ATTEMPT.pdsprj
power node: V0
original node replaced: N0 -> V0
resistor_count: 21
power_terminal_count: 1
static_validation_issues: []
project_sha256: 04370ebbb706b0107e8438ab21cd4ffd643c90be5d21e424970ba5603f8b16f3
```

R21 high-level topology:

```text
Branch A: V0 - R1 - A1 - R2 - A2 - R3 - A3 - R4 - A4 - R5 - A5 - R6 - A6 - R7 - M0
Branch B: V0 - R8 - B1 - R9 - B2 - RA - B3 - RB - B4 - RC - B5 - RD - B6 - RE - M0
Tail:     M0 - RF - C1 - RG - C2 - RH - C3 - RI - C4 - RJ - C5 - RK - C6 - RL - Z0
```

## Output package

The generated ZIP is preserved as Base64 chunks in this folder:

```text
artifacts/POWER_TERMINAL_ATTEMPTS_2026_05_29.zip.b64.part01.txt
artifacts/POWER_TERMINAL_ATTEMPTS_2026_05_29.zip.b64.part02.txt
```

Reconstruct locally:

```bash
cat artifacts/POWER_TERMINAL_ATTEMPTS_2026_05_29.zip.b64.part*.txt | base64 -d > POWER_TERMINAL_ATTEMPTS_2026_05_29.zip
```

ZIP hash:

```text
zip_size_bytes: 87588
zip_sha256: ff441b3b17e85b2db273e142304cd16ce0d3dbe8d2f933ad9af50a18acbba231
```

## What to test in Proteus 8.13

Open in this order:

```text
1. POWER_T01_6R_V0_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. POWER_T01_6R_V0_ATTEMPT/POWER_T01_6R_V0_ATTEMPT.pdsprj
3. POWER_T02_R21_V0_ATTEMPT/POWER_T02_R21_V0_ATTEMPT.pdsprj
```

Record:

```text
Does it open?
Does the $TERPOWER object appear?
Does V0 visually/netlist as the same node as the resistor endpoints labelled V0?
Are there VGDVC errors?
Are there model/netlist/simulation warnings?
Does save-as/reopen preserve or repair the object?
```

## If this fails

The most likely reason is that `$TERPOWER` has a different object layout than `$TERINPUT`. In that case, create controlled donor files:

```text
CONTROL_E001_EMPTY_BASE.pdsprj
POWER_T01_SINGLE_VCC_OR_V0_TERMINAL.pdsprj
POWER_T02_SINGLE_POWER_TERMINAL_CONNECTED_TO_R1.pdsprj
```

Then compare ROOT.DSN and derive the real power-terminal record boundaries and label offsets.

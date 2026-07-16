# Capacitor First Generation Attempts 2026-05-29

## Status

Experimental, pending Proteus test.

## Source donor pack

```text
CAP_T04_POWER_CAPACITOR_GROUND.zip
sha256: dc8d935023675dd82c5f64c032ead939d2c37c6a0a3c84dcac8b8dd185331da0
```

Donor files used:

```text
CONTROL_E001_EMPTY_BASE.pdsprj
CAP_T01_SINGLE_CAPACITOR_1uF.pdsprj
CAP_T02_CAPACITOR_BETWEEN_TWO_TERMINALS.pdsprj
CAP_T03_RESISTOR_CAPACITOR_SERIES.pdsprj
CAP_T04_POWER_CAPACITOR_GROUND.pdsprj
```

## Method

This is the first capacitor-generation attempt, so it is intentionally conservative.

The generator does **not** mutate capacitor fields yet.

For each donor case it does:

```text
1. use CONTROL_E001_EMPTY_BASE.pdsprj as the output shell
2. copy the donor capacitor ROOT.CDB component database
3. extract the donor ROOT.DSN object chunk
4. rebuild ROOT.DSN using the same E001/donor-header/tail strategy used by previous V9 generators
5. write a new .pdsprj plus manifest and binary ROOT.CDB/ROOT.DSN outputs
```

This tests whether capacitor CDB + DSN object data can be safely rebuilt into a generated E001-based project before we attempt generalized patching.

## Important limitation

This is **not** the final generalized capacitor generator.

Not locked yet:

```text
ref patching, e.g. C1 -> C2
value patching, e.g. 1uF -> 10uF
coordinate patching
general multi-capacitor generation
mixing generated capacitor templates with generated resistor templates
locked power-bridge + ground-shortwire integration
```

## Generated attempts

```text
CAP_GEN_T01_SINGLE_CAPACITOR_TEMPLATE
CAP_GEN_T02_CAPACITOR_BETWEEN_TERMINALS_TEMPLATE
CAP_GEN_T03_RESISTOR_CAPACITOR_SERIES_TEMPLATE
CAP_GEN_T04_POWER_CAPACITOR_GROUND_TEMPLATE
```

## Output ZIP

```text
filename: CAPACITOR_FIRST_ATTEMPTS_2026_05_29.zip
size_bytes: 107716
sha256: f0c9482c9e520d00be167b21abe47536aa5eeb2b6cb07ddad031783f2fdd1dd3
```

## Generator script

```text
filename: generate_capacitor_first_attempts.py
size_bytes: 12310
sha256: 60c84d94901fc9fbe215e570c4540c1961543e0a8528aaed35cad2104ef24980
```

Stored at:

```text
tools/proteus_generation/2026-05-29/generate_capacitor_first_attempts.py
```

## Test order

```text
1. CAP_GEN_T01_SINGLE_CAPACITOR_TEMPLATE/CAP_GEN_T01_SINGLE_CAPACITOR_TEMPLATE.pdsprj
2. CAP_GEN_T02_CAPACITOR_BETWEEN_TERMINALS_TEMPLATE/CAP_GEN_T02_CAPACITOR_BETWEEN_TERMINALS_TEMPLATE.pdsprj
3. CAP_GEN_T03_RESISTOR_CAPACITOR_SERIES_TEMPLATE/CAP_GEN_T03_RESISTOR_CAPACITOR_SERIES_TEMPLATE.pdsprj
4. CAP_GEN_T04_POWER_CAPACITOR_GROUND_TEMPLATE/CAP_GEN_T04_POWER_CAPACITOR_GROUND_TEMPLATE.pdsprj
```

## What to check

```text
Does each project open without VGDVC/bad object errors?
Does the capacitor appear?
Does C1 and 1uF appear correctly?
For T02, are the two terminals and two wires preserved?
For T03, are resistor + capacitor both visible?
For T04, are power/capacitor/ground visible?
Does save-as/reopen preserve the capacitor?
```

## Decision rule

If these open properly, next step is a controlled mutation pass:

```text
C1 -> C2
1uF -> 10uF
coordinate shift
second capacitor insertion
RC network using generated resistor + capacitor templates
```

If these fail, do not patch capacitor fields yet; first identify which donor chunk/header fields are not being rebuilt correctly.

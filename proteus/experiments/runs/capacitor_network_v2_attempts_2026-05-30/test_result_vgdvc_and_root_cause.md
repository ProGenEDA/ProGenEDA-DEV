# Test Result: V2 Capacitor Network VGDVC Failure

## User result

The user tested:

```text
CAPACITOR_NETWORK_V2_ATTEMPTS_2026_05_30.zip
```

Result:

```text
VGDVC / VGDVC.dll error
```

## Root cause from repository re-check

The V2 capacitor generator copied an assumption from the resistor V9 generator incorrectly.

V2 used partitioned object order:

```text
00 + all $TERINPUT + all $TEROUTPUT + all CAPACITOR component groups
```

That object order is valid for the recovered resistor V9 family, but it is not proven for capacitor.

The capacitor donor `CAP_T02_CAPACITOR_BETWEEN_TWO_TERMINALS.pdsprj` has a different exact object order:

```text
00
$TERINPUT
$TEROUTPUT
CAPACITOR
WIRE
WIRE
```

So V2 broke the capacitor donor's own object-family ordering.

## Other relevant history rechecked

The resistor history says valid generation needs:

```text
1. ROOT.CDB entry per component
2. schematic object stream with matching visible component records
3. terminal/component hidden link suffixes kept synchronized
4. no premature final terminator bytes
5. section offsets patched after final stream size is known
```

The CDB/DSN layout report also warns that a valid component is not just a DSN visual record. ROOT.CDB element/part ownership and visible schematic binding must remain coherent.

## Corrective action

A V3 diagnostic pack was generated:

```text
experiments/capacitor_network_v3_diagnostic_attempts_2026-05-30/
```

V3 changes:

```text
1. Return to exact CAP_T02 sequential group order.
2. Add a one-cap exact reproduction guard: generated T01 object chunk must exactly equal CAP_T02 object chunk.
3. Add a one-cap CDB exact reproduction guard: generated T01 CDB must exactly equal CAP_T01 ROOT.CDB.
4. Add two-cap series test before six-cap and twenty-one-cap tests.
5. Validate terminal suffixes appear in both terminal records and capacitor visual records.
```

## Status

Do not lock V2.

Keep V2 only as negative evidence.

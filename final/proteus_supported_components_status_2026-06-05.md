# Proteus Generator Supported Components Status — 2026-06-05

## Status

User-reported major working milestone.

The generator can now generate runnable Proteus circuits using the following component families:

```text
Resistor
Capacitor
Inductor
Power terminal
Ground terminal
DC voltage source
DC current source
```

## Example prompt tested by user

```text
Make a circuit where a voltage supply v0 is connected to r1(10K). The resistor is connected to node A. On the right side of node A is an inductor of 10mH and on the downside is a capacitor of 10nF which is connected to the ground.
```

## Screenshot result observed

The user-provided screenshot shows a generated Proteus schematic containing:

```text
power terminal labelled V0
resistor R1 with value 10K
inductor L1 with value 10m
capacitor C1 with value 10n
ground terminal labelled G0
node labels such as V0, N1, and N2 used for connectivity
```

## Important interpretation

This is a strong milestone compared with the earlier state, where only resistor/power/ground behavior was locked and capacitor attempts had failed.

The current generator appears to rely on labelled terminals/nets for connectivity rather than drawing every continuous wire segment physically. This is acceptable for a generator backend if Proteus resolves same-name terminals/nets correctly and the generated circuit runs.

## Current honest capability statement

The safe statement is:

```text
The Proteus backend has reached a working primitive-component stage for R, C, L, power terminal, ground terminal, DC voltage source, and DC current source.
```

Avoid claiming unrestricted arbitrary circuit generation until the following are tested:

```text
multi-component mixed RLC networks
power + ground + source + RLC simulation behavior
DC current source polarity/orientation
component value mutation across multiple values
save-as/reopen stability
netlist/simulation correctness
larger topology scaling
```

## Recommended next validation matrix

```text
1. R only
2. C only
3. L only
4. R-C series
5. R-L series
6. R-L-C mixed network
7. DC voltage source + R + ground
8. DC current source + R + ground
9. DC voltage source + RLC + ground
10. same-name terminal connectivity check
11. save-as/reopen check for every case
12. simulation/netlist output check for every powered case
```

## Relation to previous locked methods

Previously locked stable baseline:

```text
Resistor V9 generator
Power terminal donor bridge / terminal method
Ground terminal short-wire endpoint
Power bridge + ground short-wire combined method
```

This status document records that the working surface has now expanded beyond that baseline to include:

```text
capacitor
inductor
DC voltage source
DC current source
```

## Next documentation task

Capture the exact generator method now being used for capacitor, inductor, DC voltage source, and DC current source, including:

```text
input JSON schema
component template source
ROOT.CDB handling
ROOT.DSN/object handling
value patching rules
orientation/coordinate rules
node/terminal naming rules
known limitations
validated example hashes
```

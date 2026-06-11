# PSpice / OrCAD Visual Generator Status

## Current state

Started side-by-side OrCAD/PSpice visual generator work.

## Files added

```text
pspice/PLAN.md
pspice/generator/README.md
pspice/generator/orcad_visual_generator.py
pspice/schema/circuit_ir_v0_example.json
```

## Built code

`pspice/generator/orcad_visual_generator.py` is a committed Python CLI scaffold.

It currently supports:

```text
validate CircuitIR JSON
inventory donor project folders or ZIPs
create scaffold output package folders
write normalized input JSON
write manifests and hashes
prepare future native generation entrypoint
```

It does not yet write native `.opj/.dsn` visual project files. That part is gated until user-created OrCAD donor projects or verified OrCAD automation behavior are available.

## Next required user input

```text
OrCAD/Cadence exact version
Windows version
blank OrCAD project donor ZIP
single resistor donor ZIP
single capacitor donor ZIP
DC-source-resistor-ground donor ZIP
```

## Product target remains

```text
native OrCAD Capture / PSpice visual project generator
```

Not a raw netlist-only generator.

# Shared Power Terminal Visual Acceptance V1

## Purpose

Verify that EasyEDA combination mode uses one shared terminal for each power
net instead of placing a duplicate `GND` or `+5V` terminal at every endpoint.

## Input

`Easyeda/examples/regulated_5v_supply.json`

Immutable generated run:

`Easyeda/examples/generated_runs/2026_07_16_212215_724326_easyeda_regulated_5v_supply`

## Results

- EasyEDA Pro 3.2.149 opened a disposable copy of the generated `.eprj`.
- The schematic rendered one `GND` terminal and one `+5V` terminal.
- All seven GND endpoints were physically connected to the shared GND route.
- All four +5V endpoints were physically connected to the shared +5V route.
- The validator reported exact expected membership for both power nets.
- The validator reported no component overlap or wire/body contact errors.
- The generated PCB remained present and validation-clean.

Routing evidence:

```text
GND: shared_power_terminal, 7 endpoints, 20 segments
+5V: shared_power_terminal, 4 endpoints, 9 segments
terminal instances: 2
```

The screenshot `easyeda_shared_power_schematic.png` is the GUI acceptance
record. The opened disposable copy was not used as the immutable deliverable,
because EasyEDA upgrades opened projects into its `.eprj2` working format.

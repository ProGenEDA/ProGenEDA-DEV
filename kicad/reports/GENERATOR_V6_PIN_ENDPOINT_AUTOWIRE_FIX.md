# Generator V6 pin-endpoint autoroute fix

## Status

V5 opened in KiCad and embedded symbols loaded correctly, but the visible wires did not electrically connect to several symbol pins. This is now classified as a pin-coordinate bug, not a syntax or library-cache bug.

## Root cause

V5 routed to the visible end of the drawn pin line instead of the KiCad connection point. In KiCad schematic symbols, the connection point is the pin `(at x y)` coordinate inside the cached symbol definition.

Verified pin endpoint models used by V6:

```text
Device:R        pin 1 = (0,  3.81), pin 2 = (0, -3.81)
Device:L        pin 1 = (0,  3.81), pin 2 = (0, -3.81)
Simulation_SPICE:VDC   pin 1 = (0,  5.08), pin 2 = (0, -5.08)
Simulation_SPICE:VSIN  pin 1 = (0,  5.08), pin 2 = (0, -5.08)
power:GND       pin 1 = (0,  0)
```

Example failure:

A resistor centered at y=50 has real pin endpoints at:

```text
pin 2/top = 50 - 3.81 = 46.19
pin 1/bottom = 50 + 3.81 = 53.81
```

V5 was ending wires at values such as `43.65` and `56.35`, which are one pin-line length away from the actual connection points. KiCad therefore displayed open red/magenta terminals separated from the green wires.

## V6 implementation rule

V6 does not require manually supplied wire coordinates for simple circuits. It uses the component `pins` net map:

```json
{"ref": "R1", "kind": "R", "pins": {"2": "VIN", "1": "GND"}}
```

Then it:

1. Looks up the local KiCad pin endpoint for each component kind.
2. Applies component rotation.
3. Adds the component `(at x y)` position.
4. Groups pins by net.
5. Emits only two-point KiCad wire segments that terminate exactly on real pin endpoints.
6. For GND, connects each non-ground pin to the nearest `power:GND` symbol on that net instead of drawing a large ground bus.

## Generated test package

Local generated artifact:

```text
KICAD_GENERATED_OUTPUTS_V6_PIN_ENDPOINT_AUTOWIRE.zip
SHA256: 3cce6ef52686366f33143ee0f885721f95ccc8ed63f71e913ac2c98bf91dfd8f
```

Tests inside:

```text
vdc_resistor_op
vsin_rl_tran
```

Static checks passed:

```text
balanced schematic S-expression: yes
all wire objects have exactly two xy points: yes
all used lib_ids have embedded lib_symbols: yes
simulation directives detected: .op and .tran
```

## Next validation

Open the V6 project files in KiCad and verify visually that each green wire touches the symbol pin endpoint exactly. After that, run KiCad simulator and check whether `.op` / `.tran` jobs are recognized and produce a netlist/run.
# Proteus File Model

## Resistor V9 Generator Scope

The current main generator implementation in `D:/Coding/protuesgen` follows the locked V9 resistor-terminal method:

- Use blank E001 as the `.pdsprj` base.
- Copy E001 `PROJECT.XML`.
- Copy E001 `SCRIPTS/PWRRAILS.DAT`.
- Generate `ROOT.CDB`.
- Generate `ROOT.DSN`.
- Use the user-confirmed R21 V9 artifact only as a byte-record donor.

## V9 Object Stream Rule

Each resistor has a conceptual linked endpoint group:

```text
left endpoint terminal
right endpoint terminal
resistor visual record
left short wire
right short wire
```

The generated records must preserve:

- terminal/resistor link suffix consistency
- one generated CDB record per resistor
- no premature final terminators
- final terminator only at the last object
- section pointers patched after final object-stream length is known

## Resistor Orientation Field

Public Proteus sample projects show that the resistor visual record stores rotation in the four bytes immediately after the final model placement `x/y` pair:

```text
00 00 00 00 = horizontal
7c fc 00 00 = -900 tenths of a degree, vertical down
```

The current main generator patches this field for locked 90-degree orientations. For `visual.orientation_hint = "vertical"`, the first resistor pin remains at the component position and the second pin is generated at `y - 1270000`; the terminal and short-wire endpoint records are generated along the same vertical axis.

## Standalone Visual Wires

`layout.visual_wires` is parsed but currently skipped by the production generator. Earlier generated standalone `WIRE` records passed static checks but were associated with user-reported VGDVC failures in parallel-and-later resistor cases. Keep routed bus/junction wire records experimental until a Proteus-created donor proves a VGDVC-safe standalone wire method.

Manual component coordinates are accepted as placement hints, but the production resistor generator stretches dense repeated x/y positions to a safe grid before writing `ROOT.DSN`. The current production safe grid is `2540000` internal units on both x and y. This keeps vertically oriented component/terminal groups farther apart while preserving the locked terminal-to-component offsets.

## Power And Ground Endpoint Rule

Current supported labels:

```text
V0 = power
G0 = ground
```

Current safe method:

```text
Power node V0 -> one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
V0 resistor endpoints -> ordinary $TERINPUT(V0) records
G0 resistor endpoints -> $TERGROUND only when the ground node is component.nodes[1]
```

The older pure short-wire power endpoint method is not the main generator behavior. The preferred working method is the user-confirmed donor bridge from `power_terminal_bridge_donor.pdsprj`; ground remains the short-wire endpoint method.

Long labels such as `VCC` and `GND` remain outside the locked v0.1 resistor generator until variable-length terminal labels are validated.

## Capacitor Temporary Findings

Free multi-capacitor generation is user-accepted through the `cap3` donor path, but terminal-attached multi-capacitor generation is still experimental.

The user-made `CAp2withterm.pdsprj` donor shows a different object order than the failed duplicated one-cap attempts:

```text
00
$TEROUTPUT N2
$TEROUTPUT N4
$TERINPUT N1
C1 CAPACITOR
C1 left WIRE
C1 right WIRE, 49 bytes, no trailing terminator byte
$TERINPUT N3
C2 CAPACITOR
C2 left WIRE
C2 right WIRE, 50 bytes, final FF
```

The donor ROOT.CDB contains two `CAPACITOR` records with refs `C1` and `C2`, both `1nF`, and the generated CDB builder can reproduce it byte-for-byte with zero component-table flags. V10 temporary diagnostics use this manual order from E001 and must pass Proteus manual testing before any capacitor code is promoted to main.

The user reported all V10 manual-order cases worked in Proteus 8.13, including exact donor transplant, split/rebuild, coordinate translation, ref/value mutation, and a three-cap scale test. V11 now uses the same record structure for larger 6C and 21C terminal-label topology stress tests. These larger networks are still temporary until user-opened Proteus confirmation.

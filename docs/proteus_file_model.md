# Proteus File Model

## Current Resistor V9 Generator Scope

For the resistor-terminal generator implemented from the `memory` V9 method:

- The output `.pdsprj` is packed from the clean E001 base.
- `PROJECT.XML` and `SCRIPTS/PWRRAILS.DAT` are copied from E001.
- `ROOT.CDB` is generated with one resistor record per requested component.
- `ROOT.DSN` is generated with the V9 terminal/resistor/wire object stream.
- The R21 V9 project is a record-schema donor only, not an output base.

The V9 object stream keeps one conceptual group per resistor:

```text
left endpoint terminal
right endpoint terminal
resistor visual record
left short wire
right short wire
```

Static validation checks marker counts, wire counts, object-group counts, terminal/resistor link suffix reuse, and final-terminator placement.

## Resistor Orientation

Public Proteus sample projects show that the resistor visual record stores rotation in the four bytes immediately after the final model placement `x/y` pair:

```text
00 00 00 00 = horizontal
7c fc 00 00 = -900 tenths of a degree, vertical down
```

The generator now patches this field for supported 90-degree orientations. For `vertical`, the first resistor pin remains at the component position and the second pin is generated at `y - 1270000`; short-wire endpoint records are generated along the same vertical axis.

## Optional Visible Wires

`layout.visual_wires` is parsed but currently skipped by the production generator. Earlier generated standalone `WIRE` records passed static checks but were associated with user-reported VGDVC failures in parallel-and-later resistor cases. Keep routed bus/junction wire records experimental until a Proteus-created donor proves a VGDVC-safe standalone wire method.

## Layout Safety

Manual component coordinates are accepted as placement hints, but the production resistor generator now stretches dense repeated x/y positions to a safe grid before writing `ROOT.DSN`. The current guard spacing is `2540000` internal units on x and `2540000` internal units on y. This keeps vertically oriented component/terminal groups farther apart while preserving the locked terminal-to-component offsets.

## Power And Ground Endpoints

The locked endpoint method remains two-character label based:

```text
V0 = power node label
G0 = ground node label
```

Current safe substitutions:

```text
Power node V0 -> one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
V0 resistor endpoints -> ordinary $TERINPUT(V0) records
G0 resistor endpoints -> $TERGROUND only when the ground node is component.nodes[1]
```

The older pure short-wire power endpoint method is no longer the main generator behavior. The preferred working method is the user-confirmed donor bridge from `power_terminal_bridge_donor.pdsprj`; ground remains the short-wire endpoint method.

Long labels such as `VCC` and `GND` remain outside this v0.1 generator until variable-length terminal labels are separately validated.

## Capacitor Temporary Findings

Free multi-capacitor generation is user-accepted through the `cap3` donor path, but terminal-attached multi-capacitor generation is still experimental.

The user-made `cap2_with_terminals_manual` donor shows a different object order than the failed duplicated one-cap attempts:

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

The user reported all V10 manual-order cases worked in Proteus 8.13, including exact donor transplant, split/rebuild, coordinate translation, ref/value mutation, and a three-cap scale test. The user also reported all V11 6C and 21C terminal-label network cases worked.

V12 applies the same manual-order method to the 15 requested resistor-network topologies converted to capacitors. This pack is still temporary pending user Proteus open/visual acceptance. It intentionally uses ordinary two-character labels `V0` and `G0` rather than power/ground terminal symbols, emits horizontal capacitor records, and does not introduce standalone bus/junction wire records.

V13 supersedes V12 for the next capacitor test pass. It uses a wider `3810000` internal-unit grid on both x and y axes, prepends one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge after the object stream header, leaves powered capacitor endpoints as ordinary `$TERINPUT(V0)`, and emits grounded right endpoints as `$TERGROUND(G0)`. Capacitor records remain horizontal and standalone bus/junction wire records are still not emitted.

## Mixed Resistor/Capacitor Locked Scope

Mixed passive V1 combines the accepted resistor V9 method and accepted capacitor manual-order method. The user accepted the V1 6-component and 21-component mixed passive diagnostics on May 31, 2026, with a spacing adjustment request: reduce the excessive row gap while still preventing overlap.

The main locked generator now lives in `src/proteusgen/mixed_passive.py`, uses `2540000` internal units as the safe minimum x/y spacing, and shifts duplicate component positions so no two components are emitted on top of each other.

The locked object stream order is:

```text
00 header
$TERPOWER -> $TEROUTPUT(V0) bridge
all capacitor output/ground terminals
all capacitor input/component/wire groups
all resistor input terminals
all resistor output/ground terminals
00 resistor separator
all resistor component/wire groups
```

This preserves the accepted capacitor outputs-first block and the accepted resistor V9 terminal-array block. The generated `ROOT.CDB` contains both `RESISTOR` and `CAPACITOR` entries in the requested component order.

## Inductor Temporary Findings

The user supplied four controlled Proteus 8.13 inductor donors:

```text
inductor_01_single_free.pdsprj
inductor_02_two_terminal.pdsprj
inductor_03_three_terminal.pdsprj
inductor_04_power_ground.pdsprj
```

The inductor device name observed in `ROOT.DSN` and `ROOT.CDB` is `REALIND`.
The terminal-attached one-inductor donor uses:

```text
00 header
$TERINPUT
$TEROUTPUT
REALIND visual record
left WIRE
right WIRE
```

The three-inductor donor uses a non-trivial scaling order:

```text
first full inductor group
remaining $TEROUTPUT records
remaining $TERINPUT / REALIND / WIRE / WIRE groups
```

As with the accepted capacitor manual-order donor, non-final right-wire records omit the trailing terminator byte. A four-character value such as `10uH` uses a one-byte-longer `REALIND` visual record than three-character values such as `1mH` and `2mH`.

`INDUCTOR_V1_TERMINAL_TEMP_20260531` used this donor shape from E001, but the user reported that every generated V1 case caused a VGDVC.dll error. V1 must not be reused as positive evidence. A byte diff against the known-good two-terminal donor shows the first generated mutation was replacing the donor's `REALIND` link suffix bytes with resistor V9 suffix bytes.

`INDUCTOR_V2_SUFFIX_TEMP_20260531` therefore starts with exact donor repack controls and exact donor-object-chunk controls before testing suffix-preserved mutations. The single suffix-preserved case preserves the two-terminal donor object chunk byte-for-byte.

The user reported V2 T1-T6 and T8-T9 worked, while V2 T7 failed. This means deterministic repacking, E001 insertion of exact inductor chunks, suffix-preserved single-inductor mutation, renamed/translated single-inductor mutation, and exact power/ground donor insertion are accepted for current evidence. The remaining failure is isolated to generated multi-inductor reconstruction.

Local diffing of failed V2 T7 found two remaining suspects: the second 3-character inductor reused the first 3-character `REALIND` visual template, changing L2 tail/link bytes, and the generated output recomputed several donor terminal/wire coordinates instead of preserving the donor's relative geometry. `INDUCTOR_V3_MULTI_TEMP_20260531` tests those separately:

```text
T01 rebuild donor03 from explicit per-index slices, byte-identical object chunk
T02 rename refs/terminal labels with donor03 geometry preserved
T03 rigid-translate all donor03 coordinates with refs/labels preserved
T04 rename plus rigid-translate donor03 geometry
T05 formula-coordinate rebuild with the per-index REALIND suffix issue fixed
```

Do not promote arbitrary multi-inductor generation until V3 Proteus results identify which of these transformations is safe.

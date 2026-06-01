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

The user supplied five controlled Proteus 8.13 inductor donors:

```text
inductor_01_single_free.pdsprj
inductor_02_two_terminal.pdsprj
inductor_03_three_terminal.pdsprj
inductor_04_power_ground.pdsprj
inductor_05_six_terminal.pdsprj
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

After V6/V7/RCL V1 failed, the user supplied `inductor_05_six_terminal.pdsprj`.
This six-inductor donor does not use the three-inductor donor order and does
not use the capacitor donor's outputs-first order. Its observed object order is:

```text
00 header
$TERINPUT / $TEROUTPUT / REALIND / left WIRE / right WIRE
$TERINPUT / $TEROUTPUT / REALIND / left WIRE / right WIRE
... repeated six times
```

The capacitor-family rule that does carry over is right-wire trimming: non-final
right-wire records are 49 bytes, omitting the trailing record terminator, while
the final right-wire record is 50 bytes and ends with `FF`. Donor05 also shows a
regular terminal suffix step of `0x02A8` (`$TERINPUT` starts at `0x01B2`,
`$TEROUTPUT` starts at `0x01E4`). The `REALIND` visual record's terminal link
bytes start at offset 365 in the 374-byte record.

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

The user reported all V3 cases worked. That confirms per-index `REALIND` template preservation is the safe multi-inductor path, including formula-coordinate generation once the L2 template/suffix bug is fixed.

`INDUCTOR_V4_POWER_GROUND_TEMP_20260531` is the final inductor lock-candidate pack before main promotion. It combines the accepted V3 `REALIND` generation path with the already accepted passive power/ground method:

```text
one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
V0 component endpoints remain ordinary $TERINPUT(V0)
G0 right endpoints become $TERGROUND(G0)
```

If V4 opens cleanly, the inductor generator can be promoted for the current scope. Keep the initial main inductor scope conservative: up to the controlled three donor slots until a larger inductor donor establishes safe suffix/link bytes beyond three `REALIND` components.

The user reported V4 failed: T1, T2, T3, and T5 opened far enough to show a detached generic power bridge and a separate `V0` inductor input, then gave a bad object record error; T4 gave an ISIS.dll error. This rejects the generic passive bridge-first object order for inductors.

The accepted `inductor_04_power_ground` object order is different:

```text
00 header
$TERINPUT internal connection node
REALIND
left WIRE, 49 bytes, no trailing terminator
$TERPOWER V0
$TEROUTPUT internal connection node
bridge WIRE
$TERGROUND G0
final ground WIRE
```

`INDUCTOR_V5_DONOR04_ORDER_TEMP_20260531` tests this exact order. T1-T3 are byte-identical donor04 controls; T4-T5 mutate only the ref/value/internal power-bridge connection label while preserving donor04 order.

The user reported all V5 cases worked. This confirms the donor04-order mutation for the tested single-inductor scope only; it does not lock the inductor generator as main. The premature main implementation was moved to:

```text
tools/proteus_generation/2026-06-01/inductor_temp_from_premature_main
```

Current temporary evidence:

```text
terminal-only inductors:
  one to three components
  per-index REALIND donor templates from inductor_03_three_terminal
  $TERINPUT / $TEROUTPUT terminal-label topology

power/ground inductor:
  exactly one component with nodes ["V0", "G0"]
  donor04 object order only
```

V6 6/21, V7 requested-15, and R/C/L V1 were rejected by user Proteus testing;
all generated files gave errors. Those failed packs must not be reused as
positive evidence.

`INDUCTOR_V8_SIX_DONOR_TEMP_2026_06_01` uses donor05's six sequential groups.
T01 inserts the exact donor05 object chunk into E001 and T02 rebuilds donor05
from slices byte-for-byte. T03 is the main generated six-inductor candidate.
T05 is the explicit capacitor-style outputs-first probe, included only to test
the same-family hypothesis. T06 is a power/ground bridge probe and should be
tested only after the terminal-only donor05 cases work.

The user reported all V8 cases worked in Proteus. This accepts donor05 sequential
groups as the current temporary multi-inductor method, including the 21-inductor
scale case and the sequential power/ground bridge probe. The outputs-first V8
probe also worked, but the generator should prefer the donor05 observed sequential
order unless a later test proves a reason to switch.

`INDUCTOR_V9_REQUESTED15_POWER_GROUND_TEMP_2026_06_01` applies the accepted V8
method to the 15 requested topology cases, with one donor-derived
`$TERPOWER -> $TEROUTPUT(V0)` bridge, ordinary `$TERINPUT(V0)` powered component
endpoints, and `$TERGROUND(G0)` grounded right endpoints. Static validation is
clean for all 15 cases, and the existing locked resistor plus mixed R/C tests
still pass. V9 is awaiting user Proteus open/render acceptance.

The inductor generator must remain temporary until the requested 15 inductor
circuits and later R/C/L mixed circuits are accepted. The V4 generic passive
bridge-first order is rejected and must not be reintroduced for inductors unless
a later donor-based diagnostic proves a safe variant.

## Mixed R/C/L Temporary Findings

`MIXED_RCL_V1_TEMP_2026_06_01` is negative evidence. It combined the locked
resistor/capacitor methods with the rejected V6 inductor path, and the user
reported that all generated files failed in Proteus.

`MIXED_RCL_V2_V8_TEMP_2026_06_01` is the next R/C/L candidate. It uses:

```text
locked resistor V9 records
locked capacitor manual-order records
accepted V8 donor05 sequential inductor records
one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
$TERGROUND(G0) right endpoints
```

The V2 object stream order is:

```text
00 header
power bridge
capacitor output terminals
capacitor input/component/wire groups
resistor input terminals
resistor output/ground terminals
resistor separator
resistor component/wire groups
donor05 sequential inductor groups
```

V2 generated 17 projects: one six-component R/C/L cycle, one twenty-one-component
R/C/L cycle, and the 15 requested topology shapes. One- and two-component source
topologies are expanded to three mixed components so every requested topology
test includes at least one resistor, capacitor, and inductor. Static validation
is clean for all 17 cases. The user reported that all V2 files failed with a
`VGCVC.dll` error, so this object order is rejected.

`MIXED_RCL_V3_ISOLATION_TEMP_2026_06_01` isolates the next variable instead of
generating another large batch. It contains:

```text
T01-T02: resistor + inductor order probes
T03-T05: capacitor + inductor order probes
T06-T09: minimal resistor + capacitor + inductor order probes
```

Use V3 results to determine whether the failure is pairwise (`R+L` or `C+L`) or
only appears when all three families share one object stream.

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

The user reported only V3 T03 and T05 worked. Both are capacitor+inductor cases:
T03 uses a capacitor block followed by a donor05 sequential inductor block, and
T05 uses joined capacitor/inductor outputs-first ordering. V3 T01/T02
resistor+inductor failed, V3 T04 inductor-first capacitor+inductor failed, and
all V3 full R+C+L cases failed. This supports treating resistor as a separate
family boundary from the capacitor/inductor family.

`MIXED_RCL_V4_RESISTOR_BOUNDARY_TEMP_2026_06_01` probes that boundary. T01-T07
test R+L with and without power bridge, different `ROOT.CDB` component contents,
and both resistor-first and inductor-first object orders. T08-T10 then test
minimal R+C+L variants where the known-good C+L block can remain final or CDB
entries can omit one family. V4 is pending user Proteus testing.

The user then supplied `rlc.pdsprj`, imported as `rlc_manual_donor`. This donor
is useful, but it is not a complete terminal-topology oracle. Its observed
object chunk is 1087 bytes and contains:

```text
REALIND marker count: 3
RESISTOR marker count: 2
CAPACITOR marker count: 1
CAP10 marker count: 1
COMPONENT ID marker count: 3
terminal marker count: 0
WIRE marker count: 0
```

The visible free component order is `L1`, `R1`, `C1`, and `ROOT.CDB` carries
matching L/R/C entries. `MIXED_RCL_V5_MANUAL_DONOR_TEMP_2026_06_01` therefore
starts with donor controls:

```text
T01 exact deterministic donor repack
T02 donor ROOT.DSN/ROOT.CDB copied into an E001 container
T03 donor object chunk and CDB inserted into E001 using the donor DSN header
T04 donor object chunk and CDB inserted into E001 using the resistor donor header
```

Only after those controls does V5 reintroduce generated terminal topology. T05
and T06 are the key boundary checks: both use L/R/C object order, but T05 uses
the manual donor `ROOT.CDB` and T06 uses a generated `ROOT.CDB` in the same spec
order. V5 is awaiting user Proteus results and must not be promoted until the
donor controls and generated terminal cases are known.

The user reported V5 T01-T04 all worked and V5 T05 onward all errored. This
means:

```text
free L/R/C component coexistence: accepted
manual donor CDB and DSN header insertion: accepted
generated mixed R/L/C terminal topology: rejected by current evidence
```

`MIXED_RCL_V6_TERMINAL_BOUNDARY_TEMP_2026_06_01` therefore removes power/ground
from the immediate test surface and isolates terminal-attached records:

```text
T01: rebuild the worked free L/R/C donor chunk from slices
T02-T04: one terminal-attached family with the other two as exact free donor records
T05-T07: two terminal-attached families with the third as an exact free donor record
T08-T09: all terminal-attached, disconnected versus connected labels, resistor header
T13-T14: same all-terminal chunks using the manual RLC donor header
```

Do not generate another large R/C/L topology pack until V6 identifies whether
the failure is a specific family record, pairwise terminal-record coexistence,
shared terminal labels, or DSN header/device-section choice.

The user reported that V6 T01, T02, T04, T05, and T10 worked; all other V6
cases failed. Interpreting those cases:

```text
worked:
  T01 free L/R/C rebuild
  T02 terminal L with free R/C
  T04 terminal C with free L/R
  T05 terminal C+L with free R, disconnected labels
  T10 terminal C+L with free R, connected labels

failed:
  every case containing terminal-attached R
  all-terminal cases with either resistor header or manual RLC header
```

So the current boundary is narrower than generic mixed-family terminals:
terminal C and terminal L can coexist around a free resistor, but terminal R
fails whenever an inductor exists in the project.

`MIXED_RCL_V7_RESISTOR_SUFFIX_ORDER_TEMP_2026_06_01` keeps that evidence stable
and varies only the resistor terminal record:

```text
T01: reproduce the V6 terminal-R failure
T02-T07: free L/C first, terminal R final, varied ordinal/index/suffix policy
T08-T10: known-good connected terminal C+L first, terminal R final, varied suffix policy
T11-T12: all-terminal R-final variants using the manual RLC donor header
```

If V7 fails entirely, the current V9 terminal-resistor visual record is likely
not compatible with inductor coexistence, and the next required donor should be
a Proteus-created terminal-attached resistor plus inductor file.

The user later reported V7 T02-T07 worked. Those cases all share the same
important structure:

```text
free L/C donor records first
terminal-attached resistor block last and final
```

The varied ordinal/index/suffix policies in T02-T07 all opened, so the decisive
factor is currently interpreted as final object-stream order, not the exact
suffix policy. This only answers the free-L/C scope. V7 T08-T12 remain
unrecorded unless later feedback supplies their result.

`MIXED_RCL_V8_R_LAST_TERMINAL_POWER_TEMP_2026_06_01` now tests the next boundary:

```text
T01: V7-style control, free L/C then final terminal R
T02-T04: all-terminal C/L/R, no power, C/L blocks before final R
T05-T06: small V0-to-G0 R/C/L series, C/L blocks before final R
T07-T08: 6-component and 21-component R/C/L cycles with V0/G0
```

All V8 static validation passed. Do not promote mixed R/C/L until the V8 Proteus
open results are known. If T02-T04 fail, the remaining problem is terminal C/L
coexistence before terminal R. If T02-T04 work but T05-T06 fail, isolate the
power bridge and G0 endpoint interaction. If T05-T08 work, regenerate the 15
requested mixed R/C/L topologies using the same C/L-before-final-R object order.

The user reported that only V8 T01 worked. This is a strong boundary:

```text
positive:
  free L/C donor records + final terminal R

negative:
  terminal C + terminal L + terminal R with disconnected labels and no power
  terminal C + terminal L + terminal R with connected labels
  same families with V0/G0
  6-component and 21-component R/C/L candidates
```

Because V8 T02 has no power/ground and disconnected labels, the first blocker is
not V0/G0, shared labels, or circuit scale. Existing positive evidence already
shows terminal C+L works around a free resistor, and terminal R works around free
L/C. The remaining active blocker is terminal-attached `RESISTOR` plus
terminal-attached `REALIND` in the same object stream.

`MIXED_RCL_V9_RL_BOUNDARY_TEMP_2026_06_01` isolates that boundary before any
large topology work:

```text
T01-T02: minimal terminal R+L, no power, both object orders
T03-T07: terminal R+L with varied resistor index/suffix and global-style IDs
T08: connected-label R+L, no power
T09-T10: add capacitor only after R+L hypotheses
T11: add V0/G0 only after the preceding boundary is tested
```

If V9 T01-T08 all fail, generated guessing should stop for this boundary. The
next required donor should be a Proteus-created project containing a
terminal-attached resistor and a terminal-attached inductor in the same clean
E001-based project, because the current donor set does not show Proteus' native
R+L terminal object ordering/linking.

The user reported that none of the V9 files worked. This answers the R/L
boundary:

```text
failed:
  minimal terminal R+L, no power, both object orders
  terminal R+L with varied resistor index/suffix/global-style IDs
  connected-label terminal R+L, no power
  terminal R+L plus capacitor
  terminal R+L plus V0/G0
```

Do not continue generated R/L guessing from independent resistor and inductor
donors. Existing evidence already proves:

```text
terminal C+L with free R: accepted
terminal R with free L/C: accepted when R is final
terminal R+L generated from independent donor records: rejected
```

The missing evidence is now specific: a Proteus-created terminal-attached
`RESISTOR` and terminal-attached `REALIND` in the same clean E001-based project.
The highest-value manual donor is disconnected labels only, no power, no
capacitor:

```text
R1 between terminal labels R1 and R2
L1 between terminal labels L1 and L2
values 1k and 1mH
normal short wire stubs/terminals as Proteus creates them
```

A second useful donor is the same pair in series:

```text
R1 from N1 to N2
L1 from N2 to N3
same N2 terminal-label connection on R right and L left
no power/ground
```

If those donors open as manually created projects, compare their ROOT.DSN object
order, terminal records, wire records, component indices, link/suffix bytes, and
ROOT.CDB records before attempting any new mixed R/C/L generation.

The user supplied both requested R+L terminal donors:

```text
rl_terminal_disconnected.pdsprj
sha256 293f00ac5504f0f53fc514682a9cb8136dabda8c03343850b5a54c5b6a614f36

rl_terminal_series.pdsprj
sha256 80fe75ca0bf60cb40f99344bb979b6a616ed77d1da1bacbc30f260fd47c833f8
```

Static analysis of `rl_terminal_disconnected` shows:

```text
ROOT.DSN length: 68109
ROOT.CDB length: 352
object chunk length: 1335

marker counts:
  $TERINPUT: 2
  $TEROUTPUT: 2
  WIRE: 4
  REALIND: 3
  RESISTOR: 2
  COMPONENT ID: 2
  COMPONENT VALUE: 2

native object order:
  header
  both $TERINPUT records
  L $TEROUTPUT + REALIND visual record + two short wires
  R $TEROUTPUT + one boundary byte + RESISTOR visual record + two short wires
```

This is the first controlled evidence that native terminal R+L order is
different from both the locked resistor V9 order and the accepted six-inductor
sequential order. The series donor has matching marker counts but is retained as
a control because its CDB/component refs appear swapped relative to the requested
names.

`MIXED_RCL_V10_TERMINAL_RL_DONOR_TEMP_2026_06_01` uses this native donor order:

```text
T01: exact disconnected donor repack
T02: disconnected donor object chunk and CDB inserted into E001
T03: exact series donor repack
T04: series donor object chunk and CDB inserted into E001
T05: generated donor-native same-label rebuild
T06: generated donor-native connected-label R+L
T07: generated donor-native translated disconnected R+L
T08: generated donor-native V0/G0 R+L series
```

Do not promote mixed R/C/L until Proteus user testing accepts the donor controls
and at least the donor-native generated rebuild.

The user reported all V10 cases worked. This confirms the native terminal R+L
order for:

```text
exact donor repacks
donor chunks inserted into E001
same-label generated rebuild
connected-label R+L
translated disconnected R+L
V0/G0 R+L series
```

`MIXED_RCL_V11_SCALED_TEMP_2026_06_01` scales that accepted boundary to the
requested mixed R/C/L batch. It emits:

```text
header
one donor-derived V0 power bridge
accepted capacitor output/group block
repeated native R/L pair blocks from V10
```

V11 balances component type assignment so every generated circuit has paired
resistor and inductor counts, with capacitors filling extra topology slots. This
keeps each resistor inside a native R/L pair instead of falling back to the
previous failed independent resistor/inductor composition. The pack contains:

```text
T01: 6 components, 2R/2C/2L
T02: 21 components, 7R/7C/7L
T03-T17: the 15 requested topology shapes with mixed R/C/L components
```

All V11 static validation passed, but this is not a promotion point. Promotion
requires user Proteus open/render acceptance for the 6-component, 21-component,
and requested-15 outputs.

The user then tested V11 by invoking Proteus simulation/netlist compilation and
reported failures. Representative errors for T03 simple loop and T07 basic
voltage divider were:

```text
Duplicate part reference: R1 [C1]
Duplicate part reference: X00000001#0 [X00000001#0]
Duplicate part reference: X00000001#1 [X00000001#1]
Simulation FAILED due to netlist compiler error(s).
```

The user also reported the 6-component and 21-component V11 cases failed. This
means visual/opening acceptance and simulation/netlist acceptance must be tracked
separately.

Static byte analysis found V11's netlist-identity bug:

```text
V11 T03 DSN object IDs:
  C1 -> 1
  L1 -> 1
  R1 -> 2

V11 T03 ROOT.CDB table order:
  1 -> R1
  2 -> C1
  3 -> L1
```

So Proteus mapped DSN component records to the wrong or duplicate logical part
handles during netlisting. Visible refs were unique, but hidden component IDs
were not globally unique and the CDB was not aligned with the DSN object-emission
order.

`MIXED_RCL_V12_GLOBAL_IDS_TEMP_2026_06_02` is the next diagnostic pack. It keeps
the V11 physical composition strategy but changes the identity model:

```text
header
one donor-derived V0 power bridge
capacitor outputs
capacitor input/CAPACITOR/wire groups
repeated native L/R pair blocks
```

For V12, each emitted component receives a unique global component ID across all
families, and ROOT.CDB component tables are written in the same order:

```text
T03 example:
  1 -> C1
  2 -> L1
  3 -> R1

T01 6-component example:
  1 -> C1
  2 -> C2
  3 -> L1
  4 -> R1
  5 -> L2
  6 -> R2
```

Static validation now checks for duplicate global component IDs and verifies CDB
table-1 refs and IDs match the emission order. V12 still requires user Proteus
netlist/simulation testing before any promotion.

User testing then narrowed V12:

```text
V12 T03 simple loop: worked
V12 T07 basic voltage divider: worked
remaining multi-component cases: failed
especially cases with additional R, C, or L beyond one of each
```

So global IDs and CDB/object-order alignment fix the single `1C + 1L + 1R`
boundary, but they are not sufficient for scaling.

The next suspected scale boundary is R/L pair ordering. V12 repeated complete
native one-pair blocks:

```text
pair 1: L input, R input, L body, R body
pair 2: L input, R input, L body, R body
...
```

The donor only proves the one-pair rule: both R/L inputs precede that pair's
output/component bodies. It does not prove complete one-pair blocks may be
repeated. `MIXED_RCL_V13_RL_INPUTS_FIRST_TEMP_2026_06_02` therefore keeps V12's
global IDs and CDB ordering but changes the scaled R/L layout to:

```text
all capacitor outputs
all capacitor input/CAPACITOR/wire groups
all R/L input terminals for every pair
all native L/R output-component bodies
```

Static checks confirmed this order in the byte stream. For example, V13 T01 has
global IDs:

```text
1 -> C1
2 -> C2
3 -> L1
4 -> R1
5 -> L2
6 -> R2
```

and the first REALIND/RESISTOR body appears after the full R/L input-terminal
span. V13 still requires user Proteus netlist/simulation testing.

User feedback then rejected V13 for scaling: cases with only one resistor, one
capacitor, and one inductor worked, but cases with additional R/C/L components
still failed. The user supplied
`fixtures/pdsprj/rcl_4x_t07_unit_donor.pdsprj` for more evidence.

## Mixed R/C/L 4x Repeated-Unit Donor

The supplied 4x donor has SHA256:

```text
340b5972d35ce8b63c1aad6048c8fe33a2ea969ae2ad272acc316ce12f8459f5
```

Internal file sizes:

```text
ROOT.DSN  75928
ROOT.CDB   1594
object chunk 8281
```

Object marker counts:

```text
$TERPOWER        1
$TERINPUT       12
$TEROUTPUT       9
$TERGROUND       4
WIRE            25
CAPACITOR        4
CAP10            4
REALIND         12
RESISTOR         8
COMPONENT ID    12
COMPONENT VALUE 12
```

The object chunk is not organized as a pooled capacitor block plus pooled R/L
blocks. It is:

```text
header byte
one V0 power bridge
unit 1
unit 2
unit 3
unit 4
```

Each non-final unit is 2006 bytes:

```text
C output
C input
CAPACITOR
C left wire
C right wire, trimmed 49 bytes
L input
R input
L $TERGROUND output
REALIND
L left wire
L right wire, trimmed 49 bytes
R output
00 boundary byte
RESISTOR
R left wire
R right wire
```

The final unit is 2007 bytes because the final R right-wire record carries the
final `FF` terminator as an extra byte. The observed terminal suffix step is
`0x07d6`, which equals the 2006-byte non-final unit size. The donor's CDB IDs
use this pattern:

```text
unit 1: C1=1,  L1=2,  R1=3
unit 2: C2=6,  L2=7,  R2=8
unit 3: C3=9,  L3=10, R3=11
unit 4: C4=12, L4=13, R4=14
```

The gaps after ID 3 may be a copy/paste artifact, so V14 tests both contiguous
4x IDs and the supplied 4x gap policy.

One more record-level difference matters: the RESISTOR records inside this
mixed donor carry visible value `10k` with length 3. Therefore fields after the
visible value shift by one byte relative to the fixed two-character resistor V9
records. In the donor, the resistor component ID is at `value_offset + 252`
(byte offset 325 for `10k`), and the input/output suffix links start at
`value_offset + 265` and `value_offset + 269`.

`MIXED_RCL_V14_REPEATED_UNIT_TEMP_2026_06_02` uses this donor as a temporary
repeated-unit schema. It emits controls plus 1x, 2x, 3x, 4x, 4x supplied-ID-gap,
6x, 7x, and 21x repeated `V0 -> R -> C -> L -> G0` units for Proteus
open/netlist/simulation testing.

User feedback on V14:

```text
T00 exact donor repack: worked
T00B donor object chunk and CDB inserted into E001: worked
T01 and later generated cases: Bad Object Record and corrupt pink-wire render
```

That result proves the donor object chunk, donor CDB, E001 transplant path, and
DSN section pointer patching are valid. The active failure is generated mutation
inside the object records.

The closest generated 4x case, V14 T05, had the same object chunk length,
marker counts, and ROOT.CDB hash as the working donor. Byte comparison showed
the first unit differed only in terminal label bytes (`VT`/`X1` changed to
`A1`/`B1`), while later units also carried coordinate/component mutations.

`MIXED_RCL_V15_MUTATION_ISOLATION_TEMP_2026_06_02` isolates this:

```text
T00  exact 4x donor chunk in E001 control
T01  first-unit terminal labels only changed to A1/B1
T02  all four units terminal labels changed to unique A#/B# labels
T03  all four units terminal labels changed to repeated N1/N2 labels
T04  failed V14 T05 generated 4x chunk with donor terminal labels restored
T05  exact first donor unit only, 50-byte right wire final FF, 3-component CDB
T06  exact first donor unit only, 50-byte right wire final FF, full donor CDB
T07  exact first donor unit only, 51-byte final right wire, 3-component CDB
```

Interpretation:

```text
If T01 fails, terminal label mutation itself is unsafe in this donor family.
If T01-T03 pass but T04 fails, coordinate/component mutation is the bad-record source.
If T05-T07 fail, shortening the 4x donor object stream is unsafe with this DSN model.
```

User feedback on V15:

```text
T01, T02, and T03 label-only full-donor mutations worked.
T04, the V14 generated 4x body with donor labels restored, gave Bad Object Record.
T05 and T06 one-unit 50-byte final-right-wire variants gave Bad Object Record.
T07, the one-unit 51-byte final-right-wire variant, worked.
```

This proves two separate RCL rules:

```text
terminal label mutation is safe in the full 4x donor stream
shortened RCL streams need the donor-style extra final FF byte
```

The generated-body failure was then traced to wire-coordinate offsets. In the
4x RCL donor, wire coordinates are marker-relative, not fixed-offset:

```text
C and L wire records: WIRE marker at byte 24, coordinates at byte 33
R wire records:       WIRE marker at byte 25, coordinates at byte 34
```

V14 patched every wire at byte 33, corrupting resistor wire records by one
byte. `MIXED_RCL_V16_WIRE_OFFSET_FIX_TEMP_2026_06_02` repeats the V14
repeated-unit diagnostics but patches wire coordinates at `WIRE marker + 9`.
Static checks found no marker, terminator, or wire-coordinate issues. V16 test
order:

```text
T00   exact 4x donor repack control
T00B  4x donor chunk and CDB inserted into E001 control
T01   1 unit / 3 components
T02   2 units / 6 components
T03   3 units / 9 components
T04   4 units / 12 components, contiguous IDs
T05   4 units / 12 components, supplied donor ID gaps
T06   6 units / 18 components
T07   7 units / 21 components
T08   21 units / 63 components
```

User feedback on V16:

```text
All V16 cases worked.
```

This confirms the repeated full-unit method for balanced R/C/L units after the
marker-relative wire fix.

`MIXED_RCL_V17_COMPONENT_REMOVAL_TEMP_2026_06_02` tests the next boundary:
removing whole component subgroups from the accepted V16 unit order. It keeps
the donor subgroup order and preserves final-wire terminator shape for whichever
subgroup ends the object stream. V17 test order:

```text
T00  one full RCL control: V0 -> R -> C -> L -> G0
T01  one RC branch: remove L, C output becomes G0
T02  one LC branch: remove R, C input becomes V0
T03  one RL branch: remove C, R output and L input share A1
T04  one C-only branch: C between V0 and G0
T05  requested 3R/4C/1L project: RCL + RC + RC + C
```

V17 static checks passed: marker counts match requested component counts, WIRE
coordinate windows are marker-relative and sane, component IDs are unique, and
the target T05 contains exactly three resistors, four capacitors, and one
inductor.

User feedback on V17:

```text
All V17 cases worked.
```

This confirms that whole-subgroup removal from accepted repeated RCL units is
safe for temporary mixed R/C/L generation. The accepted group primitives are:

```text
RCL  full unit: R -> C -> L
RC   remove L
LC   remove R
RL   remove C
C    remove R and L
```

`MIXED_RCL_V18_FINAL_TOPOLOGY_TEMP_2026_06_02` applies the V17 method to the
final mixed R/C/L topology test set. It keeps E001 as the base project, emits
one donor-derived V0 power bridge, uses G0 ground endpoints, patches all WIRE
coordinates at `WIRE marker + 9`, and keeps component IDs globally unique with
ROOT.CDB in object-emission order.

V18 test order:

```text
T01  6-component mixed circuit
T02  21-component mixed circuit
T03  simple loop
T04  series circuit
T05  parallel circuit
T06  series-parallel combo
T07  basic voltage divider
T08  multi-step voltage divider
T09  current divider
T10  delta network
T11  star/Y network
T12  delta-to-star setup
T13  Wheatstone bridge
T14  balanced Wheatstone bridge
T15  unbalanced Wheatstone bridge
T16  H-bridge resistor-version topology
T17  R-2R ladder topology
```

V18 static checks passed for all 17 cases: every manifest has zero
`static_validation_issues`, every object chunk starts with `00` and ends with
`FF`, and every generated `.pdsprj` contains `PROJECT.XML`, `ROOT.DSN`,
`ROOT.CDB`, and `SCRIPTS/PWRRAILS.DAT`. The V18 archive SHA256 is:

```text
cd63ac4ee90e434313a6012f178b6e8f2bf3b8fef25400dbab136bc621551c63
```

User feedback on V18:

```text
T02 is not accepted as the 21-component circuit. 21 does not mean merely
placing 21 components; it must follow the accepted 21-circuit topology.
```

The accepted 21 rule, inherited from the earlier 21R and 21RC cases, is:

```text
row 1: V0 -> seven components -> M0
row 2: V0 -> seven components -> M0
row 3: M0 -> seven components -> G0
```

`MIXED_RCL_V19_CORRECT_21_TEMP_2026_06_02` generates only the corrected 21
case for confirmation. It uses accepted V17 group primitives in three visual
rows:

```text
row 1 groups: RCL, RC, LC
row 2 groups: RCL, RL, RC
row 3 groups: RCL, LC, RL
```

This gives exactly `7R / 7C / 7L` and the graph check verifies:

```text
row 1: V0-A1-B1-D1-A2-D2-A3-M0
row 2: V0-A4-B4-E1-A5-E2-A6-M0
row 3: M0-A7-B7-F1-A8-F2-A9-G0
```

V19 static checks passed: zero `static_validation_issues`, no object boundary
issues, required internal `.pdsprj` files present, all 21 components used once
by the three intended paths, and no label is longer than two characters. The
V19 corrected-21 archive SHA256 is:

```text
6e6c38e09c26bec72a6588b379a3f9813fd6d8b01b9cc6db10fff90033bd8d76
```

User feedback on V19:

```text
V19 corrected 21 worked; lock it in.
```

The accepted R/C/L method was promoted into main code as
`src/proteusgen/mixed_rcl.py`. The main generator uses:

```text
base: E001
donor schema: rcl_4x_t07_unit_donor
groups: RCL, RC, LC, RL, C
wire coordinate rule: WIRE marker + 9
component identity: globally unique DSN IDs across R/C/L
CDB order: emitted component IDs
power: one donor-derived V0 bridge
```

The main generator now also supports singleton `R` and `L` groups for circuits
that need to remove two subgroups from an accepted donor unit. The same
byte-length constraint applies to explicit visible values: resistors may use
exactly three ASCII characters, and capacitor/inductor values must also be
exactly three ASCII characters. Compact Proteus-style values such as `10R`,
`50R`, `4u7`, `10u`, and `10m` are used instead of expanding the donor
records.

`MAIN_MIXED_RCL_LOCKED_V1_2026_06_02` generated the locked 17-case pack:

```text
T01  6-component mixed R/C/L case
T02  corrected 21-rule topology, exactly 7R/7C/7L
T03-T17  the 15 requested topology cases
```

Static checks passed for all 17 locked cases: zero
`static_validation_issues`, required internal files present, object chunks start
with `00` and end with `FF`, component refs/IDs and link suffixes are unique,
and the corrected 21 case graph uses all 21 components exactly once across the
three accepted paths. The locked archive SHA256 is:

```text
5a570d480610d8189435b7f249e7a988c1fda987c1541e383e58e652395acc65
```

## DC Voltage Source-Net Diagnostics

The user-made `testing.pdsprj` donor combines a DC-voltage source with the
six-component R/C/L circuit. Its object stream differs from the normal locked
R/C/L power/ground form:

```text
$TERPOWER count: 0
$TERGROUND count: 0
$TERINPUT count: 7
$TEROUTPUT count: 7
VSOURCE markers: 2
CAPACITOR records: 3
REALIND marker groups: 3
RESISTOR markers: 4
WIRE records: 14
```

The observed source-driven net labels are `DV` for the DC-voltage positive net
and `D0` for the negative net. This means source-driven circuits should not
keep the normal `$TERPOWER -> $TEROUTPUT(V0)` bridge or `$TERGROUND(G0)`
endpoints unless a later donor proves otherwise. The source positive side is
represented by an ordinary output terminal, and the source negative side by an
ordinary input terminal.

`DC_SOURCES_V5_SOURCE_NET_TEMP_2026_06_03` is a temp-only diagnostic batch based
on this observation and the current locked `src/proteusgen/mixed_rcl.py`
generator:

```text
T00 manual combined donor object/CDB transplanted into E001
T01 manual combined donor with DV->P0 and D0->N0 terminal-label mutation
T02 generated R/C/L body using DV/D0 source nets, no source object
T03 generated DC source first, then generated R/C/L source-net body
T04 generated R/C/L source-net body first, then generated DC source
```

All five static cases contain the required `.pdsprj` internals and report zero
static validation issues. The archive SHA256 is:

```text
e3d9dab3fe61dca27997271e33f800ff538a23552d9c1bea5e76808b8ee6a658
```

User feedback on V5:

```text
T00 worked.
T01 worked.
T02 worked.
T03 and T04 failed with VGC/VG... dll errors.
```

This confirms the source-net conversion itself is not the active blocker:
generated R/C/L with `DV` and `D0` ordinary terminals works when no source
object is inserted. The remaining blocker is the generated `VSOURCE` object
block and/or its `ROOT.CDB` source metadata.

The working manual combined donor uses this source-region structure:

```text
ordinary DV anchor input before source block
DV output terminal
D0 input terminal
VSOURCE record
source wire 1: 50 bytes
source wire 2: 49 bytes when non-final
```

`DC_SOURCES_V6_SOURCE_BLOCK_FIX_TEMP_2026_06_03` is the focused follow-up pack.
It does not change the working generated source-net R/C/L body. It only varies
the source object block:

```text
T00 source-net R/C/L no-source control
T01 source first, preserve standalone source suffix/link bytes, trim non-final source wire 2 to 49 bytes
T02 source first, keep V5 patched suffixes, trim non-final source wire 2 to 49 bytes
T03 source first, exact manual source block without the extra DV anchor
T04 generated R/C/L first, then manual source block made final
T05 source first, exact manual source block plus full manual combined donor ROOT.CDB
T06 source first, manual source block plus the extra ordinary DV anchor and manual ROOT.CDB
```

V6 static checks passed: every case contains `PROJECT.XML`, `ROOT.DSN`,
`ROOT.CDB`, and `SCRIPTS/PWRRAILS.DAT`, every manifest reports zero
`static_validation_issues`, and the focused mixed R/C/L regression test passed:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V6 archive SHA256 is:

```text
ab52c82f7281bf0c763160d6cc0519ba6163eebbc89c628ff971252361606d77
```

User feedback on V6:

```text
T02 failed with VG/VGC... dll.
T04 failed with VG/VGC... dll.
```

Proteus workspace side files were created for `T00`, `T01`, `T03`, `T05`, and
`T06`, but not for `T02` or `T04`. This matches the user feedback and rejects
two methods:

```text
Do not use V5/resistor-style patched source suffixes.
Do not place the source block after the generated R/C/L body.
```

The accepted source direction for the next pack is:

```text
source block first
preserve standalone/manual source terminal and component suffix bytes
patch only the source global component ID
use the 49-byte non-final source wire 2 shape before appending the R/C/L body
keep source-driven nets as ordinary DV/D0 terminals
```

`DC_SOURCES_V7_ACCEPTED_SOURCE_FIRST_TEMP_2026_06_03` applies that rule to the
requested source-driven mixed R/C/L scale tests:

```text
T01  six-component mixed R/C/L circuit with DC-voltage source
T02  corrected 21-rule mixed R/C/L circuit with DC-voltage source
T03  corrected 21-rule fallback using the manual source block
```

All V7 cases use `DV`/`D0`, contain no `$TERPOWER` or `$TERGROUND` records, and
contain no `V0` or `G0` terminal labels. Static checks passed for all three
cases and the focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V7 archive SHA256 is:

```text
307ce9bd305be6519041307fe7545bd96bcf5d065cb562087c8f286e821ec9ec
```

User feedback on V7:

```text
all V7 cases worked
```

This confirms the source-first DC-voltage method for the 6-component and
corrected 21-rule mixed R/C/L scale cases.

## DC Voltage And Current 15-Topology Pack

The user-created DC-current donors show a related but not identical standalone
source shape:

```text
dc_current_01_default object chunk length: 653
terminal order: $TERINPUT(I0), then $TEROUTPUT(DI)
source model: CSOURCE
source ref/value: I1 / 1A
source wire 2 final length: 51 bytes
```

Therefore V8 uses these source-net conventions:

```text
DC voltage: positive net DV, negative net D0, source model VSOURCE
DC current: positive net DI, negative net I0, source model CSOURCE
```

`DC_SOURCES_V8_15_VOLTAGE_15_CURRENT_TEMP_2026_06_03` applies the V7
source-first method to the 15 locked mixed R/C/L topology cases:

```text
T01-T15: DC-voltage source-driven versions using DV/D0
T16-T30: DC-current source-driven versions using DI/I0
```

Current-source cases use a combined device section built from the accepted
R/C/L donor device section plus the standalone `CSOURCE` donor device section.
All V8 cases preserve native source suffix bytes, patch only source global IDs,
place the source block before the generated R/C/L body, and remove the normal
power/ground bridge.

V8 static checks passed for all 30 cases:

```text
required internals present: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
$TERPOWER count: 0
$TERGROUND count: 0
V0/G0 terminal labels: 0
manifest static_validation_issues: []
```

The focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V8 archive SHA256 is:

```text
074c148d8b0c1a06d5ada2f213898a0e493b5e5f3ac8280e9bed7fa6cf962e1e
```

User feedback on V8:

```text
all DC-voltage cases worked
no DC-current cases worked
```

This accepts the DC-voltage 15-topology pack and rejects the V8 DC-current
method. Since the same R/C/L source-net topology generator worked for DC voltage,
the failure boundary is the current source insertion method, not the passive
R/C/L body layout.

## DC Current Connected-Source Diagnostics

The working user-created current-source load donor differs from the standalone
current source used in V8:

```text
dc_current_03_resistor_load object chunk length: 1310
first source/load records:
  input terminal I0:     chunk[1:104]
  output terminal DI:    chunk[104:208]
  CSOURCE record:        chunk[208:555]
  source wire 1:         chunk[555:605]
  source wire 2 nonfinal chunk[605:655]
source ref/value: I4 / 500mA
source model: CSOURCE
CDB order: passive resistor record before current-source record
```

`DC_CURRENT_V9_CONNECTED_SOURCE_DIAGNOSTICS_TEMP_2026_06_03` tests this donor
shape against the rejected V8 standalone source shape:

```text
T00 standalone current-source donor transplanted into E001
T01 connected current-source + resistor-load donor transplanted into E001
T02 generated DI/I0 source-net R/C/L body, no current source
T03 generated simple R/C/L, connected CSOURCE block, fixed I4, 500mA, source-last CDB
T04 generated simple R/C/L, connected CSOURCE block, fixed I4, 500mA, source-first CDB
T05 generated simple R/C/L, V8 standalone I1/1A CSOURCE block, source-last CDB
T06 generated six-component R/C/L, connected CSOURCE block, fixed I4, 500mA, source-last CDB
T07 generated six-component R/C/L, connected CSOURCE block, visible source ref patched to ID, source-last CDB
```

V9 static checks passed for all 8 cases:

```text
required internals present: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
$TERPOWER count: 0
$TERGROUND count: 0
V0/G0 terminal labels: 0
manifest static_validation_issues: []
```

The focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V9 archive SHA256 is:

```text
79823f09870e3f9d4aecd089d90663df222dcf86d6c4d54ba6589e1e9697d3aa
```

User feedback on V9:

```text
T03 and onward gave ISIS/VG dll errors
```

The failure starts at generated current-source cases, while donor controls and
the no-source generated body were not reported as failing. Therefore the
connected CSOURCE block alone is still insufficient before generated R/C/L body
records.

## DC Current Anchor Terminal Diagnostics

The exact connected current-load donor places a load-side anchor terminal pair
immediately after the source block:

```text
source block:            chunk[1:655]
load-side anchor pair:   chunk[655:858]
  DI $TERINPUT
  I0 $TEROUTPUT
resistor body starts:    chunk[858]
```

`DC_CURRENT_V10_ANCHOR_TERMINALS_TEMP_2026_06_03` tests preserving that donor
anchor pair before appending generated load records:

```text
T00 exact connected current-source + resistor-load donor transplanted into E001
T01 generated resistor-only load with connected CSOURCE block plus DI/I0 anchor pair
T02 generated simple R/C/L load with connected CSOURCE block plus DI/I0 anchor pair
T03 generated six-component R/C/L load with fixed visible source ref I4
T04 generated six-component R/C/L load with visible source ref patched to the source ID
```

V10 static checks passed for all 5 cases:

```text
required internals present: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
$TERPOWER count: 0
$TERGROUND count: 0
V0/G0 terminal labels: 0
manifest static_validation_issues: []
```

The focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V10 archive SHA256 is:

```text
480ec22bb825792cf7fb4e74db9b18734867e6f2c7b553ed36052fba32b692db
```

User feedback on V10:

```text
T02, T03, and T04 all gave ISIS dll errors
```

T00/T01 were not reported as failing. This keeps the connected current donor
and generated resistor-only load as useful controls, but rejects the V10 mixed
R/C/L cases.

The V10 mixed device section did not match the accepted DC-voltage source
metadata shape:

```text
Accepted DCV mixed source device section:
  CAP + REALIND + RESISTOR + VSOURCE

Rejected V10 DCI mixed source device section:
  CAP + REALIND + RESISTOR + CSOURCE + RESISTOR
```

The duplicate `RESISTOR` device entry came from combining the full R/C/L donor
device table with the connected current-load donor table. Since the DCV cases
worked with one clean device entry per family, V11 tests that same metadata
shape for current sources.

## DC Current DCV-Style Device Diagnostics

`DC_CURRENT_V11_DCV_STYLE_DEVICES_TEMP_2026_06_03` keeps the current source
geometry from the V10 controls, but uses the accepted DCV-style clean device
table for mixed cases:

```text
CAP + REALIND + RESISTOR + CSOURCE
```

V11 test order:

```text
T00 exact connected current-source + resistor-load donor transplanted into E001
T01 generated resistor-only load with connected source and current-load donor devices
T02 generated simple R/C/L load with connected source + anchor terminals and clean devices
T03 generated six-component R/C/L load with connected source + anchor terminals and clean devices
T04 generated simple R/C/L load with connected source, no anchor terminals, and clean devices
T05 generated simple R/C/L load with standalone current source and clean devices
```

V11 static checks passed for all 6 cases:

```text
required internals present: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
$TERPOWER count: 0
$TERGROUND count: 0
V0/G0 terminal labels: 0
manifest static_validation_issues: []
mixed device marker counts: CSOURCE 1, RESISTOR 1, CAPACITOR 1, REALIND 2
```

The focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V11 archive SHA256 is:

```text
63461232a5d51ab7f2a84469527d2f7f6092db409ffca84009ee65352271d4df
```

User feedback on V11:

```text
all V11 cases gave ISIS dll errors
```

This rejects the clean-device-table hypothesis by itself. The source identity
and/or object geometry is still wrong when using the DI/I0 current-source donor
family.

## DC Current Manual Testing Study

The user supplied a new manual reference:

```text
C:\Users\tahab\Downloads\testing.pdsprj
last write: 2026-06-03 15:50:56
```

Byte-level inspection of this file shows a different DC-current source pattern:

```text
source nets: DV / D0
source reference/value: V1 / 10V
visible object subckt text: VSOURCE
final object model marker: CSOURCE
ROOT.CDB source model: CSOURCE
device table model: CSOURCE
device table order: CAP + CSOURCE + REALIND + RESISTOR
normal power/ground terminals: none
```

The manual source unit is:

```text
chunk[2187:2942]
contains:
  DV $TERINPUT
  DV $TEROUTPUT
  D0 $TERINPUT
  V1/10V source object with visible VSOURCE and model CSOURCE
  D0 $TEROUTPUT
```

`DC_CURRENT_V12_MANUAL_TESTING_STUDY_TEMP_2026_06_03` tests this new model:

```text
T00 exact supplied manual testing.pdsprj copied without repacking
T01 manual object chunk, CDB, and device table transplanted into E001
T02 generated simple R/C/L using accepted DCV source geometry patched to CSOURCE
T03 generated six-component R/C/L using accepted DCV source geometry patched to CSOURCE
T04 generated six-component R/C/L using the exact manual source unit
```

V12 static checks passed for all 5 cases:

```text
required internals present: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
$TERPOWER count: 0
$TERGROUND count: 0
V0/G0 terminal labels: 0
manifest static_validation_issues: []
```

The focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V12 archive SHA256 is:

```text
f94eef38f4d4fa2d00ae0962dda2cf21b8955d9f29474f66b53805990f71dd18
```

User feedback on V12:

```text
all V12 cases worked
```

This confirms the DC-current correction direction: use the accepted DC-voltage
source geometry and ordinary `DV`/`D0` source-net terminals, but patch the
source identity to `CSOURCE` in the final object model marker, `ROOT.CDB`, and
device table.

## DC Current 15-Topology V13 Pack

`DC_CURRENT_V13_15_TOPOLOGIES_TEMP_2026_06_04` applies the V12 confirmed
method to the 15 requested mixed R/C/L topology cases.

Generation rules:

```text
input topology source net: V0 -> DV
input topology return net: G0 -> D0
power/ground terminal records: none
source geometry: accepted DCV source-first geometry
visible source text: VSOURCE
source model metadata: CSOURCE
source reference/value: V1 / 10V
device table: CAP + CSOURCE + REALIND + RESISTOR
ROOT.CDB source order: source record after passive records
```

V13 test order:

```text
T01 SIMPLE_LOOP
T02 SERIES_CIRCUIT
T03 PARALLEL_CIRCUIT
T04 SERIES_PARALLEL_COMBO
T05 BASIC_VOLTAGE_DIVIDER
T06 MULTI_STEP_VOLTAGE_DIVIDER
T07 CURRENT_DIVIDER
T08 DELTA_NETWORK
T09 STAR_Y_NETWORK
T10 DELTA_TO_STAR_SETUP
T11 WHEATSTONE_BRIDGE
T12 BALANCED_WHEATSTONE_BRIDGE
T13 UNBALANCED_WHEATSTONE_BRIDGE
T14 H_BRIDGE_RESISTOR_VERSION
T15 R_2R_LADDER_NETWORK
```

V13 static checks passed for all 15 generated topology cases:

```text
required internals present: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
$TERPOWER count: 0
$TERGROUND count: 0
V0/G0 terminal labels: 0
visible VSOURCE marker count: 1
final/model CSOURCE marker count: 1
source terminals: DV / D0
manifest static_validation_issues: []
```

The focused mixed R/C/L regression test still passes:

```text
python -m pytest tests/test_mixed_rcl.py -q
7 passed, 34 subtests passed
```

The V13 archive SHA256 is:

```text
00e49a929489ac178de9b9d366ce24dced510aa497d0b9c653ba0e20ddd8bfe7
```

User feedback on V13:

```text
all V13 DC-current source-driven topology cases worked
```

This locks the DC-current source method for the current source-driven R/C/L
scope. Combined with the earlier accepted DC-voltage V7/V8 results, the DC
source rule is now:

```text
source-driven circuits do not emit default V0/G0 power/ground terminals
DC voltage: source-first VSOURCE with ordinary DV/D0 source-net terminals
DC current: same source-first geometry and DV/D0 source-net terminals, but CSOURCE metadata
```

The rejected path remains important negative evidence:

```text
Do not use standalone DI/I0 current-source donor geometry for generated mixed R/C/L circuits.
```

## AC Source Onboarding

AC voltage and AC current source generation should start from user-created
Proteus 8.13 donors, matching the DC source workflow:

```text
one default AC voltage source with positive/negative ordinary terminals
one AC voltage source with a non-default value/frequency if Proteus exposes those fields
one AC voltage source driving a simple resistor load
one default AC current source with positive/negative ordinary terminals
one AC current source with a non-default value/frequency if Proteus exposes those fields
one AC current source driving a simple resistor load
optional combined AC source plus small R/C/L load donor if source insertion differs from DC
```

For AC donors, use restricted ordinary source-net labels equivalent to the DC
`DV`/`D0` pair, but AC-specific so future transforms cannot collide with DC
rules. Suggested starting labels are `AV` and `A0`.

## AC Voltage V1 Source Diagnostics

The user supplied four AC-voltage source donors:

```text
ac_voltage_01_default.pdsprj
ac_voltage_02_variant.pdsprj
2xac_voltage_02_variant.pdsprj
ac_voltage_03_resistor_load.pdsprj
```

Observed AC-voltage source model:

```text
source nets: AV / A0
source model: VSINE
ROOT.CDB ref: V1
ROOT.CDB value field: VSINE
ROOT.CDB model field: VSINE
properties: {VA=...}, {FREQ=...}, {PRIMITIVE=ANALOGUE}
normal power/ground terminals in source object chunk: none
```

The load donor device section already contains the required mixed source table
families:

```text
VSINE + CAPACITOR + REALIND + RESISTOR
```

`AC_VOLTAGE_V1_SOURCE_DIAGNOSTICS_TEMP_2026_06_04` tests exact controls and
generated source insertion variants.

Test order:

```text
T00 exact default donor copy
T01 default donor object/CDB/device transplant into E001
T02 variant donor object/CDB/device transplant into E001
T03 two-source donor object/CDB/device transplant into E001
T04 generated six-component R/C/L AV/A0 body with no source object
T05 generated simple-loop R/C/L with source-first standalone VSINE block
T06 generated six-component R/C/L with source-first standalone VSINE block
T07 generated six-component R/C/L with source-last load-donor VSINE block
T08 generated corrected 21-rule R/C/L with source-first standalone VSINE block
T09 generated corrected 21-rule R/C/L with source-last load-donor VSINE block
```

V1 static checks passed:

```text
projects generated: 10
required internals present in all projects: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
manifest static_validation_issues: []
generated source-only variant ROOT.CDB matches ac_voltage_02_variant ROOT.CDB byte-for-byte: true
focused mixed R/C/L regression: 7 passed, 34 subtests passed
```

The V1 archive SHA256 is:

```text
985630d2c7d98f97281679ae58fcce798e91f8a3791d787e5a761225217c76a0
```

User feedback on V1:

```text
T00 through T04 worked
T05 and onward gave VGDVC.dll error
```

This means exact donor copies, E001 transplants, and the generated `AV`/`A0`
R/C/L body without a source are valid. The failure starts when a generated
VSINE source is inserted.

The likely V1 source-insertion fault is non-final source unit shape. The
standalone variant source body is 674 bytes, ending in a final 51-byte wire.
The `2xac_voltage_02_variant` donor shows the first non-final `AV`/`A0` source
unit is exactly 673 bytes:

```text
output AV: 104 bytes
input A0: 103 bytes
V1 VSINE source record: 366 bytes
wire 1: 50 bytes
wire 2 non-final: 50 bytes
```

## AC Voltage V2 Non-Final Source Unit

`AC_VOLTAGE_V2_NONFINAL_SOURCE_UNIT_TEMP_2026_06_04` tests the exact non-final
source unit from the two-source donor.

Test order:

```text
T00 two-source donor transplant control
T01 generated six-component R/C/L AV/A0 body with no source object
T02 simple-loop R/C/L with exact two-source non-final AV/A0 VSINE unit
T03 six-component R/C/L with exact two-source non-final AV/A0 VSINE unit
T04 corrected 21-rule R/C/L with exact two-source non-final AV/A0 VSINE unit
T05 simple-loop R/C/L with standalone variant source block trimmed to non-final length
T06 six-component R/C/L with standalone variant source block trimmed to non-final length
```

V2 static checks passed:

```text
projects generated: 7
required internals present in all projects: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
manifest static_validation_issues: []
focused mixed R/C/L regression: 7 passed, 34 subtests passed
```

The V2 archive SHA256 is:

```text
8bdd36e0bae520940dbc7534bd0931cf2724df5d9a306eaa42900be8769ad492
```

User feedback on V2:

```text
All V2 cases worked.
```

AC current source generation is out of scope for the current release by user
decision, so the next source work moved to mixed DC voltage/current source
circuits.

## DC Mixed Sources V1 Requested Five Circuits

`DC_MIXED_SOURCES_V1_REQUESTED5_TEMP_2026_06_04` generates the five complex
R/C/L circuits requested by the user, each containing mixed DC voltage and DC
current sources.

Method under test:

```text
source object order: all source units first, then generated R/C/L body
source geometry: user-made 4x DC voltage donor source units
DC voltage identity: VSOURCE in ROOT.DSN, ROOT.CDB, and device table
DC current identity: accepted DCV geometry with final model marker, ROOT.CDB, and device table patched to CSOURCE
source terminal labels: ordinary source-net terminals, patched to the circuit nodes
default power/ground symbols: not emitted
R/C/L body: accepted mixed_rcl source-net subgroup generator
```

The five generated projects are:

```text
T01 DCMS_V1_T01_CIRCUIT_1_12V_2A
T02 DCMS_V1_T02_CIRCUIT_2_TWO_5V_1A
T03 DCMS_V1_T03_CIRCUIT_3_24V_TWO_0A5
T04 DCMS_V1_T04_CIRCUIT_4_TWO_15V_TWO_3A
T05 DCMS_V1_T05_CIRCUIT_5_THREE_9V_1A5
```

Static checks passed:

```text
projects generated: 5
required internals present in all projects: PROJECT.XML, ROOT.DSN, ROOT.CDB, SCRIPTS/PWRRAILS.DAT
manifest static_validation_issues: []
focused mixed R/C/L regression: 7 passed, 34 subtests passed
```

The V1 archive SHA256 is:

```text
c1865a2cb96a3770c0315dc42f2b1a3e1b12c4c628627be9d19216d2600838b9
```

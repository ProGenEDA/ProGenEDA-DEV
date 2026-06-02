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

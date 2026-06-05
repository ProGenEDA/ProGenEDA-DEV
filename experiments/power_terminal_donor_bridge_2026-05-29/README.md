# Power Terminal Donor-Bridge Attempt

## Source donor uploaded by user

```text
filename: New Project(1).pdsprj
size_bytes: 11029
sha256: d06b97bec98b2a6990a3e9e948afa0a848acc56815c4c5ee458d4e2f4c979d55
```

## What was found in the donor

The donor project is a Proteus 8.13 `.pdsprj` container with:

```text
SCRIPTS/PWRRAILS.DAT
ROOT.CDB
ROOT.DSN
PROJECT.XML
```

Important ROOT.DSN marker counts:

```text
$TERPOWER  = 2 occurrences
$TEROUTPUT = 2 occurrences
$TERINPUT  = 2 occurrences
$TERGROUND = 1 occurrence
WIRE       = 6 occurrences
RESISTOR   = 3 string occurrences, including the component marker/metadata
N1         = 2 occurrences in ROOT.DSN
```

Important observation:

The donor contains a real user-created bridge sequence in the actual object data:

```text
$TEROUTPUT(N1)
$TERPOWER
WIRE
$TERINPUT(N1)
RESISTOR R1
WIRE
```

This differs from the failed generated bridge attempts, which generated a standalone bridge with an unsafe ordering/layout.

## Extracted bridge cluster

The extracted donor bridge cluster is the front part of the donor actual OBJECT DATA stream before the donor `$TERINPUT` object.

```text
donor_bridge_cluster_len: 256 bytes
contains: $TEROUTPUT, $TERPOWER, WIRE
label used by bridge output terminal: N1
```

## New generated attempt

Generated from blank E001:

```text
POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT
```

Method:

```text
1. Extract exact donor bridge cluster from New Project(1).pdsprj.
2. Insert that bridge cluster at the start of generated ROOT.DSN object data.
3. Generate normal R21 V9 resistor network after it.
4. Rename the R21 start node to N1 so the donor output terminal N1 should match the resistor endpoint terminals.
5. Generate ROOT.CDB and ROOT.DSN from blank E001.
```

Topology summary:

```text
Branch A starts at N1 through R1.
Branch B starts at N1 through R8.
Tail starts at M0 and ends at Z0.
Bridge cluster is $TEROUTPUT(N1) + $TERPOWER + WIRE.
```

## Output ZIP

```text
filename: POWER_TERMINAL_DONOR_BRIDGE_ATTEMPT_2026_05_29.zip
size_bytes: 48272
sha256: a8b891667fd3ee4986a2f580222b7937b2b99ab77b6c3ebada5b3f89891eefe8
```

## Main project

```text
project: POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT.pdsprj
project_sha256: d3e131e9e25c4570d1974974653f16237412a41c0b111fc939f0828382ea410d
ROOT.DSN sha256: 60230d4b3fddd7cba7c3960122b2876271b58331093fe62f2e89a91c6c6c8c4e
ROOT.CDB sha256: c5761d5ea7c1f9eb4ab831e32cc16110e48b98de87f42466e507581ceed31b84
```

## Static validation

```text
static_validation_issues: []
TERPOWER: 1
TEROUTPUT: 22
TERINPUT: 21
WIRE: 43
resistor_count: 21
```

## Test order

```text
1. POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT/CONTROL_E001_EMPTY_BASE.pdsprj
2. POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT/POWER_T10_R21_N1_DONOR_BRIDGE_ATTEMPT.pdsprj
```

## What to check

```text
Does it open without VGDVC.dll error?
Does the donor-style power/output bridge appear?
Does the bridge output terminal show N1?
Does the R21 circuit start node N1 appear connected to the bridge by same terminal name?
Any netlist/model/simulation warnings?
Does save-as/reopen preserve it?
```

## Interpretation

If this works, then the previous bridge failures were caused by our generated bridge record layout/order, not by the concept itself.

If this fails, then the donor bridge cluster cannot simply be transplanted into the V9 generator stream and will need a more exact donor-derived section reconstruction.

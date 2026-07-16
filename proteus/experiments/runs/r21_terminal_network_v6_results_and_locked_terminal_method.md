# R21 Terminal Network V6 Results and Locked Terminal Method

## User-observed V6 result

The user tested:

```text
R21_TERMINAL_NETWORK_V6_FIXED_TERMINAL_LABEL_PATCH.zip
```

Observed result:

```text
TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL opened and displayed all 21 resistors.
TEST_R21_V6_TWO_TERMS_N0_A1_FIXED_LABELPATCH_E0_TAIL opened.
TEST_R21_V6_TWO_TERMS_B6_M0_FIXED_LABELPATCH_E0_TAIL opened.
A terminal-containing all-terms variant opened and showed the generated terminal set.
Remaining larger/wire variants produced bad-object/circuit-data-lost style errors or incorrect geometry.
```

The user concluded:

```text
terminal records are now structurally successful, with coordinate/layout issues remaining.
```

## Locked terminal technique

The terminal writer should now preserve the V6 fixed-offset patch method.

### Do not use string search to patch terminal labels

Old unsafe method:

```text
replace label bytes
search for the new label bytes in the binary record
patch label coordinates near first match
```

Why it failed:

```text
labels like B6 can naturally appear inside coordinate bytes.
The search can hit binary coordinate data instead of the label field.
That corrupts the terminal object record.
```

### Correct method

Patch fixed terminal fields directly.

Input terminal:

```text
symbol x/y  @ +1/+5
label len   @ +30
label bytes @ +31..+32
label x/y   @ +33/+37
```

Output terminal:

```text
symbol x/y  @ +1/+5
label len   @ +31
label bytes @ +32..+33
label x/y   @ +34/+38
```

This method successfully handled both:

```text
N0/A1 labels
B6/M0 labels
```

## Current stable layers

Validated/stable enough to promote:

```text
21 resistor CDB writer
21 resistor visible DSN writer
2-character resistor refs with RA/RB/etc fallback
actual CDB values up to 21k
small terminal generation with fixed-offset label patching
large terminal generation structurally opens in at least one V6 all-terminal case
```

## Still not fully solved

```text
terminal coordinate placement is not yet correct
wire record generation is not yet reliable
bad-object errors still occur in some large/wire variants
true resistor-to-terminal electrical attachment is not yet validated
```

## Important engineering decision

For the next attempt, avoid explicit wire records at first.

Instead use a pin-contact strategy:

```text
place terminal symbol endpoints exactly on resistor pin coordinates
use repeated terminal labels to define shared nodes
avoid separate wire objects until terminal+component attachment is validated
```

Reason:

```text
The wire variants are still the most fragile part.
Terminals now open when generated correctly.
Resistors already open and simulate.
The safest next bridge is exact coordinate contact between terminal endpoints and resistor pins.
```

## Next generator target

Generate the requested R21 topology using:

```text
E001 base
21 generated CDB-backed resistors
42 generated terminals using V6 fixed-offset patching
no explicit wire records
terminal endpoints placed directly at resistor pins
node labels repeated according to topology
```

Expected topology:

```text
7 resistors in series
parallel with another 7 resistors in series
then 7 more resistors in series after that parallel block
```

If this opens and simulates, it becomes the first usable arbitrary-resistor-network method.

If it opens visually but netlisting is wrong, the remaining issue is physical endpoint snapping/contact semantics.

If it fails with bad object record, the all-terminal count/ordering still needs one more correction.

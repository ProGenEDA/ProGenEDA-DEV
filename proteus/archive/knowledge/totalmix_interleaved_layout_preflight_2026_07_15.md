# Unified totalmix interleaved-layout preflight — 2026-07-15

## Trigger and authoritative visual evidence

The user rejected the earlier 15x all-family artifact after opening it: the
visible page showed a row of one family rather than an intelligible mixed
circuit. That rejection overrides the earlier loader-only acceptance claim.

I cold-opened the user-supplied
`experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`
in Proteus and inspected the schematic canvas. Its ROOT.DSN contains one
packet for each of the 49 current supported families, and its visible region
contains a genuine mixture of IC and non-IC components. This donor is the
layout intent oracle; no ROOT.CDB comparison is needed for this investigation.

The rejected generated 15x DSN really contains 725 component packets and
4,650 terminal/WIRE units. It is nevertheless not an acceptable mixed-layout
test artifact: the compact placement transform places source-order family
blocks in separate IC/non-IC bands, so the visible page can show only one
family while the remaining families lie far away.

## Complete cause inventory

1. `_select_raw_groups` preserves donor object-stream order. That is correct
   for ROOT.DSN serialization and terminal link ordering, but it is the wrong
   order to use as the *visual* schedule for a mixed stress circuit.
2. The compact-family option preserves those blocks and additionally splits IC
   and non-IC groups into separate visual bands.
3. A 15x matrix therefore has 15 adjacent same-family objects before the next
   family. The first accessible canvas region is not a mixed sample.
4. The terminal emitter is not the cause: the DSN audit proves all packets,
   terminals, WIREs, and rebased links exist. It must remain unchanged.

## Evidence-backed repair scope

Add an explicit, opt-in component-placer layout policy only:

- retain the original selected-group/root-stream order;
- schedule *visual placement* round-robin by requested family, so each round
  contains one available instance of every family;
- disable the separate IC/non-IC visual bands only for this opt-in policy;
- require existing compact flow when the policy is selected;
- retain all current/default beautifier behavior and all terminal attachment
  paths unchanged;
- prove the first visual round contains both IC and non-IC families, then
  regenerate a 1x all-family mix before any scale pack.

The repair must not move terminal logic, copy donor terminal packets, reorder
the final component stream, alter accepted-family geometry, or use a new donor.

## Native-prefix localization preflight — 2026-07-15

### Authority and scope

Authority remains the user-accepted
`experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`.
The user explicitly limited this investigation to `ROOT.DSN`; `ROOT.CDB` is
not read or changed by this repair.

The actual 1x visual comparison is decisive: the new bare interleaved control
renders R1 and C1, while its terminalized counterpart renders R1/C1 terminal
markers but not their red component bodies.  7447 and 7490 bodies still render.
This is therefore a native attachment-stream error, not a component-placement
or screenshot issue.

### Complete DSN finding

The donor's native R/C unit is contiguous.  Its object stream begins with the
right CAP terminal `C1`, followed by `R001A`, `R001B`, the R1 packet and its
two WIREs, then the left CAP terminal `C0`, C1's packet and its two WIREs.
There is only the donor-proven one-byte separator between a terminal and its
following component packet.  Each active terminal suffix equals the low 16
bits of its final WIRE address.

The rejected generated stream has the same terminal coordinates, angles,
nonzero WIRE endpoints, and rebased suffixes, but serializes `C1`, `R001A`,
and `R001B` at the global beginning of the stream.  It then inserts the 7447,
7490, and other catalogue terminal/component/WIRE blocks before the R1 packet
at byte 33703.  This separates the native leading terminal unit from its
component by unrelated active objects.  That fully explains why only the
native component bodies disappear while their terminals remain.

### Evidence-backed repair boundary

Only `totalmix_combined_v1` changes.  Keep component packet order unchanged.
Defer the already-planned R/C leading terminal prefix until immediately before
the first native component in the selected stream, and make the prior packet
use the donor-proven trimmed boundary before that terminal zone.  The existing
R/C local sequence, grid-contact geometry, WIRE schema, suffix rebasing, and
all non-totalmix/accepted family routes remain unchanged.

Backup created before this edit:
`backups/component_terminal_placer/component_terminal_placer_20260715_125300_before_native_prefix_localization.py`.

Required proof: a focused structural regression must prove the contiguous
`C1`, `R001A`, `R001B`, R1 sequence even when R1 occurs after catalogue
components; then a new interleaved 1x bare/terminalized visual gate must show
both R1/C1 and multiple IC/non-IC families before any scale output is made.

## Reopened cumulative-stream diagnosis â€” 2026-07-15

The visual test rejected the first all-49 terminalized candidate.  Its bare
control renders multiple placed families, while the terminalized version
renders only the first visible R/C/7447/7490 subset.  Therefore a component
count or static link audit is not acceptance evidence: the shared terminal
emitter still has a mixed object-stream ordering defect.

Complete ROOT.DSN event decoding of the accepted donor and candidate shows the
concrete phase difference.  The accepted donor serializes, by component
*family* (never donor slot or reference):

```text
native R/C and native inline families -> NPN tail anchor
-> current/control/BJT tail attachments
-> 74HC76, 7490, 7447, 74HC283, 74HC192, 74HC174, 74HC160, 74HC157, 74HC85
-> logic-tail families -> 4027
```

The rejected candidate instead began R/C and then emitted the locked mega's
source-order catalogue packets (`7447`, `7490`, `4511`, `4027`, ...), only
reaching most native/control families much later.  Its attachment records were
present but this breaks the donor-proven phase grammar and Proteus stops
rendering most component bodies.

An unpromoted `totalmix_combined_v1` profile change now stores the complete
family-phase order as catalogue data.  It retains the placed packet bytes,
references, and translated coordinates; only the final ROOT.DSN backend
serialization order is normalized by family profile.  This is a hypothesis,
not an acceptance claim.

Per user direction, validation now uses a cumulative ladder and stops at the
first visual loss instead of jumping directly to all 49 families:

1. `RESISTOR + CAP` through the shared terminal placer.
2. Add `7490 + 7447` through the shared mixed terminal entrypoint.
3. Add `4511 + 4027`.
4. Continue two families at a time in the documented profile phase order.

Every rung uses a fresh locked-mega component-placer project.  A rung only
advances after Proteus visibly renders all prior and newly added component
bodies with their terminal/WIRE attachments.  At the first failure, compare
that rung only with its preceding passing rung and the accepted donor before
making one evidence-backed shared-emitter edit.

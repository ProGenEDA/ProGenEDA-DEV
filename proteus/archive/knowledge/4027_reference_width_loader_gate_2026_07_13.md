# 4027 reference-width loader repair - 2026-07-13

## Authority and scope

The actual accepted 4027 donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj`.
The only placement source is the locked mega donor. This investigation reads
and compares `ROOT.DSN` only; it neither reads nor compares `ROOT.CDB`.

## User-directed Bad Object Record recovery

The rejected direct-contact candidate displayed:

`Bad object record - circuit data lost.`

As directed, a disposable copy was captured before dismissal, opened after
**OK**, saved with **Ctrl+S**, captured again before closing, and compared
against the generated DSN. Proteus retained the first A terminal/component
prefix and discarded the stream at the first WIRE. The generated attachment
unit was therefore structurally close enough to recover a prefix, but not
valid enough to retain the full A/B stream.

Evidence:

- `06_local_proteus_gate/G08_4027_1X_BOR_BEFORE_OK.png`;
- `06_local_proteus_gate/G08_4027_1X_AFTER_OK_SAVE_BEFORE_CLOSE.png`;
- `06_local_proteus_gate/G08_4027_1X_DONOR_CONTACT_BOR_SAVE_COPY.pdsprj`.

## Complete donor-frame finding

The accepted donor has `U1:A/B` physical references. The locked mega
selected `U13:A/B`, which adds one literal reference byte to each
component packet. The prior profile declared a two-byte link-prefix trim,
mistaking this reference-width delta for padding. It shortened active
locked-mega packets to the donor's raw packet length and put their active
link/WIRE boundaries one byte early.

The donor proves exactly one removable zero before the active 28-byte link
array. The profile now uses:

`subpart_link_prefix_zero_trim_count: 1`

No accepted two-pin, HC74, HC76, or other frozen terminal route was changed.

## Expected and observed stream boundary

| Boundary | Accepted donor | Regenerated locked mega |
| --- | ---: | ---: |
| first A WIRE marker | 1183 | 1184 |
| first B WIRE marker | 2691 | 2693 |
| terminal count | 14 | 14 |
| WIRE count | 14 | 14 |
| active WIRE endpoints | equal | equal |

The regenerated candidate has direct grid contacts, left-terminal 1800
orientation, right-terminal 0 orientation, zero-length donor-native WIRE
records, and final-address-rebased terminal/component link suffixes.

## Loader gate

Candidate:
`experiments/dil16_dual_jk_ff_terminal_v2_temp_2026_07_13/07_reference_width_repair/S02_4027_1X_REFERENCE_WIDTH_DONOR_CONTACT_sa.pdsprj`

It passed:

1. visible delayed cold open with no dialog;
2. close without saving;
3. foregrounded delayed cold reopen with no dialog.

The two visual records are:

- `G09_4027_1X_REFERENCE_WIDTH_BEFORE_CLOSE.png`;
- `G11_4027_1X_REFERENCE_WIDTH_COLD_REOPEN_FOREGROUND_BEFORE_CLOSE.png`.

`G10` is retained but not relied upon because the capture was not
foregrounded. Normal opens were not Ctrl+S-saved.

Focused 4027/frozen-family regression set: 7 passed. Compile check passed.
The whole component-placer test module exceeded its 184-second command
window, and is deliberately not reported as a pass.

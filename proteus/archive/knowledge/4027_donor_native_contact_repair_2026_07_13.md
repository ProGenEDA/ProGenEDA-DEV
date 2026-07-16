# 4027 donor-native contact repair — 2026-07-13

## Scope

This is a `ROOT.DSN`-only repair. The user explicitly directed that this
investigation must not inspect, compare, or mutate `ROOT.CDB`. The locked
placement source remains
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
No donor is copied into generated output at runtime.

## Authoritative donor findings

The accepted primary donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj`.
Its 3,018-byte object stream contains two repeated attachment blocks:

```text
7 $TERBIDIR -> 00 -> physical A packet -> 7 WIRE records
7 $TERBIDIR -> 00 -> physical B packet -> 7 WIRE records -> FF
```

The same 4027 structure was checked in the duplicate primary donors and in
the accepted 2×/mixed 4027 donor corpus under
`proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/4027/` and
`proteus_ic/donors/sequential_ics_batch3/`.

Every active 4027 terminal/WIRE pair has these invariant facts:

- left contacts use `1800`; right contacts use `0`;
- terminal contact and the component pin are the same grid intersection;
- the active WIRE unit has two equal endpoints at that intersection;
- terminal and component suffixes point to the final absolute WIRE address;
- the two physical component records use the donor-proven 28-byte active
  pin-link tail after trimming the locked packet's two zero prefix bytes.

There is no accepted 4027 donor with an extra one-grid outward terminal
contact or a nonzero 254,000-unit WIRE segment. The earlier V6 project is
historical unaccepted diagnostic evidence and is not a source for this route.

## Failure isolation

The locked-mega no-terminal control
`experiments/dil16_dual_jk_ff_terminal_v2_temp_2026_07_13/03_short_wire_retry/S02_4027_1X_SHORT_WIRE_NO_TERMINAL.pdsprj`
cold-opened and cold-reopened normally. The packet/frame is therefore not the
failure.

The nonzero short-WIRE candidate
`03_short_wire_retry/S02_4027_1X_CATALOGUE_TERMINAL_SHORT_WIRE_sa.pdsprj`
matches the donor in terminal record templates, labels, angles, suffix formula,
component-link ordering, WIRE record shape, block order, and stream length.
Its only active-unit geometry change is a 254,000-unit nonzero segment from
the terminal contact to the current pin. Proteus reports `Bad object record -
circuit data lost` on cold reopen and, after dismiss/save, retains only the
first terminal/A prefix while discarding WIRE records and B.

The already-generated direct-contact candidate
`02_subckt_frame_retry/S02_4027_1X_CATALOGUE_TERMINAL_SUBCKT_FRAME_sa.pdsprj`
uses the donor-native equal-endpoint WIRE coordinates at the transformed
current pin. A first hidden-window scan did not expose a modal dialog and was
incorrectly recorded as a pass. The user reported the error, and a visible
retest captured before closing at 2026-07-13 17:45 PKT shows the actual
Proteus dialog:

```text
Bad object record - circuit data lost.
```

This candidate is therefore rejected. The screenshot is
`experiments/dil16_dual_jk_ff_terminal_v2_temp_2026_07_13/06_local_proteus_gate/G06_4027_1X_DONOR_CONTACT_VISIBLE_BEFORE_CLOSE.png`.
The local launcher must capture and inspect a visible screenshot before
closing every future Proteus project; title/window scanning alone is not an
acceptance check.

## Current conclusion and next donor audit

The rejected nonzero route and rejected donor-contact route prove that
terminal/WIRE geometry is not the only remaining defect. No profile or shared
placer change is approved from this evidence alone. The next DSN-only audit
must compare the complete donor and locked-mega component frames, including
all packet fields before the active link tail and all outer `ROOT.DSN`
section/frame fields. It must identify every remaining unexplained difference
before another candidate is emitted.

The donor-native contact facts remain the required target once the remaining
frame defect is found:

- `terminal_contact_policy: donor_explicit`;
- zero outward-grid steps;
- donor coordinates without retargeting;
- `allow_zero_length_wire_units: true`.

This target must be implemented only after the full DSN comparison explains
the bad-record boundary. It will leave the shared terminal placer,
locked-mega component placer, beautifier, accepted family paths, and
`ROOT.CDB` untouched. The generated WIRE must remain an active native
attachment unit with matching terminal and component links; it cannot become
a label-only or inactive-terminal fallback.

## Complete-packet length finding

The complete DSN comparison identified the missing frame fact. Component
packet length is reference-dependent:

| Packet | Reference | Clean length | Active length |
| --- | --- | ---: | ---: |
| accepted donor A/B | `U1:A` / `U1:B` | 399 | 398 |
| locked mega A/B | `U13:A` / `U13:B` | 400 | pending repair: 399 |

The accepted donor removes **one** zero byte before its active 28-byte link
array. The old 4027 catalogue declared two bytes based only on the raw
`400 -> 398` difference, accidentally conflating the additional `U13` versus
`U1` reference character with padding. Consequently the rejected generated
packet was forced to 398 bytes, and each active link array was one byte early.
The donor stream has no such forced-size rule: with a one-character-longer
reference, its current packet and WIRE markers must also be one byte later per
subpart.

The evidence-backed repair is therefore a **one-byte**
`subpart_link_prefix_zero_trim_count` for 4027. With direct donor contact,
the first A WIRE marker must be donor offset `1183 + 1`, and the first B WIRE
marker must be donor offset `2691 + 2` because it follows both widened A and
B component records. Final active suffixes must then be rebased from those
new final absolute DSN addresses.

## Required verification after the profile change

1. Complete the donor-vs-locked-mega DSN frame audit and record every
   difference, not only terminal/WIRE coordinates.
2. Focused 4027 static regression: 14 terminals, 14 active WIREs, direct
   grid contact, matched suffixes, donor A/B block order, and one `FF`.
3. Existing accepted-family focused regressions and compile check.
4. Regenerate a fresh 1× project through the locked mega placer and shared
   terminal placer, then run a visible delayed cold-open/cold-reopen gate on
   a disposable copy, capture a screenshot before each close, and inspect it.
5. Leave 9×/15× unpromoted until the regenerated 1× gate and user visual
   acceptance both pass.

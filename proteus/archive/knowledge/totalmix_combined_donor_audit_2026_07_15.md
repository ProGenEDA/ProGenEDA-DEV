# `totalmix.pdsprj` ROOT.DSN donor-vs-generated audit — 2026-07-15

## Scope and authority

This is a **ROOT.DSN-only** audit, as requested. The authoritative combined
terminal example is the user-provided project:

`experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`

It is evidence for stream grammar only. It is not a runtime template and does
not replace the locked component-placer donor:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

The compared candidate is:

`experiments/mixed_all_supported_totalmix_v1_temp_2026_07_15/scratch_1x/ALL_TOTALMIX_49F_1X_TERMINAL_sa.pdsprj`

The complete machine-readable byte audit is retained beside the experiment:

`experiments/mixed_all_supported_totalmix_v1_temp_2026_07_15/complete_donor_vs_generated_byte_audit.json`

No `ROOT.CDB` fact is used by this repair.

## Complete decoded ROOT.DSN inventory

| Measure | Accepted donor | Generated candidate |
| --- | ---: | ---: |
| `ROOT.DSN` bytes | 224,671 | 224,678 |
| Object-stream absolute start | 144,163 | 144,163 |
| Decoded object-stream bytes | 79,096 | 79,103 |
| `COMPONENT ID` records | 74 | 74 |
| Component/package groups | 49 | 49 |
| `$TERBIDIR` records | 318 | 318 |
| `WIRE` records | 318 | 318 |
| Final stream byte | `ff` | `ff` |

All 49 intended families occur exactly once in both streams. There is no
missing family, duplicate terminal, missing WIRE, or different finalizer class
to repair.

The raw equal-offset comparison has 56,918 different bytes in 4,024 runs. That
is expected to be large because this is a freshly placed design: component and
terminal coordinates, references, link suffixes, and all short-WIRE coordinates
are different. It is therefore not valid to patch every unequal byte from the
donor. The grammar comparison below isolates the meaningful differences.

## Confirmed link mechanics that already match

For both projects, all 318 terminals satisfy all of these checks:

1. The terminal suffixes are unique.
2. The 318 terminal suffixes and 318 WIRE suffixes are the same one-to-one
   set.
3. Every WIRE suffix equals
   `(object_stream_absolute_start + wire_marker_offset - 24) & 0xffff`.
4. Every terminal has exactly one matching non-terminal component-link field.
5. Trailer counts match exactly: 192 active `02 00` routes and 126 active
   `03 00` routes.

The relative terminal/component-link/WIRE topology also matches exactly:

| Relative order | Donor | Candidate |
| --- | ---: | ---: |
| terminal → component link → WIRE | 173 | 173 |
| component link → terminal → WIRE | 142 | 142 |
| terminal → WIRE → component link | 3 | 3 |

So the global failure is **not** caused by missing rebasing, an inactive
trailer, a missing short WIRE, or an incorrect final `ff` terminator. Those
mechanics must remain unchanged by the repair.

## Exact stream-order mismatch

The accepted donor has three terminal ordering zones:

1. Terminal indexes `0–39`: native two-pin/source prelude.
2. Indexes `40–69`: the 30 component-tail terminals for `POT-HG`, `OPAMP`,
   `LM317T`, `NMOSFET`, `2N3904`, `2N4401`, `2N7000`, `BS170`, `NPN`, and
   `PNP`.
3. Indexes `70–191`: the 122 terminal-leading records for `74HC76`, `7490`,
   `7447`, `74HC283`, `74HC192`, `74HC174`, `74HC160`, `74HC157`, and
   `74HC85`.
4. Indexes `192–317`: the 126 `03 00` component-tail/subpart records for
   `74HC08`, `74HC32`, `74HC86`, `74HC266`, `74HC02`, `74HC00`, `74HC04`,
   `4511`, `74HC151`, and `4027`.

The candidate preserves the prelude and the final 126-record zone, but moves
the donor's indexes `40–69` after the terminal-leading block:

| Zone | Donor terminal indexes | Candidate terminal indexes |
| --- | ---: | ---: |
| Native prelude | 0–39 | 0–39 |
| Current/control/BJT tail | 40–69 | **162–191** |
| `74HC76` + terminal-leading ICs | 70–191 | **40–161** |
| `03 00` logic/subpart tail | 192–317 | 192–317 |

The labels inside each moved zone are otherwise identical and in the same
order. Thus the emitter has the right terminal records but inserts the first
tail zone at the wrong stream boundary.

The accepted donor does **not** prove one universal final tail zone. The
current shared candidate incorrectly treated all `component_stream_then_attachment_units`
families as one tail before `4027`; that is contrary to the donor.

## Exact packet-tail mismatch

The candidate is one byte longer than the donor for each of these inline
terminal-leading component groups:

| Family | Donor bytes | Candidate bytes | Difference |
| --- | ---: | ---: | ---: |
| `7490` | 2,355 | 2,356 | +1 |
| `7447` | 2,531 | 2,532 | +1 |
| `74HC283` | 2,546 | 2,547 | +1 |
| `74HC192` | 2,554 | 2,555 | +1 |
| `74HC174` | 2,558 | 2,559 | +1 |
| `74HC160` | 2,555 | 2,556 | +1 |
| `74HC157` | 2,554 | 2,555 | +1 |
| `74HC85` | 1,100 | 1,101 | +1 |

Each source packet ends in a bare `00` selector/finalizer byte. The accepted
donor removes that byte before serializing the terminal-leading unit. The
existing standalone terminal route already contains this trim; the new
combined route skipped it and patched/emitted the untrimmed packet. This is
the exact one-byte defect behind the isolated `7490` loader failure.

`74HC76` is not in this table because its donor-proven subpart emission has a
separate grammar and already preserves its own boundary correctly.

## Source-order contract finding

The locked mega's selected packet order begins with `7447`, `7490`, `4511`,
`4027`, then the other ICs; the user donor begins with the native families.
The candidate changed its component stream into the donor's family order to
try to match it. Its own report marks `component_record_order_mutation: true`.

That is not an acceptable repair. The terminal placer must preserve the
beautified component stream and emit attachment zones from component identity
and profile facts. The canonical family sort must be removed rather than
promoted as a dependency on a donor order.

## Evidence-backed repair set

The following three changes were made together in the existing shared placer:

1. For the eight listed inline terminal-leading families, strip the proven
   trailing `00` from the bare component packet **before** patching link
   offsets and emitting terminal/component/WIRE records.
2. Replace the one `before 4027` tail with explicit profile-driven zones:
   the 30 `02 00` current/control/BJT tail units belong before the
   terminal-leading IC zone; the `03 00` logic/subpart tail keeps its separate
   final zone before `4027` when that boundary exists.
3. Remove canonical component-stream sorting. When a placed design has a
   different legitimate order, derive each attachment-zone boundary from the
   groups actually present; never reorder component packets to match this
   donor.

## Grid-validation observation

The accepted donor itself proves that a terminal contact cannot be judged by
the simplistic absolute check `coordinate % 254000 == 0`. Its 318 contacts use
seven observed coordinate-phase classes: 278 are `(0, 0)`, while others include
`(20320, 20320)`, `(0, 106680)`, and several component-local phases. The
generated design has the corresponding placement-dependent phase classes.

This is a **validator-frame issue**, not evidence to move any terminal. Future
grid validation must use the component/sheet grid phase and the terminal
contact edge, not global zero as its sole origin. The emission coordinates were
not changed by this audit repair.

## Repair and local Proteus gate result

Regenerated candidate:

`experiments/mixed_all_supported_totalmix_v1_temp_2026_07_15/dsn_audit_repair_1x/ALL_TOTALMIX_49F_1X_DSN_AUDIT_REPAIR_TERMINAL_sa.pdsprj`

- 49 placed component groups, 318 terminals, and 318 WIREs.
- All rebased terminal/component/WIRE suffix checks pass.
- The output preserves the locked-mega selected component order; it does not
  use the donor's component sequence.
- The eight inline families now remove their donor-proven bare finalizer before
  link patching. The focused regression independently checks the `7490`
  component-to-first-WIRE span is one byte shorter than the bare packet.
- On the locked mega's order, neither donor boundary is topologically available
  without a forward component link, so both zones used the documented fallback:
  `current_control_bjt_tail` after source index 47 and `logic_tail` after
  source index 48. That preserves component order and link direction.
- A delayed normal open and a separate cold reopen both stayed alive for the
  required wait, showed no modal error, and left their disposable-copy hashes
  unchanged. Screenshots are in
  `experiments/mixed_all_supported_totalmix_v1_temp_2026_07_15/dsn_audit_repair_1x/local_proteus_gate/`.

The cold-reopen screenshot visibly shows loaded `7490`/`7447` terminalized
packages without an error dialog. Whole-schematic layout acceptance remains a
user visual check because the automatic view opens at a partial viewport.

Focused regression result: seven mixed/current/totalmix tests pass. The
accepted two-pin/current routes were not changed.

## Explicit non-fixes

- Do not copy the user donor's bytes, coordinates, packet IDs, CDB, or object
  order into runtime output.
- Do not alter already accepted two-pin, current/control, display, or solo
  routes.
- Do not alter the active-link rebasing formula, `02 00`/`03 00` trailer
  allocation, or finalizer solely because the full candidate failed.

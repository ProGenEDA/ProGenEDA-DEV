# 2N3904 terminal-route preflight — 2026-07-18

## Scope

This note audits the existing catalogue-backed 2N3904 route before any
promotion. It does not alter accepted two-pin, NPN, PNP, or NMOSFET behavior.

## Authoritative evidence examined

- `evidence/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`
  - project SHA-256 `377394b46e4f50743486c0e68ec0bf4246202c574eb0cc8957a8ae1f5535c67a`
  - ROOT.DSN object stream starts at absolute byte `144163`, is `21979` bytes,
    and contains Q65 as a 398-byte 2N3904 component packet.
  - Its 2N3904 tail attachment evidence contains `EMITTER`, `COLLECTOR`, and
    `BASE` terminal records plus adjacent donor-shape WIRE units. The terminal
    and component pin links use the final-address rebasing contract.
- Historical opened 1× evidence:
  `experiments/runs/three_pin_bjt_proteus_opened_1x_v41_temp_2026_07_11/01_proteus_opened/T003_2N3904_1x_PROTEUS_OPENED/T003_2N3904_1x_PROTEUS_OPENED_sa.pdsprj`
  - ROOT.DSN object stream is 873 bytes: ordered terminal records
    `COLLECTOR`, `EMITTER`, `BASE`, a zero separator, the Q65 component packet,
    then three WIRE records and one final `FF`.
  - ROOT.CDB is the compact 282-byte Q65 package row.
- Fresh locked-mega control:
  `experiments/runs/2026-07-18_2n3904_terminal_promotion_matrix/D03_beautified_control/D03_2N3904_1X_BARE_BEAUTIFIED.pdsprj`
  - Built through the current component placer with
    `layout.strategy=beautify` and `terminal_grid_alignment=true`.
  - The binary beautifier moved Q65 from `(-2794000, -32110680)` to the normal
    visible frame (packet bounding box `(-6350000,-5186680)` through
    `(-5948680,-4551680)`).
  - It passed two 12-second local Proteus cold opens without a modal error and
    without the gate copy changing.

## Failed diagnostic and finding

The prior direct candidate skipped the binary beautifier, leaving Q65 off the
normal sheet. That is a pipeline invocation failure, not terminal geometry
evidence. The beautified bare control proves the placed packet and full CDB
pair are loader-valid.

On the beautified control, the generic detached `native_pin_contact` stage
emitted terminal records without their WIRE/link attachment units. Proteus
rejected both cold opens with `Device '…' used but not in library`; the bare
control did not. This establishes that 2N3904 terminals are not accepted as
standalone detached objects in this packet grammar.

The historical project and accepted combined donor only prove the complete
unit: active terminal suffix + matching component pin-link + nonzero WIRE,
in terminal-leading order. Therefore the profile must use the shared
`staged_contact_requires_active_attachment_unit` route for native/grid
diagnostic stages, exactly as already used by similarly proven transistor
families. No standalone side-terminal diagnostic is admissible.

## Evidence-backed next test

Set only the 2N3904 profile flag
`staged_contact_requires_active_attachment_unit: true`. Regenerate native
contact, grid contact, and complete stages from the same beautified control.
Each must retain the current frame, contain the complete active unit, and pass
the two-pass local Proteus gate before any executable allow-list or scale/mix
work is considered.

## Mixed-stream boundary audit

The accepted user-resaved mixed donor was then read as a complete ROOT.DSN
stream rather than inferred from catalogue notes:

`experiments/runs/totalmix_gate_manual_terminal_donor_v1_temp_2026_07_15/terminalized49.pdsprj`

- Its 78,126-byte object chunk places Q65 (2N3904) at offset 7,239, followed
  by Q84, Q100, Q114 and ordinary diode/passive packets through Q129 (NPN) at
  offset 17,315.
- The Q65 tail units occur later at offsets 19,583 (`EMITTER`), 19,749
  (`COLLECTOR`), and 19,909 (`BASE`), before the first IC boundary U41 at
  offset 23,718. Thus this authoritative donor proves a deferred BJT tail,
  not an attachment unit inserted directly after Q65.
- The generated asymmetric control P05 had the same valid selected-package
  CDB subset and static link checks, but inserted Q65's tail immediately after
  Q65 at component-stream index 11 while D232 and D233 followed. Proteus
  rejected that stream with a device-library dialog. Smaller controls that
  ended after Q65 opened, which isolates the fault to this tail-to-later-packet
  boundary rather than the 2N3904 pin geometry or the frozen diode route.

The existing shared totalmix serializer already has a catalogue policy for
this exact donor-proven placement: `totalmix_tail_insertion:
after_component_stream`, used by independently researched BJT families. The
minimal additive 2N3904 profile fact is therefore that policy. It moves only
2N3904's own terminal/WIRE tail after the placed component stream; it does not
rewrite any accepted native two-pin packet, terminal geometry, WIRE, or diode
serializer.

The executable is a separate caller of the same shared placer. It must select
`totalmix_combined_v1` from the 2N3904 profile rather than silently use the
conservative mixed serializer, and the profile must require grid-contact
nonzero WIREs when a standalone catalogue caller does not provide an override.
These two flags are catalogue facts for 2N3904 only; no new generator or
terminal workflow is introduced.

The original 2N3904 catalogue cache marked zero-length units as allowed because
older diagnostic output used them. The active shared route now emits a
106,680-unit nonzero vertical segment at each B/C/E contact, so that allowance
is explicitly false and the executable's nonzero-WIRE gate can enforce the
same contract for direct and mixed requests.

## Promotion evidence completed

The shared path generated and passed the two-open, 12-second local Proteus gate
for staged 1x, 9x, and 15x solos, an asymmetric native ratio mix, a
heterogeneous non-IC mix, and a dense 15-per-family mix. The rebuilt portable
`ProgenProteus.exe` then generated a fresh ratio mix containing two `2N3904`,
five `RESISTOR`, three `CAP`, and four `DIODE` instances; it contained 30
active terminals and 30 nonzero terminal-to-pin WIREs and passed normal open
and cold reopen with no dialog. The disposable gate-copy SHA-256 was unchanged
before/after both opens. This proves the executable selects the same shared
catalogue route; visual layout remains subject to user review.

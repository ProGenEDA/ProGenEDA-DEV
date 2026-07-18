# PNP nonzero-grid terminal-route preflight — 2026-07-18

> **GPT-5.6 active Proteus work.** This note records the donor-first PNP
> promotion audit used by the shared terminal placer. It extends the accepted
> route additively; it does not change an already accepted family.

## Scope and frozen routes

- Target: `PNP`, a three-pin non-IC component currently placeable by the
  locked mega-donor component placer.
- Frozen: every accepted two-pin, control, FET, NPN, display, and IC route.
  The proposed change is PNP catalogue metadata plus executable allow-list
  membership only.
- Shared implementation: `src/proteusgen/component_terminal_placer.py`; no
  family-specific terminal script is introduced.
- Backup made before implementation:
  `archive/backups/component_terminal_placer/component_terminal_placer_20260718_142133_before_pnp_nonzero_grid_route.py`.

## Authoritative donor inventory

Authority:
`evidence/donors/terminalized_catalogue_evidence/three_pin_transistor/PNP/PNP_terminalized_primary.pdsprj`.

| Archive member | Bytes | SHA-256 |
| --- | ---: | --- |
| `SCRIPTS/PWRRAILS.DAT` | 17 | `1381cf6c26c8fc808c265e1c3affeedaf4041454d2ed843a9df56f67871776d7` |
| `ROOT.CDB` | 220 | `93982b89704a6db74cabc6ab453c2c69428233160430a99300e2e00ceeb9be0d` |
| `ROOT.DSN` | 68,762 | `6f528b079d890f7ed2db4a0948b31df6e8b889ba377bd531e159ed5d1855e06c` |
| `PROJECT.XML` | 249 | `e4e7f5bff68c8735a24d542d4472eb6cbdd621643ea3a0309cce119500e1c676` |

`ROOT.DSN` contains an 816-byte object chunk beginning `00 10` and ending in
one explicit `FF`. Its order is three terminal records, the PNP component
packet, and three `WIRE` records. The component begins at object offset 321;
the WIRE region begins at 665. The three active component-link fields occur at
the donor-proven `component-end -13/-9/-5` locations and use the original
`0100` trailer. The shared route rebases those links from the final DSN WIRE
addresses with its proven `0200` trailer.

`ROOT.CDB` has exactly one unchanged package row and one unchanged property
row, both for `Q1`; the pin row identifies the PNP primitive with pins
`B/C/E`. No CDB mutation is needed or permitted for this terminal-only route.

## Pin and record facts

The PNP component marker anchor is `(-7,620,000, 5,080,000)`. All three pins
already lie on the 254,000-unit Proteus terminal grid:

| Pin | Label | Side / angle | Pin relative to anchor | Donor terminal contact | Donor WIRE |
| --- | --- | --- | --- | --- | --- |
| B | `BASE` | left / 1800 | `(-1,016,000, 762,000)` | `(-8,636,000, 5,842,000)` | zero-length |
| C | `COLLECTOR` | right / 0 | `(0, 1,524,000)` | `(-7,620,000, 6,604,000)` | zero-length |
| E | `EMITTER` | right / 0 | `(0, 0)` | `(-7,620,000, 5,080,000)` | zero-length |

The donor labels/order are `BASE`, `COLLECTOR`, `EMITTER`; WIRE marker order
matches B, C, E. Terminal suffixes are 2178, 2228, and 2278; WIRE markers are
at object offsets 689, 739, and 789. The donor terminals are correctly
oriented but directly contact their pins, so every donor WIRE has identical
start and end coordinates.

## Evidence-backed promotion plan

The authoritative NPN donor has the same three-pin packet grammar, the same
pin offsets, the same link locations, the same zero-length historical WIREs,
the same `00 10` prefix, and one-final-`FF` terminator. NPN was newly accepted
on 2026-07-18 after its terminal contact was shifted one grid step outward,
producing nonzero grid-attached direct WIREs while preserving its packet,
link-address rebasing, CDB, and finalizer grammar.

PNP therefore uses that already loader-gated shared policy, without modifying
NPN or any other family:

- B contact: one grid step left of B; C/E contacts: one grid step right.
- Contacts remain on grid intersections and terminal angles remain 1800/0/0.
- Each generated WIRE is a nonzero straight segment from that contact to the
  original exact PNP pin.
- The existing terminal-leading PNP packet order and one-`FF` finalizer stay
  intact for solo projects.
- The mixed route uses PNP's own end-of-component-stream tail insertion, so
  it cannot repeat the former NPN-tail-before-diode boundary error.

This is the only planned change set. The next gate is a new 1x PNP project,
followed by 9x/15x and different-ratio mixed projects only if 1x passes the
two 12-second cold-open checks.

## Stage-1 correction

The first generated `native_pin_contact` diagnostic deliberately emitted
unlinked PNP terminal records. Both 12-second cold opens stopped at Proteus's
device-library dialog, confirming that an unattached PNP terminal record is
not a valid loader stage. The DSN comparison explains the failure completely:
the donor has no detached terminal state; each terminal is inseparable from
its active suffix, matching PNP pin link, and immediate WIRE record.

The PNP profile therefore declares
`staged_contact_requires_active_attachment_unit: true`. This does not invent a
new workflow: it makes the shared staged gate retain the donor-proven complete
attachment unit and vary only the contact coordinate between native and grid
stages. The rejected detached diagnostic remains preserved in the experiment
folder as failure evidence.

## Completion record

The PNP profile is now locked for the current executable non-IC route. Its
shared-place/routing facts were emitted through the existing unified terminal
placer; no donor project, component slot, or terminal packet was transplanted
at runtime.

| Evidence | Result |
| --- | --- |
| `D01_native_pin_contact_active_unit_v2` | Passed two 12-second cold opens; this is a diagnostic attachment-unit proof, not the final contact geometry. |
| `D02_grid_contact_active_unit_v2` | Passed twice with grid contacts and nonzero WIREs. |
| `S01_complete_nonzero_grid_v3`, `S02_PNP_9X`, `S03_PNP_15X` | Passed twice each. |
| `M01`/`M02`/`M03`/`M04` non-IC combinations | Passed twice each, including asymmetric and 60-component `15x` stress coverage. |
| `EXE_M10_PNP_DIODE15X_RELEASE` | Final rebuilt executable: 60 terminalized components, 135 terminals/WIREs, all grid-aligned/nonzero; two cold opens passed. |
| `EXE_M09_PNP_HET1X` | Latest executable: nine-family heterogeneous non-IC mix, 24 terminals/WIREs; two cold opens passed. |

The mixed BJT regression initially exposed an old conservative-writer mismatch:
when a requested catalogue profile already requires donor-proven nonzero grid
contacts, legacy R/C overlay contacts in the same stream remained non-grid. The
shared placer now elevates `force_grid_contact_short_wires` only for a mixed
stream that contains an explicit profile flag (`NPN` or `PNP`); an R/C-only
route is unchanged. The complete 23-test BJT/grid-sensitive regression set and
the 17-test application suite passed after this correction.

The executable path-length failure seen in the long-named `EXE_M07` probe was
also isolated: the transient manifest path was exactly 260 characters because
the temporary work directory repeated the descriptive output stem. The active
application now uses the bounded `.progen_` work prefix. The short-named
regeneration and current executable gates above prove normal generation; the
failed long-name folder is retained as diagnostic evidence.

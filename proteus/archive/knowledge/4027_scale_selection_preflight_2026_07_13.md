# 4027 scale-selection preflight — 2026-07-13

## Scope

This is a `ROOT.DSN`-only investigation, as directed by the user.  It does
not inspect, compare, normalize, or mutate `ROOT.CDB`.  The authoritative
placement source is the locked mega donor:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

## Complete DSN package audit

The donor has 25 parsed `4027` DSN groups.  Fifteen are valid two-subpart
packages; ten are deliberately split controls.  Their source order is:

| Kind | Package keys |
| --- | --- |
| Complete `A+B` packages | `U13`, `U14`, `U15`, `U154`, `U155`, `U156`, `U295`, `U296`, `U297`, `U436`, `U437`, `U438`, `U577`, `U578`, `U579` |
| Split controls (`B` then non-final `A`) | `U16`, `U157`, `U298`, `U439`, `U580` |

Each complete package has two parsed `4027` marker anchors and a
finalizable packet tail.  Each split control half has one marker anchor.
The catalogue correctly requires anchor index 0 for the A pins and index 1
for the B pins; therefore attaching a full 14-pin terminal plan to a split
control must fail rather than guess an absent B anchor.

## Reproduced failure and complete cause

The first 9× static generation selected generic DSN group positions.  After
`U13`, `U14`, and `U15`, that sequence reached `U16:B`; the planner then
rejected pins 9–15 with `component_anchor_index_out_of_range`.  This is a
component-placer package-selection bug, not a terminal-coordinate, WIRE,
suffix, or CDB issue.

## Evidence-backed repair

Declare `4027: 2` in the existing complete-package selection registry.  The
locked component placer then selects only full A/B packets through the same
removal-only path, provides all fifteen real donor packages for 15×, and
leaves the shared terminal placer, accepted two-pin families, and HC76 route
unchanged.  No records are cloned and no donor is replaced.

## Required verification

1. A focused 15× placement regression must assert all fifteen exact package
   keys and both subpart references.
2. Regenerate 9× and 15× through the locked component placer plus the shared
   catalogue terminal placer; require 14 terminals and 14 nonzero short WIREs
   per package with grid-aligned terminal contacts.
3. Run the delayed Proteus loader gate after the active user PDS session is
   closed.  Normal opens remain unsaved; a dismissed Bad Object Record is
   saved only as a disposable DSN comparison.

## Static regeneration result

After the complete-package selector was enabled, the locked component placer
and shared terminal placer regenerated both requested scales successfully:

| Scale | Packages | Terminals | Parsed nonzero WIREs | Grid/contact checks |
| --- | ---: | ---: | ---: | --- |
| 9× | 9 | 126 | 126 | pass |
| 15× | 15 | 210 | 210 | pass |

The nonzero count is read directly from the emitted `ROOT.DSN` WIRE records,
not inferred from a report field.  Loader/open acceptance remains pending the
user's active Proteus session closing.

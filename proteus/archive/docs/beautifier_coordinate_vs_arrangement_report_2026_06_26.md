# Beautifier Coordinate vs Arrangement Report - 2026-06-26

## Scope

This note classifies the latest IC-heavy screenshots only. It does not propose
or implement arrangement fixes, because the current beautifier milestone is
strictly to prove safe coordinate mutation of complete donor packets.

## Classification

The observed issues are placement-logic / arrangement-policy issues, not proven
coordinate-changing corruption.

Evidence:

- IC packets move as intact Proteus objects; the visible gate symbols, reference
  labels, pin numbers, family labels, and package suffixes remain attached.
- The symptoms are dense rows, chained gate symbols, and awkward grouping. These
  are layout policy failures: the current shelf placer does not yet understand
  that one logical IC request such as `74HC00` expands into several gate
  subparts with a wider visual footprint.
- The screenshots do not show the classic coordinate-mutation failure modes we
  already recorded earlier: stranded value text, detached component IDs,
  random off-sheet labels, bad object record, LXLCORE/VGDVC errors caused by
  edited non-coordinate bytes, or changed marker/ref counts.

## Current Rule

Do not fix these IC arrangement issues during the coordinate-mutation phase.
The beautifier may continue to translate complete packets and report bounding
boxes, but semantic arrangement rules for IC subparts, gate rows, pin lanes,
and final readability are deferred to the later arrangement-planning phase.

## Next Work

- Build value changing as a deterministic post-placement stage.
- Build bidirectional terminal placement as a deterministic post-placement
  stage.
- Keep both stages documented and validated independently before combining them
  with later arrangement and wiring logic.


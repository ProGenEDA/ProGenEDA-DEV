# Dense all-family `totalmix` grid-contact preflight — 2026-07-15

## Scope and authority

This preflight extends the previously loader-gated 49-family 1x combined
route to the all-IC + non-IC 9x stress mix. The authoritative stream grammar
remains the user's `experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/totalmix.pdsprj`.
The earlier DSN-only audit in
`knowledge/totalmix_combined_donor_audit_2026_07_15.md` remains the source for
component order, link trailers, inline finalizer handling, attachment zones,
and final-address suffix rebasing. No new ROOT.CDB audit was performed.

Before the shared-placer change, the current file was preserved as
`backups/component_terminal_placer/component_terminal_placer_20260715_114000_before_dense_totalmix_grid_contact.py`.

## Complete failure inventory

The original compact 9x all-family placement used the existing optional
`terminal_grid_alignment` packet translation. The component placer selected
all 440 requested packets (49 families, with HC00 at its independently
loader-proven eight-package selection) and placed them below the terminal-safe
coordinate boundary, but the terminal report found these complete classes of
failure:

1. Many native two-pin/source pin contacts landed exactly on the terminal grid,
   causing a zero-length WIRE when a grid contact used the same coordinates.
2. Catalogue pins with donor-explicit contact/WIRE evidence could preserve an
   old donor endpoint instead of the newly selected grid contact. This affected
   IC/control examples such as 4511 and OPAMP.
3. BJT/FET mixed-tail evidence is anchor-relative. Translating its raw terminal
   offsets into a new grid-snapped component frame can put the terminal contact
   between grid intersections.
4. SWITCH's accepted mixed evidence corrects its generic right-pin endpoint.
   Choosing the terminal contact before applying that correction can move the
   outward contact directly onto the real pin.

The report listed every failure before a change. No accepted default family
route was modified to solve it.

## Additive shared-planner repair

`attach_mixed_component_and_catalogue_bidir_terminals_to_project()` now accepts
the opt-in `force_grid_contact_short_wires=True` mode. It is used only by the
dense all-family stress route; its default is false.

- A terminal already coincident with its grid-aligned pin moves one outward
  grid step, retaining left `1800` / right `0` orientation and producing a
  nonzero WIRE.
- Native mixed donor evidence still supplies the exact pin endpoint. In the
  opt-in mode the terminal contact is recomputed *after* that endpoint is
  known, then the active WIRE runs from the grid contact to the donor-derived
  pin. This is required for SWITCH.
- Catalogue donor polylines keep their evidence-derived topology, labels,
  attachment order, and link fields, but their terminal and pin endpoints are
  retargeted to the current grid contact and exact current pin.
- Mixed BJT/FET tail evidence likewise retains the donor topology/order while
  retargeting both endpoints. It never copies an absolute donor packet.
- The opt-in report validates native as well as catalogue contact alignment,
  terminal-to-WIRE continuity, WIRE-to-pin continuity, and nonzero WIREs.

The existing default callers retain their prior geometry and all focused
accepted-route regressions remain green.

## 9x all-family result

Artifact:
`experiments/mixed_all_supported_totalmix_v1_temp_2026_07_15/dsn_audit_repair_scales/03_all_49_mixed_9x_hc00_8x/ALL_TOTALMIX_49F_9X_HC00_8X_TERMINAL_sa.pdsprj`.

- Placement: 440 components, 49 families, compact all-family flow, no overlap,
  maximum Y `329,204,320` (below the established terminal-safe coordinate
  boundary).
- Terminals/WIREs: 2,850 each; every contact is grid aligned, every WIRE is
  nonzero, every WIRE touches its terminal and exact component pin, and all
  suffix links were rebased from final ROOT.DSN WIRE addresses.
- HC00: eight packages are included. A fresh nine-package locked-mega probe
  reached an actual Proteus `Fatal Error [00000000]`; this is recorded as a
  donor-packet safety constraint rather than a placement-row limit.
- Loader gate: a disposable copy normal-opened and cold-reopened after the
  required delayed check, showed a schematic window without Bad Object Record,
  LXLCORE, fatal, or library dialog, and retained an identical SHA-256 hash.
  No Ctrl+S was used because no warning appeared. Screenshots are retained in
  the artifact's `local_proteus_gate/` folder; user visual layout review remains
  separate from loader acceptance.

## Regression evidence

Focused regression and compile validation:

```text
6 passed, 196 deselected
python -m compileall -q src tests tools/proteus_generation
```

The focused set includes the frozen default mixed route, donor-proven BJT tail
route, 1x `totalmix` order/finalizer route, and a new dense-grid regression
covering native two-pin, SWITCH endpoint correction, BJT/FET tail topology,
OPAMP/LM317T, 4511, and DIL14 logic in one shared emitter call.

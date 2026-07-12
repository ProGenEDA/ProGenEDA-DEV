# Current-group mixed terminal pack

This pack exercises the complete currently accepted mixed group through the
locked `new_components_5x_mega` component placer and the one shared terminal
placer, `src/proteusgen/component_terminal_placer.py`. It does not transplant
the user donor as an output. The donor is used only as authoritative evidence
for the mixed attachment order, pin-relative terminal geometry, WIRE shapes,
and stream boundaries.

## Generated terminalized projects

| Requested scale | Effective scale | Terminal/WIRE units | Terminalized project |
| ---: | ---: | ---: | --- |
| 1x | 1x | 70 | `01_1x_user_donor_oracle/ALL_ACCEPTED_CURRENT_GROUP_1X_TAIL_ORACLE_sa.pdsprj` |
| 9x | 9x | 630 | `02_9x_full_current_group/ALL_ACCEPTED_CURRENT_GROUP_9X_TAIL_ORACLE_sa.pdsprj` |
| 15x | 15x | 1,050 | `03_15x_full_current_group/ALL_ACCEPTED_CURRENT_GROUP_15X_TAIL_ORACLE_sa.pdsprj` |
| 23x | 21x | 1,470 | `04_up_to_23x_full_current_group/ALL_ACCEPTED_CURRENT_GROUP_21X_CAPPED_FROM_23X_REQUEST_TAIL_ORACLE_sa.pdsprj` |

Every folder also contains the corresponding `_NO_TERMINAL.pdsprj` control,
the input JSON, capacity metadata, and the shared-placer report. The requested
23x case is capped at 21x because the locked mega donor has only 21 clean
`CAP-ELEC` groups; this is recorded in the component catalogue and
`capacity.json`.

## Evidence and validation

- Authoritative mixed donor:
  `proteus_ic/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`
- Complete donor analysis:
  `knowledge/current_group_mixed_tail_donor_analysis_2026_07_12.md`
- Static regeneration checks: each output has the expected number of active
  bidirectional terminals and WIREs, grid-valid terminal contacts, and valid
  shared-placer reports.
- Focused regression: 4 passed (`full current-group donor oracle`, mixed
  controls at 1x/9x, and BJT tail/CAP-ELEC coverage).
- `compileall` passed for `src/proteusgen`, `tests`, and this experiment
  runner.

The user directed that Ctrl+S byte canonicalization is not an acceptance target.
Proteus visual inspection remains the acceptance test for terminal placement.
A local cold-open diagnostic reached the normal schematic window for the 1x
and 9x candidates. A later 21x cold-open attempt displayed a `VGDVC.DLL`
access-violation dialog; no speculative cap, geometry change, or save-mimic
repair was made after the user instructed the work to stop at the requested
generated pack. Treat the 21x file as a generated static candidate pending user
inspection/direction, not as locally accepted.

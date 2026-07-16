# D20 / ordinary-diode 15x regression audit

## Report

The user reported that a 15x diode project appeared to show only two ordinary
diodes and asked whether the display-bridge exclusion was incorrectly
discarding every diode after `D20`.

## Donor and selector evidence

The locked component placer remains bound to
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
Its `DIODE` selector filters only `group.key != "D20"`. It does not use a
numeric reference cut-off.

The existing 15x control manifest and a fresh current-code generation both
selected these exact ordinary diode packets:

`D18, D19, D232, D233, D234, D235, D236, D237, D238, D239, D240, D241, D242,
D243, D244`.

That is fifteen selected components, thirteen of which have a numeric reference
greater than 20. `D20` alone is absent.

## Local Proteus render check

The existing locked-mega 15x no-terminal project
`experiments/locked_mega_no_terminal_matrix_temp_2026_07_08/01_solo_scaling/C0194_DIODE_15x.pdsprj`
was cold-opened in the installed Proteus after a 12-second settled window. It
opened normally. The visible viewport showed `D18`, `D19`, `D232`, `D233`,
`D242`, `D243`, and `D244`; the Proteus sheet minimap showed the complete
fifteen-item shelf. This disproves the proposed "everything after D20 is
ignored" failure for the current locked-mega route.

The temporary screenshot/copy used for this diagnosis is intentionally not
committed. It contains desktop/window state rather than durable component
evidence.

## Regression

`tests/test_component_placer.py::test_component_placement_diode_scale_excludes_only_display_bridge`
locks the exact selection. No accepted terminal route, component packet, or
beautifier behavior was changed for this audit.

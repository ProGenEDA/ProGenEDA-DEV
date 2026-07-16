# ProgenProteus executable preflight — 2026-07-16

## Scope

The executable is a public Proteus-only application wrapper. It composes the
existing shared stages and does not add an alternate terminal workflow:

1. `generate_component_placement_project`
2. `attach_component_bidir_terminals_to_project`
3. `edit_project_values_and_properties` when `post_terminal_edits` is present

The wrapper rejects `connections`, `wires`, `nets`, and `netlist` input until
the shared physical Wire Maker exists. It also rejects a terminal report that
contains a zero-length terminal-to-pin WIRE.

## Bundle audit

The PyInstaller one-file build includes only the runtime data required by the
locked shared Proteus route:

- `fixtures/`
- `knowledge/component_catalog_v0.json`
- `knowledge/validator_history_rules.json`
- `proteus_ic/registry/trusted_donor_manifest.json`
- `proteus_ic/registry/native_components.json` (normalization/marker metadata)
- `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

It does not package KiCad code or data. `templates.repository_root()` resolves
the PyInstaller `_MEIPASS` extraction root before normal source-checkout
discovery, so the bundled fixtures and locked donor are used at runtime.

## Verification

- `python -m pytest tests/test_proteus_app.py tests/test_component_value_changer.py -q`: **12 passed**
- `python -m compileall -q src tests tools`: **passed**
- Built `release/ProgenProteus.exe` with PyInstaller 6.21.0: **passed**
- Actual executable `generate` invocation using
  `examples/progen_proteus_r_c_value_edit.json`: **passed**
  - produced one R/C design through placement, beautification, shared terminal
    placement, and post-terminal edits;
  - emitted four terminal records and four nonzero WIRE records.
- Local Proteus 8 disposable-copy gate: **passed**
  - cold open after 12 seconds: no Bad Object Record, Fatal Error, LXLCORE, or
    device-library dialog;
  - cold reopen after 12 seconds: same result.

The build is a console executable by design so it can be called from the
future prompt/JSON pipeline and automated tests. A GUI launcher is a separate
product layer, not a replacement for this stable pipeline entry point.

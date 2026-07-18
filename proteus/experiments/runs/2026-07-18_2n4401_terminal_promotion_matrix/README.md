# 2N4401 terminal-promotion matrix — 2026-07-18

This is additive evidence for the shared Proteus terminal placer. It does not
change any accepted two-pin, diode, NPN, PNP, NMOSFET, or 2N3904 serializer.

## Authoritative evidence

- Primary accepted donor:
  `proteus/active/evidence/donors/ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj`
  (`377394b46e4f50743486c0e68ec0bf4246202c574eb0cc8957a8ae1f5535c67a`).
- User-resaved mixed control:
  `proteus/experiments/runs/totalmix_gate_manual_terminal_donor_v1_temp_2026_07_15/terminalized49.pdsprj`
  (`b1a9be6a58a8fe8c15b23fc8112d7ee2b0b2b846ad66b700996154cf490860b9`).
- Native bodies are freshly placed from the locked mega donor, not copied from
  either terminalized donor.

The donor proves the `2N4401` Q84 tail order `COLLECTOR`, `EMITTER`, `BASE`
after the full component stream, with 106,680-unit direct WIREs. The shared
catalogue profile uses grid contacts and nonzero WIREs for all promoted output.

## Generated matrix

- `D01_active_unit_stages`: native-contact loader probe, grid-contact proof,
  and complete 1x proof.
- `S02_9x` and `S03_15x`: homogenous scale proofs.
- `M00_additive_boundary`: five incremental native-plus-2N4401 combinations.
- `M01_ratio_mix`: two-BJT asymmetric ratio.
- `M02_heterogeneous_mix`: 24 components across 11 supported non-IC families.
- `M03_dense_15x_mix`: 105 components and 270 terminal/WIRE units.
- `M04_executable_source`: fresh public Python application output.
- `M05_portable_executable`: fresh `ProgenProteus.exe` output.

Each directory preserves its input, bare project, terminalized project,
placement/terminal reports, copied gate project, and screenshots. The complete
two-open loader record and unchanged SHA-256 values are in
[`loader_gate_summary.json`](loader_gate_summary.json). Every stated candidate
passed the local Proteus gate with a 12-second wait and no Bad Object Record,
Fatal Error, LXLCORE, or library dialog. Normally opening projects were not
saved through Proteus.

## Validation

- `tests/test_component_placer.py -k test_three_pin_transistor_catalogue_terminal_attachment`: 7 passed.
- `tests/test_proteus_app.py`: 19 passed.
- `python -m compileall -q src tests tools`: passed.
- The rebuilt portable executable SHA-256 is
  `D32D06E4935EAAC1E8439807472871E1A706F299AE4A1DF7839CBC4E8534FEAD`.

The local loader gate establishes file acceptance. User visual review remains
the authority for final layout acceptance.

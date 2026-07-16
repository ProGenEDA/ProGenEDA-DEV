# litpaper Cleanup / Migration Record for Proteus-Generator Files

## Reason

Proteus native-project-generator / reverse-engineering notes were accidentally committed to `MuhammadTahaBinZaeem/litpaper`. They belong in `MuhammadTahaBinZaeem/memory`.

The correct active repo for this work is:

```text
MuhammadTahaBinZaeem/memory
```

## Migration safety

A migration script exists at:

```text
tools/migrate_proteus_from_litpaper.sh
```

It is pinned to the old `litpaper` commit that still contained the accidental Proteus files:

```text
25c86b0a0d0574f63728a13cf3f30fe2f4f7147f
```

So even after cleaning `litpaper/main`, the files can still be recovered from Git history if needed.

## Cleanup completed on litpaper/main

The following misplaced Proteus files were removed from `MuhammadTahaBinZaeem/litpaper` on `main`:

```text
docs/generator_method/r21_resistor_terminal_generator_v9_canonical_method.md
docs/public_black_box_methodology/README.md
docs/public_black_box_methodology/01_problem_statement.md
docs/public_black_box_methodology/02_black_box_experiment_protocol.md
docs/public_black_box_methodology/03_resistor_synthesis_milestone.md
experiments/b02_order_fixed_r21_generation_note.md
experiments/b02_order_terminator_fix_note.md
experiments/e001_cdb_written_r7_r12_generation_shot.md
experiments/e001_cdb_written_r7_r12_test_results_success.md
experiments/final_r21_e001_terminal_network_generation.md
experiments/r5_generation_shot_cdb_dsn_binding_attempt.md
experiments/r7_r12_t04_method_generation_shot.md
experiments/r21_terminal_network_generation_shot.md
experiments/r21_terminal_network_v1_failure_and_v2_fix.md
experiments/r21_terminal_network_v2_results_and_v3_terminal_field_fix.md
experiments/r21_terminal_network_v3_results_and_v4_order_suffix_diagnostics.md
experiments/r21_terminal_network_v4_results_and_v5_boundary_fix.md
experiments/r21_terminal_network_v5_results_and_v6_label_patch_fix.md
experiments/r21_terminal_network_v6_results_and_locked_terminal_method.md
experiments/r21_terminal_resistor_final_checks_v7_e001.md
experiments/reference_strategy_component_vs_combination.md
experiments/v9_no_premature_terminators_note.md
experiments/generation_code/r21_terminal_network_v3_terminal_field_fix.py
experiments/generation_code/r21_terminal_network_v4_order_suffix_diagnostics.py
experiments/generation_code/r21_terminal_network_v5_correct_object_boundaries.py
experiments/generation_code/r21_terminal_network_v6_fixed_terminal_label_patch.py
```

The current-session bad base64 artifact chunk was also removed from `litpaper`:

```text
artifacts/proteus_v9_recovery/R21_E001_B02_V9_NO_PREMATURE_TERMINATORS.zip.b64.part01.txt
```

## Direct verification completed

After deletion, representative direct `main` checks returned `404 Not Found` for:

```text
docs/generator_method/r21_resistor_terminal_generator_v9_canonical_method.md
experiments/v9_no_premature_terminators_note.md
experiments/r21_terminal_network_v4_results_and_v5_boundary_fix.md
experiments/reference_strategy_component_vs_combination.md
docs/public_black_box_methodology/README.md
docs/public_black_box_methodology/02_black_box_experiment_protocol.md
docs/public_black_box_methodology/01_problem_statement.md
experiments/generation_code/r21_terminal_network_v3_terminal_field_fix.py
experiments/generation_code/r21_terminal_network_v4_order_suffix_diagnostics.py
experiments/generation_code/r21_terminal_network_v5_correct_object_boundaries.py
experiments/generation_code/r21_terminal_network_v6_fixed_terminal_label_patch.py
experiments/r21_terminal_network_v1_failure_and_v2_fix.md
experiments/final_r21_e001_terminal_network_generation.md
```

Note: GitHub code search may temporarily show stale results from older commits even after `main` no longer contains the files. Direct `fetch_file` checks against `ref=main` were used for verification.

## Current memory-side records

The following records now exist in `memory`:

```text
artifacts/proteus_v9_recovery/README.md
experiments/v9_no_premature_terminators_note.md
tools/migrate_proteus_from_litpaper.sh
docs/reports/litpaper_cleanup_needed.md
```

## Correct continuation point

The active Proteus-generator work should continue in `memory`, not `litpaper`.

Next target:

```text
generalize the V9 linked terminal/resistor/wire object group emitter into a graph-based two-pin component generator
```

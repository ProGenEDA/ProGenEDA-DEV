#!/usr/bin/env bash
set -euo pipefail

# This script migrates Proteus-generator files that were accidentally committed to
# MuhammadTahaBinZaeem/litpaper into this repository.
# Run from the root of MuhammadTahaBinZaeem/memory.
#
# Important: SOURCE_REF is pinned to the litpaper commit that still contained the
# accidental Proteus files after the bad current-session base64 chunk had been
# removed. Do not use main, because main is being cleaned.

SOURCE_REPO="MuhammadTahaBinZaeem/litpaper"
SOURCE_REF="25c86b0a0d0574f63728a13cf3f30fe2f4f7147f"
RAW_BASE="https://raw.githubusercontent.com/${SOURCE_REPO}/${SOURCE_REF}"

FILES=(
  "docs/generator_method/r21_resistor_terminal_generator_v9_canonical_method.md"
  "docs/public_black_box_methodology/README.md"
  "docs/public_black_box_methodology/01_problem_statement.md"
  "docs/public_black_box_methodology/02_black_box_experiment_protocol.md"
  "docs/public_black_box_methodology/03_resistor_synthesis_milestone.md"
  "experiments/b02_order_fixed_r21_generation_note.md"
  "experiments/b02_order_terminator_fix_note.md"
  "experiments/e001_cdb_written_r7_r12_generation_shot.md"
  "experiments/e001_cdb_written_r7_r12_test_results_success.md"
  "experiments/final_r21_e001_terminal_network_generation.md"
  "experiments/r5_generation_shot_cdb_dsn_binding_attempt.md"
  "experiments/r7_r12_t04_method_generation_shot.md"
  "experiments/r21_terminal_network_generation_shot.md"
  "experiments/r21_terminal_network_v1_failure_and_v2_fix.md"
  "experiments/r21_terminal_network_v2_results_and_v3_terminal_field_fix.md"
  "experiments/r21_terminal_network_v3_results_and_v4_order_suffix_diagnostics.md"
  "experiments/r21_terminal_network_v4_results_and_v5_boundary_fix.md"
  "experiments/r21_terminal_network_v5_results_and_v6_label_patch_fix.md"
  "experiments/r21_terminal_network_v6_results_and_locked_terminal_method.md"
  "experiments/r21_terminal_resistor_final_checks_v7_e001.md"
  "experiments/reference_strategy_component_vs_combination.md"
  "experiments/v9_no_premature_terminators_note.md"
  "experiments/generation_code/r21_terminal_network_v3_terminal_field_fix.py"
  "experiments/generation_code/r21_terminal_network_v4_order_suffix_diagnostics.py"
  "experiments/generation_code/r21_terminal_network_v5_correct_object_boundaries.py"
  "experiments/generation_code/r21_terminal_network_v6_fixed_terminal_label_patch.py"
)

for path in "${FILES[@]}"; do
  mkdir -p "$(dirname "$path")"
  echo "Fetching $path"
  curl -fsSL "${RAW_BASE}/${path}" -o "$path"
done

mkdir -p docs/reports
cat > docs/reports/proteus_litpaper_migration_record.md <<'MARKDOWN'
# Proteus Files Migrated from litpaper

These files belonged to the Proteus native project generator / reverse-engineering work and were accidentally committed to `MuhammadTahaBinZaeem/litpaper` during the old chat.

They have been copied into `MuhammadTahaBinZaeem/memory`, which is the correct repository for this work.

After verifying this copy, the corresponding Proteus files can be removed from `litpaper` so `litpaper` remains only for the literary/stylometry paper.
MARKDOWN

git status --short

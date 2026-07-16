#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ANALYZER="progeneda_autonomous_camber_analyzer.py"
INPUT_A="experiments/CAMBER_COMPONENT_PLACER_ANALYSIS_2026_06_15.zip"
INPUT_B="experiments/COMPLETE_RESULTS.zip"
OUT_DIR="experiments/camber_cli_analysis_outputs"
OUT_ZIP="experiments/camber_cli_analysis_outputs.zip"

if [[ ! -f "$ANALYZER" ]]; then
  echo "ERROR: missing analyzer script: $ANALYZER" >&2
  exit 1
fi

if [[ ! -f "$INPUT_A" ]]; then
  echo "ERROR: missing input: $INPUT_A" >&2
  exit 1
fi

if [[ -f "$INPUT_B" ]]; then
  python3 "$ANALYZER" \
    --input "$INPUT_A" \
    --input "$INPUT_B" \
    --out "$OUT_DIR" \
    --max-pair-comparisons 500
else
  echo "WARNING: optional input missing: $INPUT_B" >&2
  python3 "$ANALYZER" \
    --input "$INPUT_A" \
    --out "$OUT_DIR" \
    --max-pair-comparisons 500
fi

rm -f "$OUT_ZIP"
(
  cd experiments
  zip -r "$(basename "$OUT_ZIP")" "$(basename "$OUT_DIR")"
)

echo "Analysis folder: $OUT_DIR"
echo "Analysis zip:    $OUT_ZIP"

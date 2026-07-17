# Proteus 200-circuit complete pin-wiring corpus

This corpus is generated from the pinned fixture
[`../../fixtures/circuit_specs/Proteus_200_Circuits_Complete_Pin_Wiring.pdf`](../../fixtures/circuit_specs/Proteus_200_Circuits_Complete_Pin_Wiring.pdf).
It contains 200 canonical source specifications with every component pin mapped
to exactly one named net.

## Files

- `specifications/`: the complete authoritative logical circuit JSONs. Each
  file preserves PDF references, source part labels, requested values, every
  pin-to-net mapping, and the net connection table.
- `placement_controls/`: clean, derived inputs for the current portable
  executable. They contain only supported placement-family counts and a
  beautification request.
- `corpus_manifest.json`: source-PDF hash, circuit metadata, complexity score,
  and the paired JSON filenames.

## Important execution boundary

The source JSONs are complete wiring specifications. The current executable
does not synthesize arbitrary physical Proteus nets, so it must not be given
their `nets` table yet. Run the paired placement controls with
`--no-terminals` to prove the donor-backed component placement stage while the
complete netlist remains preserved for the future shared Wire Maker.

```powershell
$env:PYTHONPATH = "proteus/active/src"
python proteus/active/tools/build_pdf_200_circuit_corpus.py --check
python proteus/active/tools/run_pdf_200_circuit_corpus.py --jobs 3
python proteus/active/tools/run_pdf_200_circuit_corpus.py --check --require-cold-open
```

The second command writes generated projects, a per-circuit executable report,
and the ten highest-complexity successful candidates under
`proteus/experiments/runs/2026-07-17_pdf_200_circuit_placement_controls/`.

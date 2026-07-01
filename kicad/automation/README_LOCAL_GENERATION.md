# Local KiCad Experiment Generation

Preferred V1 path:

```text
python kicad/automation/local_generate_experiments_with_groq.py --offline-json path/to/json_folder
python kicad/automation/generate_target_pack.py --outdir kicad/experiment_records/runs/local_target_pack
```

The script reads every `.json` file in the folder, validates/generates the KiCad project, and writes:

```text
kicad/experiment_records/runs/<run_id>/
  json/
  projects/
  run_manifest.json
```

Optional Groq mode remains available, but it is not required for generator validation and must not be used to store API keys.

## C01-C55 Pack

`generate_target_pack.py` is the deterministic no-API regression generator for
the OCR target list in `kicad/targets/proteus_generator_circuit_test_set_ocr.md`.
It writes 55 CircuitIR JSON inputs, 55 KiCad projects, and a top-level
`run_manifest.json`.

The same path is exposed through the main executable entry point:

```text
python -m proteusgen generate-kicad-target-pack --outdir out/kicad_target_pack
```

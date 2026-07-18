# Progen KiCad Local Generator

## Codex 5.6 Current Local Path

Codex 5.6 replaced the old V1-only local flow with the active source-backed
pipeline, portable executable, validation stack, and qualified corpus. The
direct source command is now:

```bash
PYTHONPATH=. python -m kicad.pipeline.progen_kicad_executable run INPUT.json \
  --output-root /tmp/progen-kicad-runs --routing-mode combination
```

This is the large 5.6 improvement over the earlier 5.5-era local experiments:
the same command fixes loose JSON, resolves real symbols/pins, places, routes,
validates expected connectivity, conditionally creates a PCB, and packages the
result. The portable launcher is the same source pipeline behind a distribution
wrapper. See [`kicad/README.md`](kicad/README.md) for current usage.

## Historical V1 CLI

The preserved V1 CLI record is:

```text
python -m proteusgen generate-kicad kicad/examples/json/vdc_resistor_op.json --outdir out/kicad_v1
python -m proteusgen plan-kicad-layout kicad/examples/json/rc_lowpass_tran.json
python -m proteusgen generate-kicad-target-pack --outdir out/kicad_target_pack
python -m proteusgen kicad-source-reference
```

Each generated project contains exactly one `.kicad_pro` and one matching `.kicad_sch` file. Open only the `.kicad_pro` file.

## Offline Batch Mode

For local/manual JSON testing without any API:

```text
python kicad/automation/local_generate_experiments_with_groq.py --offline-json path/to/json_folder
```

Outputs are written to:

```text
kicad/experiments/runs/local_YYYYMMDD_HHMMSS_<label>/
```

## Optional Groq Mode

The old Groq runner is still present for experiments:

```text
RUN_LOCAL__TEST_GROQ_CONNECTION.bat
RUN_LOCAL__ASK_API_AND_GENERATE_KICAD_EXPERIMENTS.bat
```

The API key is read at runtime and is never written to disk.

## Bundled Source Data

The KiCad source-pack zip is stored under:

```text
kicad/source_pack/downloaded_zip/KiCad_Source_Files_Needed_20260612_030305.zip
```

The V1 generator mines exact embedded symbol blocks from this source pack for `Device:R`, `Device:L`, `Simulation_SPICE:VDC`, `Simulation_SPICE:VSIN`, and `power:GND`. Missing V1 symbols such as `C`, `IDC`, and `VAC` are generated as project-local embedded symbols.

## C01-C55 Target Pack

The deterministic offline target-pack generator is:

```text
python kicad/automation/generate_target_pack.py --outdir kicad/experiments/runs/local_20260613_target_pack_c01_c55_v3
```

It generates all 55 target circuits from `kicad/targets/proteus_generator_circuit_test_set_ocr.md`. Broad digital nets use repeated local labels; ordinary local/analog nets still use Manhattan wires.

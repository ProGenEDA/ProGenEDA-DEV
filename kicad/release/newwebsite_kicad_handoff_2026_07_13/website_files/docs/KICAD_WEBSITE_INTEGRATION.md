# KiCad Website Integration Contract

The KiCad generator is deterministic after it receives canonical main JSON.

## API input

For the first KiCad website integration, use:

```json
{
  "prompt": "optional original user prompt",
  "targetService": "KC",
  "mainJson": {
    "circuit_id": "demo",
    "components": [],
    "nets": [],
    "routing": { "mode": "combination" }
  }
}
```

Do not call the KiCad executable with only a natural-language prompt. The prompt
enhancer/final JSON compiler is a separate upstream stage.

## Executable output

The executable prints a JSON run manifest. For each generated circuit:

- `output_artifacts.serial`
- `output_artifacts.user_project.path`
- `output_artifacts.user_project.file_name`
- `output_artifacts.internal_bundle.path`

The website should store the user project zip as the public export artifact and
store the internal bundle privately.

## PCB-only API output

For a selected KiCad PCB-only request, invoke `run-pcb` through
`generatePcbOnlyWithKiCadExecutable`. It uses the same canonical `mainJson`,
but returns one direct native `.kicad_pcb`. Internally it still creates the
schematic contract required for source-backed pad resolution. If the physical
subset is unmapped or bounded routing/hosted PCB validation fails, it returns
no board rather than a partial candidate.

## Serial registry

Install `KC-A.json` next to `PR-A.json`. KiCad serials use:

```text
KC-A-<COMPRESSED_BOM_CODE>-<SUFFIX4>
```

`KC-A` codes must remain append-only once public serials exist.

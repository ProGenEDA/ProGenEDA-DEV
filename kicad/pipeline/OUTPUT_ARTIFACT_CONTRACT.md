# Output Artifact Contract

This contract defines the final output boundary for KiCad generation.

Every complete generated circuit produces two archive classes and may produce
one direct PCB artifact:

```text
1. user_project      user-downloadable export
2. internal_bundle   backend/database-only metadata zip
3. user_pcb          optional direct native PCB file, accepted boards only
```

The frontend/user receives `user_project` and, when present, `user_pcb`. The internal bundle is stored
by the backend database/storage layer under the generated serial and must never
be returned through public serial download routes.

## Output Packager

Canonical script/module:

```text
kicad/pipeline/output_packager.py
```

CLI:

```bash
PYTHONPATH=. python -m kicad.pipeline.output_packager <generated_project_run_dir>
```

The packager is also called automatically by:

```text
kicad/pipeline/kicad_wire_maker.py
```

for wire, terminal, and combination project runs.

## Folder Layout

For each generated project:

```text
outputs/<circuit_id>/
  output_manifest.json
  user_project/
    PROGEN_KICAD_PROJECT.zip
  user_pcb/
    <project>.kicad_pcb
  internal/
    internal_bundle.zip
```

`output_manifest.json` is backend metadata. It is useful for importing the run
into a database, but it is not a user-facing file.

## User Project Archive

Path:

```text
outputs/<circuit_id>/user_project/PROGEN_KICAD_PROJECT.zip
```

Visibility:

```text
user_downloadable
```

Contents:

```text
project/<main>.kicad_pro
project/<main>.kicad_sch
project/<optional accepted main>.kicad_pcb
project/<optional KiCad project-local library/table files>
```

Rules:

- No internal JSON.
- No prompts.
- No validation reports.
- No route-variant metadata.
- No source catalogue dumps.
- Must contain a `.kicad_pro` and `.kicad_sch` for KiCad portability.
- Contains `.kicad_pcb` only after independent hosted PCB validation passes.
- Never contains `pcb_internal` or a `.candidate.kicad_pcb`.

The website may expose this as the serial-downloadable artifact.

## Internal Bundle

Path:

```text
outputs/<circuit_id>/internal/internal_bundle.zip
```

Visibility:

```text
internal_only
```

Required contents:

```text
internal/output-metadata.json
internal/main-input.json
internal/placement-input.json
internal/routing-input.json
internal/wire-plan.json
internal/project-manifest.json
internal/run-manifest.json
internal/arrangement-variants.json
internal/component-summary.json
internal/local-netlist-validation-report.json
internal/value-edit-report.json
internal/value-validation-report.json
internal/final-validation-report.json
internal/component-body-overlap-report.json
all_generated_json/<all per-circuit generated JSON files>
export/KC/PROGEN_KICAD_PROJECT.zip
```

Rules:

- This bundle stores all non-user metadata and all generated JSON.
- Rejected arrangement/routing variants must be retained here.
- The accepted variant must be clearly marked.
- This bundle may include a copy of the user project archive for internal
  reconstruction, but public routes must not serve the internal zip itself.

## Serial

Current KiCad serial shape:

```text
KC-A-<COMPRESSED_BOM_CODE>-<SUFFIX4>
```

This follows the website serial model:

```text
<SERVICE>-<TABLE_VERSION>-<COMPRESSED_BOM_CODE>-<SUFFIX4>
```

Current fields stored in `output_manifest.json`:

- `serial`
- `service`
- `table_version`
- `canonical_bom_code`
- `compressed_bom_code`
- `suffix`
- `component_summary`
- `component_code_map`

Database import should use the serial as the stable lookup key. Component code
registries must remain append-only: never reuse a code for a different meaning.
KiCad `KC-A` component/count codes use uppercase Base36 characters (`0-9A-Z`)
so they remain compatible with the current website registry decoder, which
uppercases component codes during lookup.

## Variant Retention

Route/placement variants are stored at:

```text
internal/arrangement-variants.json
```

Shape:

```json
{
  "schema": "progen-kicad-arrangement-variant-metadata/v0.1",
  "accepted_variant": "compact_flow",
  "variant_count": 5,
  "selection": {},
  "variants": [
    {
      "index": 0,
      "name": "compact_flow",
      "accepted": true,
      "score": {},
      "coordinate_edit_count": 42,
      "elapsed_seconds": 0.25,
      "error": null,
      "coordinate_plan": {}
    }
  ]
}
```

Terminal and bounded combination fast paths may have only one accepted variant
today. Strict wire and future visual variation generation can store many.

## Run Manifest Fields

Each project result in `run_manifest.json` records:

- `output_artifacts.serial`
- `output_artifacts.user_project`
- `output_artifacts.internal_bundle`
- `output_artifacts.retained_variants`

The run manifest also contains:

```json
{
  "output_artifact_contract": {
    "schema": "progen-kicad-run-output-artifacts/v0.1",
    "user_visible_artifact": "user_project",
    "internal_only_artifact": "internal_bundle",
    "artifact_count": 1
  },
  "output_artifacts": []
}
```

## Website Boundary

Matches the website storage policy:

```text
local-data/export-artifacts/<service>/<serial>/vN/<project file>
local-data/internal-artifacts/<scope>/<service>/<serial>/vN/internal_bundle.zip
```

The KiCad generator does not write into the website database directly. It emits
database-ready metadata so the hosting service can save:

- circuit record
- serial registry row
- version row
- user-downloadable export artifact row
- internal-only bundle artifact row
- validation and generation-run metadata

## Rust Rule

Packaging, zipping, metadata assembly, and JSON copying are not hard numerical
work, so they stay in Python.

Heavy route search, contact scoring, dense placement scoring, and future
multi-variation optimization remain the Rust acceleration targets.

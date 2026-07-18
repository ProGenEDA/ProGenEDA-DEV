# EasyEDA Pro Website Handoff

This package adds the release-candidate EasyEDA Pro backend to the audited
`newwebsite` checkout. It contains a ready-to-apply website overlay, the
portable native generator, the complete 300-circuit qualification corpus,
frontend and API integration, deterministic JSON Lab support, component
registry data, real progress streaming, tests, and release evidence.

## Apply

From this extracted handoff directory:

```bash
python3 apply_handoff.py /path/to/newwebsite
cd /path/to/newwebsite
npm run build
```

The installer verifies `baseline_hashes.json` before writing. It refuses to
overwrite files that differ from both the audited baseline and this overlay.
Use `--dry-run` to inspect the operation. `--force` is available only for an
intentional manual merge.

## Runtime

The default paths require no extra configuration:

```text
vendor/easyeda/progen-easyeda
vendor/easyeda/examples-300
local-data/easyeda-runs
```

`api.env.easyeda.example` documents optional overrides. The executable emits
one validated native `.eprj` as the public artifact and retains its internal
audit ZIP in the circuit record. It supports `combination` (default), `wire`,
and `terminal` schematic modes. PCB data is included in the same project only
after bounded physical validation passes.

## Evidence

- `evidence/corpus_audit.json`: independent structural audit of all inputs.
- `evidence/qualification_report.json`: all 300 inputs through the portable.
- `release_manifest.json`: file hashes and release summary.
- `information.md`: product scope, architecture, limits, and future work.
- `NEWEBSITE_EASYEDA_AUDIT.md`: every website integration surface changed.
- `IMPLEMENTATION_CHECKLIST.md`: deployment and acceptance checklist.

The corpus inputs are present once as the canonical flat corpus and once in
the website example-library layout. Both copies are byte-identical.

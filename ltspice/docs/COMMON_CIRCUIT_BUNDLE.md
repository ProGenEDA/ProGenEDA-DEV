# Common donor-native LTspice bundle

`ltspice.pipeline.common_circuit_bundle` turns the 100 named canonical
circuits into a user-facing bundle without bypassing the real generator.

```bash
cd /home/zaruka/Documents/kicad
PYTHONPATH=. python -m ltspice.pipeline.common_circuit_bundle \
  /tmp/ltspice-common-circuit-bundle \
  --archive /tmp/ltspice-common-circuit-bundle.zip
```

The output path and ZIP must be outside the repository.  A non-empty output
folder or existing archive is rejected rather than overwritten.

For each of the 100 title-named folders, the bundle contains:

```text
001_voltage-divider/
  circuit.json             # untouched canonical shared JSON input
  001_voltage-divider.asc  # produced by ordinary donor-native generation
  accuracy_check.txt       # expected behavior plus deterministic generation facts
```

It also contains `CORPUS_INDEX.md` and `BUNDLE_MANIFEST.md`.  The bundle does
not include temporary executable internals unless `--retain-native-work` is
requested, and even then they are excluded from the ZIP.

## Generation boundary

The bundler rejects `ltspice_at`, `at`, `position`, and `coordinates` in a
corpus input.  It invokes `run_donor_native_executable` normally, lets that
path choose placement and direct physical wires, then copies its independently
validated ASC into the matching corpus folder.  It does not render raw ASC,
perform manual placement, launch LTspice, capture screenshots, or run external
netlisting.

Each checklist appends stable facts: ASC SHA-256, logical/stock symbol counts,
physical wire and ground-flag counts, directive count, and the native
no-terminal/no-custom-symbol validation state.  Elapsed time, timestamps, and
machine-specific paths are intentionally excluded.

## Optional installed-LTspice netlist record

After a trusted local LTspice run has produced one nonempty sibling `.net` file
for every generated ASC, call
`record_installed_netlist_validation(bundle_directory, archive_path=...)` from
this module. It refuses incomplete evidence, appends the native netlist hash to
each `accuracy_check.txt`, writes `LTSPICE_26_NETLIST_VALIDATION.txt`, and
refreshes the ZIP atomically. The machine-local `.net`, `.log`, `.raw`, and
`.cir` sidecars remain outside the portable ZIP while their hashes and result
are recorded in it.

## Reproducible archive

The ZIP uses a fixed archive root, fixed timestamp/permissions, sorted files,
and fixed compression level.  Equal generated contents produce equal archive
bytes; the ZIP excludes `.native_run` executable internals.

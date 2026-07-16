# Legacy Conversion Failure V1

## Project

`Easyeda/examples/generated_runs/2026_07_16_201556_604929_easyeda_regulated_5v_supply`

## Result

EasyEDA Pro rejected the first generated project with:

```text
Failed to open project, Non-3.0 project conversion failed,
Failed to get historical project data!
```

The desktop conversion attempt replaced the original `.eprj` with a zero-byte
file and retained `.eprj2` and `.eprj_backup` copies. The original pre-open
project remains inside that run's internal ZIP.

## Root Cause

The donor template used the legacy `0.0.3` SQLite schema. The emitter changed
the project UUID but retained donor-scoped `project_members`, `coppers`, and
`texts` rows, and it did not provide the `branch_uuid` identity expected by
EasyEDA 3.x. EasyEDA therefore entered legacy history conversion and attempted
to recover historical data for inconsistent project identities.

## Fix

- Add a deterministic non-empty `branch_uuid` to every generated project.
- Rebind `project_members` to the generated project UUID.
- Remove donor-derived copper and text cache rows.
- Validate all three conditions without EasyEDA installed.
- Open only a disposable acceptance copy so the immutable `.eprj` deliverable
  remains unchanged.

The corrected native-open acceptance is documented by the later generated run
and the shared-power visual experiment.

# Big Circuit Trials - Proteus 8.13 Metadata Patch

User reported BIG11 repack control opened with a warning that the project was created for a later Proteus version than the installed version.

## New version-control experiment

A new pack was generated: `BIG_CIRCUIT_TRIALS_V813_PATCHED.zip`.

Every `.pdsprj` in the pack has `PROJECT.XML` patched to:

```xml
RELEASE="813"
FILEVER="830"
```

Only `PROJECT.XML` metadata was patched. Circuit data in `ROOT.DSN` and `ROOT.CDB` was otherwise preserved from the previous big trial pack.

## Purpose

Test whether Proteus' later-version warning is controlled only by `PROJECT.XML` metadata.

## Interpretation

If BIG11 no longer gives a later-version warning:

- The warning is likely controlled by PROJECT.XML `RELEASE`/`FILEVER` fields.
- Version normalization for generated projects can start with PROJECT.XML patching.

If BIG11 still gives the warning:

- Version data is also stored somewhere else.
- Candidate locations: ROOT.DSN early metadata region, ROOT.CDB metadata, or another hidden version marker.

## Test order

1. Test `BIG11_repack_control_digital_clock_no_change` first.
2. Record whether the later-version warning appears.
3. If BIG11 passes without warning, continue BIG01/BIG02.
4. If BIG11 still warns, return the result and stop; further version-field search is needed.

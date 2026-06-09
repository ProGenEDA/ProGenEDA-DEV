# Mixed IC Cross-Donor V2 Metadata Retry - 2026-06-09

This note documents the retry after `MIXED_IC_CROSS_DONOR_V1_TEMP_2026_06_09`
failed in Proteus.

## V1 Failure

User testing reported:

```text
T01 and T06: LXLCORE.dll error
T02 through T05: Proteus crashed while trying to open
```

The visible object-region strategy is not isolated by this result, because
Proteus failed at metadata/load time.

## V2 Changes

V2 keeps the same six visible IC-region combinations as V1. It changes only
metadata handling:

- every concatenated donor device-section tail pointer is patched to the
  generated object-data pointer;
- selected `ROOT.CDB` rows are sorted by numeric `U` reference before emission.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_v2_metadata_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_v2_metadata_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_V2_METADATA_TEMP_2026_06_09.zip
```

Automated result:

```text
6 generated projects
0 static validation issues
python -m pytest tests -q => 110 passed, 78 subtests passed
archive_sha256: 0cbfb0cfb34878d1bd8a21d930f43e3e7be760007062c34cb6dcbbcbaa10ed7d
```

## Boundary

If V2 still crashes, stop cross-donor metadata synthesis and ask for a real
manual donor containing at least one counter/divider IC and one misc logic IC in
the same project. That donor is needed to learn Proteus-authored merged device
section behavior.

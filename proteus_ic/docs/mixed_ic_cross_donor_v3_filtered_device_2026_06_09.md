# Mixed IC Cross-Donor V3 Filtered Device Probe - 2026-06-09

This note documents the stricter retry after both V1 and V2 cross-donor IC
mixtures failed in Proteus.

## Prior Failures

V1 concatenated donor device sections without patching section footers. V2
patched every concatenated donor device-section footer and sorted selected
`ROOT.CDB` rows, but user testing still reported:

```text
T01 and T06: LXLCORE.dll error
T02 through T05: Proteus crashed while trying to open
```

The repeated failure means complete donor device-section concatenation is not a
safe way to mix unrelated IC donor families.

## V3 Changes

V3 keeps the accepted visible whole-object-region method, but rebuilds the
device metadata more narrowly:

- parse each donor device section as per-device length-prefixed definitions
  plus one final object-data pointer footer;
- use passive and analog markers as definition boundaries only;
- select only the device definitions required by the generated project;
- exclude unrelated analog/passive tails such as `CAP-ELEC`, `LM741`, `NPN`,
  `PNP`, `REALIND`, and `RESISTOR`;
- emit a single generated final footer pointer for the rebuilt device section;
- keep V2's sorted selected `ROOT.CDB` rows.

This is still an experiment. It is not promoted to the main generator until the
user confirms the generated pack opens in Proteus.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_v3_filtered_device_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_v3_filtered_device_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_V3_FILTERED_DEVICE_TEMP_2026_06_09.zip
```

Automated result:

```text
6 generated projects
0 static validation issues
python -m pytest tests -q => 111 passed, 78 subtests passed
archive_sha256: 88da0e597e8b6a81b37eda2070b1d283354dc76a23152ace37ea2d77863f0fc6
```

## Boundary

If V3 still crashes or throws load-time DLL errors, stop synthetic cross-donor
IC merging and request a manual Proteus donor containing at least one
counter/divider IC and one misc logic IC in the same project. That donor is
needed to learn the Proteus-authored merged device-section behavior.

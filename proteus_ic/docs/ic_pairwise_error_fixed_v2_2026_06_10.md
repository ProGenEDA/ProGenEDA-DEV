# IC Pairwise Error Fixed V2 - 2026-06-10

## Why this pack exists

The user confirmed that `IC_PAIRWISE_ERROR_FOCUSED_V1_TEMP_2026_06_10`
worked for `S01+S02`.

That confirmed the root fix for failed pairwise cases involving accepted
combinational ICs:

- do not splice whole exact-rezip donor chunks for the combinational side;
- do not copy a donor `U2` body as a shortcut;
- generate the combinational side from the locked gate-slice writer;
- emit fresh package references, object IDs, terminal suffixes, and CDB rows.

## Scope

Generated archive:

```text
experiments/IC_PAIRWISE_ERROR_FIXED_V2_TEMP_2026_06_10.zip
```

Generated folder:

```text
experiments/ic_pairwise_error_fixed_v2_temp_2026_06_10
```

This pack only emits V1-reported rejected pairs that include at least one
accepted combinational source:

```text
S01 = 74HC00
S02 = 74HC02
S03 = 74HC04
S04 = 74HC08
S05 = 74HC32
S06 = 74HC86
S07 = 74HC266
```

It does not touch V1-passed pairs.

## Output count

```text
generated_pair_count = 65
deferred_pair_count  = 44
static_issue_count   = 0
```

The generated cases split into:

```text
15 accepted combinational + accepted combinational pairs
50 accepted combinational + exact donor pairs
```

Deferred cases are recorded in `summary.json`. They include:

- non-combinational-only duplicate-reference failures, such as `S08+S09`;
- non-combinational-only no-model failures, such as `S21+S22`;
- coordinate-only refreshed-4060 cases from V1, because those were not part of
  the accepted `S01+S02` repair mechanism and should not be touched blindly.

## Mixed repair method

For accepted-combinational plus exact-donor pairs:

1. Keep the non-combinational donor native.
2. Parse its existing CDB and preserve its object IDs.
3. Add the accepted combinational gate after the donor with:
   - next free package ref, for example `U2`;
   - object ID greater than the donor max object ID;
   - a fresh CDB pin row;
   - a fresh CDB package property row.
4. Build the project from `E001` with both the donor device section and the
   combined accepted-combinational device section.

Representative static checks:

```text
P001_S01_S02_FIXED_ACCEPTED_COMBINATIONAL:
  CDB pin refs: U1:A, U2:A
  CDB property refs: U1, U2
  object IDs: 1, 2

P007_S01_S08_FIXED_ACCEPTED_PLUS_DONOR:
  CDB pin refs: U1, U2:A
  CDB property refs: U1, U2
  object IDs: 1, 2

P026_S01_S27_FIXED_ACCEPTED_PLUS_DONOR:
  CDB pin refs: U1, U2:A
  CDB property refs: U1, U2
  object IDs: 13, 14
```

## Validation

Commands run:

```text
python -m py_compile tools\proteus_generation\2026-06-10\generate_ic_pairwise_error_fixed_v2_temp.py
python tools\proteus_generation\2026-06-10\generate_ic_pairwise_error_fixed_v2_temp.py
python -m pytest tests\test_ic_pairwise_error_focused.py -q
python -m pytest tests\test_ic_pairwise_error_focused.py tests\test_mixed_ic_analog_donors.py::test_ic_pairwise_34_v1_uses_clean_source_matrix_and_generic_cdb_splitter -q
```

Results:

```text
2 passed
3 passed
```

Archive SHA256:

```text
5ACF559B8156B47A32C31FD3F1598B0D76B653BFDE9F0C3A0AB9278D9A0979A1
```

## Proteus status

Passed user Proteus open/simulate testing on 2026-06-11. The user reported
that all 65 generated projects in this pack worked.

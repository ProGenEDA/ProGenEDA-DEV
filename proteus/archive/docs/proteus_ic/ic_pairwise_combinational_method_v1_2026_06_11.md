# IC Pairwise Combinational Method V1 - 2026-06-11

## Why this pack exists

`IC_PAIRWISE_ERROR_FIXED_V2_TEMP_2026_06_10` passed user Proteus testing for
all 65 V1-rejected pairs that included at least one accepted combinational IC.

That result supports testing the same method more broadly:

- use fresh accepted combinational gate slices for any `S01..S07` side;
- keep exact non-combinational donors native when they are paired with a
  combinational side;
- do not use whole-donor copy/paste for accepted combinational ICs.

## Generated archive

```text
experiments/IC_PAIRWISE_COMBINATIONAL_METHOD_V1_TEMP_2026_06_11.zip
```

Generated folder:

```text
experiments/ic_pairwise_combinational_method_v1_temp_2026_06_11
```

Archive SHA256:

```text
FD1CC8B409174FBBFB3F4BC1C3290348C70AB008C3D2EA45BCC2BACB96E77468
```

## Scope

```text
source_count                      = 34
combinational_method_pair_count   = 210
noncomb_probe_pair_count          = 21
static_issue_count                = 0
```

The 210 combinational-method pairs are every unordered pair that contains at
least one accepted combinational source:

```text
S01 = 74HC00
S02 = 74HC02
S03 = 74HC04
S04 = 74HC08
S05 = 74HC32
S06 = 74HC86
S07 = 74HC266
```

The 21 non-combinational-only pairs are a probe set, not an accepted route.
They intentionally focus on the earlier failure families: counters/dividers,
shift/register devices, 7447, NE555, and refreshed 4060.

## Method

For accepted-combinational plus accepted-combinational pairs:

1. Regenerate both sides from locked combinational gate slices.
2. Emit fresh object IDs, terminal suffixes, and CDB rows.
3. Keep IC pins directional.

For accepted-combinational plus non-combinational pairs:

1. Preserve the exact non-combinational donor chunk.
2. Preserve its native CDB rows and device section.
3. Add one fresh accepted combinational gate slice with the next free package
   ref and object ID.

For non-combinational-only probes:

1. Preserve both exact donor chunks.
2. Remap the right donor package ref to a free same-length `U` reference.
3. Relabel the right donor terminals.
4. Translate the right donor body and terminals.
5. Patch only colliding right-side CDB pin/property IDs; preserve native IDs
   when they are already unique.

Representative non-combinational probe behavior:

```text
P211_S08_S09:
  right U1 -> U2
  right CDB ID 1 -> 2

P471_S21_S22:
  right U1 -> U2
  right CDB IDs 33 and 23 preserved because they do not collide
```

## Validation

Commands run:

```text
python -m py_compile tools\proteus_generation\2026-06-11\generate_ic_pairwise_combinational_method_v1_temp.py
python tools\proteus_generation\2026-06-11\generate_ic_pairwise_combinational_method_v1_temp.py
python -m pytest tests\test_ic_pairwise_error_focused.py -q
python -m pytest tests -q
```

Results:

```text
4 passed
133 passed, 78 subtests passed
static_issue_count = 0
```

## Proteus status

Pending user Proteus testing. Test the 210 combinational-method cases first.
The 21 non-combinational-only projects are probes to determine whether the
fresh-identity rule can transfer beyond accepted combinational gate slices.

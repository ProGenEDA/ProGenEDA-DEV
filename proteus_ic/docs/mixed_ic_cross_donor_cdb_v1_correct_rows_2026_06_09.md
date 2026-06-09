# Mixed IC Cross-Donor CDB V1 Correct Rows

## Purpose

`MIXED_IC_CROSS_DONOR_CDB_V1_CORRECT_ROWS_TEMP_2026_06_09` replaces the old
ASCII-based `ROOT.CDB` row slicer with `src/proteusgen/cdb.py`.

The goal is to learn whether Proteus accepts generated CDB row unions once the
rows are sliced on real binary boundaries.

## Decoded CDB Rules

- The device/object count is a little-endian u32 at offset `92`.
- Pin rows start at offset `96`.
- Each pin row has a 16-byte header, a length-prefixed reference, a u32 pin
  count, length-prefixed pin-name/pin-number pairs, and a 12-byte footer.
- A fixed 18-byte section separates pin rows from property rows in the observed
  donors.
- Property rows use a 20-byte header, then four length-prefixed strings:
  reference, device, value, and package.
- Property-row references use package names. A pin row named `U7:A` maps to a
  property row named `U7`.
- The property blob length overlaps the first dword of the next property row.
  Non-final emitted property rows must exclude that next dword. Final emitted
  property rows must include a four-byte trailer.

## Test Pack

Command:

```powershell
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_cdb_v1_correct_rows_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_cdb_v1_correct_rows_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_CDB_V1_CORRECT_ROWS_TEMP_2026_06_09.zip
```

Cases:

- `T00`, `T06`: full-CDB controls.
- `T01`-`T03`, `T07`-`T09`: correctly sliced generated rows preserving donor
  ordinals.
- `T04`-`T05`, `T10`-`T11`: correctly sliced generated rows renumbered to
  emitted row order.

## Current Status

Static generation completed. All generated CDB outputs parse back through the
new parser. Manual Proteus open/render testing is pending.

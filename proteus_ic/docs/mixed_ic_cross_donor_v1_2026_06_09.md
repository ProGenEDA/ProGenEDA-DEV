# Mixed IC Cross-Donor V1 - 2026-06-09

This note documents the first attempt to combine IC regions from different
accepted mixed donors where the user did not supply that exact combination.

## Purpose

The earlier accepted packs proved:

- complete real mixed donors can be repacked/transplanted/relabelled;
- complete balanced regions can be retained or removed inside one donor.

This V1 pack tests the next risk level: combining complete IC regions from
different donors.

## Constraints

To avoid repeating the failed unit-slicing path, this pack keeps strict limits:

- combine only complete IC regions;
- avoid analog/passive regions in this first cross-donor probe;
- choose only regions whose existing `U` references do not collide;
- do not rewrite component references;
- generate unique bidirectional terminal labels per retained region;
- build a union `ROOT.CDB` from selected `U` rows;
- concatenate donor device sections from the involved donors.

## Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_cross_donor_v1_temp.py
```

Output:

```text
experiments/mixed_ic_cross_donor_v1_temp_2026_06_09
experiments/MIXED_IC_CROSS_DONOR_V1_TEMP_2026_06_09.zip
```

Automated result:

```text
6 generated projects
0 static validation issues
python -m pytest tests -q => 109 passed, 78 subtests passed
archive_sha256: 5b255e371e67460b0e132e3b38f577c88b5c07fe24a2eff6ae0c8e1e3b717403
```

## Case Intent

- Mix `74HC595`, `74HC165`, `7447`, `74HC157`, `74HC283`, and `74HC85` with
  late counter/divider regions such as `4518`, `74HC4060`, `74HC4040`, `7490`,
  `74HC160`, `74HC161`, and `74HC163`.
- Mix the `4017`/`4020`/`74HC4024` divider chain with shift registers.
- Mix `74HC192`/`74HC193` with comparator/mux/adder style IC regions.
- Mix the `7447` decoder/driver with synchronous counters.

## Test Boundary

This is not production synthesis yet. If V1 passes Proteus testing, the next
step is a ref-collision probe that rewrites selected `U` references in a
controlled same-length way, then a device-section/CDB cleanup probe.

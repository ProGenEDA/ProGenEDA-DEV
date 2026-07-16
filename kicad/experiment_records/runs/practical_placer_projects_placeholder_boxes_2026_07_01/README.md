# Practical Placer Projects: Placeholder Box Run

Date: 2026-07-01

## What Was Tested

Generated 20 openable KiCad projects from the practical placer pack.

This was the old approach where each component used a generated `ProgenPlace:*` symbol that drew a rectangle and a name.

## Previous State

The placer could create project folders and KiCad could load the schematics, but the symbols were not real KiCad library components.

## Outcome

Historical failed direction.

- KiCad CLI quality report: 20 schematics checked, 20 passed, 0 failed.
- Static content: 20 schematics, 100 symbol instances.
- Problem: 200 `ProgenPlace` strings across the generated schematics.
- User-visible issue: names like `X1` and values appeared, but actual real components were not present.

## Known Limits

This archive is intentionally kept as evidence of what did not satisfy the requirement. Do not use it as the supported baseline.

## Next

Replaced by `../practical_placer_projects_real_symbols_flattened_2026_07_01`, which embeds real KiCad symbols and removes placeholder boxes.

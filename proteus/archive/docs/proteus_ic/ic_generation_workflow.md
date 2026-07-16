# IC Generation Workflow

## Locking Rule

No IC family is promoted into the main generator until all lock cases:

- open in Proteus 8.13;
- save/reopen without deleting or changing package/subpart bindings;
- simulate successfully where a diagnostic truth-table case exists.

## Donor Progression

For each IC family:

1. Import single-gate and all-subpart donors.
2. Extract `ROOT.DSN` object chunks and `ROOT.CDB`.
3. Rebuild exact donor content into the E001 base.
4. Mutate terminal labels only.
5. Mutate package/subpart refs only after label mutation works.
6. Mutate coordinates only after package/subpart mutation works.
7. Combine with passive loads only after the pure IC path is accepted.

## Stop Conditions

Stop the current mutation direction if Proteus reports:

- `VGDVC.DLL` or `ISIS.DLL`;
- Bad Object Record;
- missing library device;
- wrong package ownership;
- `U1:A` and `U1:B` no longer belonging to the same package;
- save/reopen instability.

When a stop condition appears, create the smallest donor that isolates that one
change. Do not patch blindly.


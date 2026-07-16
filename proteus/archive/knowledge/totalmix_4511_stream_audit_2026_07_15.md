# Totalmix 4511 Stream Audit — 2026-07-15

## Authoritative evidence

- User-saved project: `experiments/totalmix_gate_manual_terminal_donor_v1_temp_2026_07_15/terminalized49.pdsprj`
- `ROOT.DSN` SHA-256 after the user re-saved it: `3837d6d4d20e69ab0e9092d002e561213563eda1956f5562ea31724eccd4ffd7`
- The project contains all 49 requested component packets, 318 active `$TERBIDIR` records, and 318 `WIRE` records.
- The earlier 47-packet observation was from the pre-save version and is superseded by this file.

## U9 / 4511 boundary facts

The user donor's 4511 packet begins at object-stream offset `46544`. Its seven output-terminal records are immediately before U9 (offsets `45836` through `46442`) and their seven WIRE records are immediately after U9 (markers `47004` through `47304`). Every corresponding U9 active pin-link field ends in `02 00`.

This is inconsistent with the existing `totalmix_combined_v1` cache, which treated 4511 as a late-tail family with active trailer `03 00`. That mismatch begins at U9 and is the evidence-backed explanation for the post-4511 stream loss reported by the user.

The dedicated 4511 terminal donor already proves the complete 14 non-supply-pin order:

`13, 12, 11, 10, 9, 15, 14, 7, 1, 2, 6, 3, 4, 5`.

## Repair rule

Only the combined mixed profile changes:

1. Serialize 4511 as `terminal_leading_component_then_wires`, adjacent to U9.
2. Use the complete dedicated-donor order above.
3. Use `02 00` for 4511's active component-pin links.
4. Remove 4511 from the delayed decoder/mux tail. The `74HC151` tail remains unchanged.

No standalone 4511 route and no frozen accepted family geometry, terminal orientation, wire geometry, or suffix allocation policy is changed.

## Controlled generated probe

`experiments/totalmix_4511_inline_boundary_probe_v1_temp_2026_07_15/ALL49_4511_INLINE_TRAILER0200_REPAIR.pdsprj`

was emitted through the shared placer using these rules only. Its internal terminal report records 49 components, 318 terminals, 318 WIRE records, all 14 U9 terminals inline, and only `02 00` U9 link trailers. It still requires user Proteus visual acceptance; no local Proteus process was launched for this audit.

## Fresh all-49 regression and geometry audit

The final fresh candidate is:

`experiments/totalmix_4511_inline_0200_repair_v1_temp_2026_07_15/ALL49_TERMINALIZED_1X_4511_INLINE_0200_REPAIR.pdsprj`

It was freshly produced from the locked `new_components_5x_mega.pdsprj` through the ordinary component placer, beautifier, and shared terminal placer. Its paired bare control is `ALL49_BARE_COMPONENT_PLACER_1X.pdsprj` in the same directory.

Mechanical checks passed without launching Proteus:

- The bare and terminal-stripped output streams both contain all 49 placed component groups with identical per-family counts.
- The output contains 318 `$TERBIDIR` records and 318 `WIRE` records.
- U9 has 14 terminal/WIRE attachments, all with `02 00` component-link trailers; U9 is immediately followed by the existing U49 mux tail and then U13/4027.
- The focused profile regression, full-49 regression, accepted two-pin regression, and dedicated 4511 regression pass.
- The multipart beautifier already separates every tested A/B/C/D logic package by `5,080,000` schematic units. In the generated all-49 candidate, gate terminal WIRE Manhattan lengths are `157,480` to `452,120` units; none exceeds the two-grid (`508,000`) short-wire threshold. Therefore no geometry change was made merely from the hypothesis; a Proteus visual test is still the authority for spacing acceptance.

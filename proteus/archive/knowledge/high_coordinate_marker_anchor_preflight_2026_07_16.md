# High-coordinate native two-pin marker preflight — 2026-07-16

## Scope

The user requested the already accepted native two-pin mixed route at 30× and
higher.  This is not a new terminal geometry, template, component family, or
ROOT.CDB change.  It is a narrow parser-range repair required to read valid
body anchors after the component placer has positioned them at larger scales.

## Authority and complete focused evidence

- Locked source donor: `proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
- Exact 30× uneven placed control:
  `experiments/non_ic_totalmix_matrix_v1_temp_2026_07_16/01_native_two_pin18/N09_REGEN_DEBUG_BARE.pdsprj`.
- Request: 30 of every native two-pin family except the locked-mega
  `CAP-ELEC` ceiling of 21, for 531 placed components.
- The complete ROOT.DSN object stream was reparsed by raw groups.  The
  resistor packet grammar is unchanged between R23, R24, and R30: a native
  non-length-prefixed body marker (`00 08 RESISTOR <s32 x><s32 y>`) provides
  the terminal anchor.
- R23's anchor is `(31,983,680, 671,708,080)`, which passes the old 700M
  guard.  R24 is `(24,363,680, 702,950,080)` and R30 is
  `(24,363,680, 879,988,080)`; both are valid signed, grid-aligned native
  coordinates but fail only that guard.  The full 531-component layout's
  maximum absolute body bound is `912,134,320`.

## Difference set and repair

The terminal planner asks `layout_coordinate_pairs(..., family)` only for the
direct `marker_body:<family>` anchor.  The generic scan must remain at 700M:
it is intentionally broad and could mistake arbitrary payload for coordinates.
Only `_strict_marker_body_coord_pair_ok` is widened to a separately named
2,000,000,000 signed-coordinate ceiling.  Its existing family-marker,
non-length-prefix, non-embedded-ASCII, integer-grid, and nonzero checks are
unchanged.  No terminal record, pin link, WIRE, component packet, CDB member,
placement order, or accepted-family geometry is modified.

## Verification plan

1. Unit-test a high direct body marker and prove the family-less generic scan
   still ignores it; reject a marker beyond the strict bound.
2. Regenerate the exact 30× request through the existing shared component
   placer and shared terminal placer.
3. Run static validation, then delayed local Proteus open and cold reopen on a
   copied terminalized project.
4. Regenerate and gate at least one higher uneven scale.  Stop at the first
   demonstrated component-placer, serializer, signed-coordinate, or Proteus
   loader ceiling; record the actual limit rather than inventing one.

## Addendum: full 30× temporary-suffix audit

After the marker repair, the fresh 30× project emitted 1,062 terminal records
and reached final WIRE-address rebasing.  A complete scan of its active
terminal suffixes found exactly two duplicate low-word pairs, not a geometry or
packet-order failure:

- `4172`: CAP `C01M` and REALIND `L01C`;
- `7132`: RESISTOR `R025B` and VSINE `S005`.

Every other temporary suffix (1,060 of 1,062) is unique.  The final rebase
stage already allocates unique suffixes from final WIRE addresses, but it
correctly refuses an ambiguous temporary suffix because it cannot safely map
two component pin-links to separate WIREs.  The repair is therefore a
collision-only remap: preserve the first stream occurrence and assign later
duplicates from unused `0x7A00+` temporary slots before final rebasing.  The
slots are an already established mixed catalogue temporary namespace.  It
does not alter terminal coordinates, labels, WIRE geometry/order, donor
packets, final WIRE-address allocation, ROOT.CDB, or any no-collision route.

## Results

- Focused tests: the strict high-marker and collision-only suffix allocator
  tests pass; compileall passes.
- A dynamic backup-vs-current regression regenerated the current 15x request
  with the pre-change shared placer backup and the changed shared placer. Both
  emitted an identical 331,776-byte `ROOT.DSN` with SHA-256
  `5f4671cae58ff1f26e6b702e5a3dcfecebb052feb696044248f0e1cb46c6a6aa`.
- 30x (`CAP-ELEC` 21): 531 components, 1,062 terminals/WIREs; normal open and
  cold reopen without a modal error.
- 45x (`CAP-ELEC` 21): 786 components, 1,572 terminals/WIREs; normal open and
  cold reopen without a modal error.
- 58x (`CAP-ELEC` 21): 1,007 components, 2,014 terminals/WIREs; normal open
  and cold reopen without a modal error.
- 60x did not create a project: the locked mega exposes only 58 CDB-backed
  `CSOURCE` packets. Since 58x placed every other requested family too, this
  is the demonstrated uniform native-two-pin mix ceiling for this donor.

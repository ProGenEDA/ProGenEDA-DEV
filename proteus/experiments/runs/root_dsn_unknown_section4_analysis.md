# ROOT.DSN Unknown Section 4 Analysis

This note summarizes the review of the 376-page `E0 -> R1 -> R2 -> R3 -> R4` resistor comparison, the green-removed byte comparison, and the yellow/red relevance map.

## Main answer

Section 4 is relevant, but the small header range `0x00AD-0x00B2` is probably not the direct source of the DLL errors.

Reason: all five valid files have different bytes in that range, yet all five open. That makes the range look like a project/session/hash/pointer-like header field that Proteus tolerates when the rest of the file is internally consistent.

The stronger DLL-error candidate is the larger binary-only region around the object-section boundary:

```text
second ISIS CIRCUIT FILE marker
second OBJECT DATA marker
byte immediately before the second ISIS CIRCUIT FILE marker
uint32 pointer after CCT000
uint32 pointer after __DEFAULT__\0\0
binary placed-object records and nearby registry/table bytes
```

## What was already known and being implemented

- `ROOT.CDB` stores component inventory, refs, values, type, and primitive metadata.
- `ROOT.DSN` stores visible schematic, topology, object records, terminal labels, and wire records.
- Missing `ROOT.CDB` is unsafe.
- Whole `ROOT.DSN` replacement is safe.
- Minimal CDB can work with a complete donor `ROOT.DSN`.
- At least one section pointer must be patched when `ROOT.DSN` body size changes.

## What is new from this review

The generated resistor-count pack had a concrete pointer bug.

Example from generated 5R:

```text
second ISIS CIRCUIT FILE offset = 66438
pointer after __DEFAULT__\0\0 = 68860
```

`68860` is the 12R second-section offset, not the 5R second-section offset.

So the pack was not truly pointer-fixed per generated file.

Also in generated 5R/6R, the byte immediately before the second `ISIS CIRCUIT FILE` marker was `00`; in valid-style files it should be `FF`.

## Updated interpretation of Section 4 unknowns

| Area | Likely role | DLL risk |
|---|---|---|
| `0x00AD-0x00B2` | Unknown header/session/check-like field | Low direct risk because valid files differ there |
| `0xFAB8 / 64168 onward` | Main resistor device/object region | High |
| byte before second `ISIS CIRCUIT FILE` | section terminator/boundary byte | High |
| pointer after `CCT000` | pointer to first circuit section | High |
| pointer after `__DEFAULT__\0\0` | pointer to second circuit section | Very high |
| dense binary in placed records | object IDs, coordinates, handles, registry fields | High but still uncharted |

## What should now be implemented

- Recompute every pointer to both `ISIS CIRCUIT FILE` markers, not only one pointer.
- Verify the byte immediately before the second `ISIS CIRCUIT FILE` marker.
- Add a pointer-map validator before every generated `.pdsprj` is given to the user.
- Scan all 4-byte little-endian values that point inside `ROOT.DSN`; flag stale or out-of-range values.
- Keep CDB component count consistent with the intended component count.
- Stop calling object-record copying true generation until pointer-map and boundary validation pass.

## New diagnostic pack created locally

```text
TRUE_GENERATED_RCOUNT_SECOND_POINTER_FIX_PACK.zip
```

This pack patches, for each generated 5R-12R file:

1. byte before the second `ISIS CIRCUIT FILE` -> `FF`
2. uint32 after `__DEFAULT__\0\0` -> actual second `ISIS CIRCUIT FILE` offset

This tests whether the 5R-11R failures were caused by the stale 12R pointer copied into every generated count file.

## Still uncharted territory

Even after fixing these pointers, arbitrary generation may still fail because a separate object registry/table may exist. The most suspicious remaining area is not readable text; it is the dense binary around placed object records and the table/boundary area surrounding the second `OBJECT DATA` marker.

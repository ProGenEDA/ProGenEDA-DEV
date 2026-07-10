# Three-pin BJT component-stream 1x V35

Test only the four files under `01_test_these_bjt_sa`:

1. `T001_NPN_1x_COMPONENT_STREAM_sa`
2. `T002_PNP_1x_COMPONENT_STREAM_sa`
3. `T003_2N3904_1x_COMPONENT_STREAM_sa`
4. `T004_2N4401_1x_COMPONENT_STREAM_sa`

V34 failed before rendering with a Proteus “Device ... used but not in library”
message containing a garbage device name. Its no-terminal controls started with
the locked-mega component-stream prefix `00 00 FF`, but V34 terminalized files
started `00 10 ...` because terminal records were emitted before the component.
Proteus therefore parsed terminal bytes as a device identifier.

V35 preserves the complete component-placer stream first. Its first three bytes
remain `00 00 FF`, and the first terminal record begins exactly at the byte that
was the no-terminal control's final stream terminator. The active BJT WIRE units
remain zero-length exactly on the grid-aligned pins, as proved by accepted
NPN/PNP donor evidence.

All cases were produced by the locked mega-donor component placer, beautifier,
and the one shared `src/proteusgen/component_terminal_placer.py`. Terminalized
donors were evidence only.

Static audit: 4/4 outputs preserve `00 00 FF`, component precedes terminals and
WIREs, attachment boundary equals `len(no-terminal-control)-1`, one component,
three active terminals, three active on-pin WIRE units, single final `FF`, and
valid final-address links. Proteus open/render acceptance is required before
scaling.

# NPN component-stream double-FF 1x V36

Test only:

`01_test_this_one/T001_NPN_1x_COMPONENT_STREAM_DOUBLE_FF_sa.pdsprj`

V35 fixed the earlier garbage-device framing error by restoring the locked-mega
`00 00 FF` component prefix, but all four BJT files then failed with an
`lxlcore.dll` error. The remaining shared frame mismatch was the finalizer:
V35 ended with one `FF`, copied from the standalone NPN/PNP donor, while the
user-accepted locked-mega component-first NMOSFET and catalogue routes end
`FF FF`.

V36 changes only NPN and only the finalizer. It preserves:

- locked-mega component placement and `00 00 FF` prefix;
- component stream before terminal/WIRE units;
- first attachment at `len(no-terminal-control)-1`;
- three donor-proven on-pin active zero-length WIRE units;
- final-address terminal/component link allocation.

The output now ends `FF FF`. PNP, 2N3904, and 2N4401 were deliberately not
regenerated. If this single file passes Proteus, apply the same locked-mega
finalizer to those three and regenerate their 1x files.

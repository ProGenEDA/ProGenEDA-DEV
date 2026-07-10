# NPN complete frame-contract 1x V38

V37 failed and is rejected. Test only:

`01_test_this_one/T001_NPN_1x_FRAME_CONTRACT/T001_NPN_1x_FRAME_CONTRACT_sa.pdsprj`

This is not the NPN donor copied back. The component is placed from the locked
`new_components_5x_mega.pdsprj`, and only the unified shared terminal placer
edits its `ROOT.DSN`.

The actual accepted NPN `.pdsprj` is the authoritative source for terminal
templates, relative pin geometry, pin sides, zero-length WIRE records, WIRE
schema, pin-link offsets, and labels. The actual accepted component-first
NMOSFET `.pdsprj` supplies the locked-mega frame contract: component-first
terminal/WIRE units, `02 00` active links, and `FF FF` finalization.

V38 is the first BJT candidate combining the entire contract. V36 had the
correct pairing/finalizer but retained the standalone donor's frame-specific
`01 00` links. V37 retained `01 00` and introduced an unproven grouped hybrid.

See `donor_contract_audit.json` for the complete member, CDB, DSN frame,
terminal template, WIRE template, order, pointer, address-link, and known-
difference audit. No unexplained static structural differences remain, but
only Proteus open/render testing can accept the candidate.

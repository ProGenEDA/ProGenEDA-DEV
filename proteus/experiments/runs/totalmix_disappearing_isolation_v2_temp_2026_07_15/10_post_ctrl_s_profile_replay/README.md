# I18 post-Ctrl+S profile replay

Scope: the 38-family compact mixed baseline that excludes the still-isolated
logic/display families. This is a newly placed project from the locked mega
donor, then terminalized by the shared
`src/proteusgen/component_terminal_placer.py`; it is not a donor transplant.

## Inputs and evidence

- Bare placement: `I18_POST_CTRL_S_PROFILE_BARE_1X.pdsprj`
- Terminalized replay: `I18_POST_CTRL_S_PROFILE_TERMINALIZED_1X_sa.pdsprj`
- Authoritative user Ctrl+S control: `../01_compact_74hc76_free_baseline/I15_COMPACT_74HC76_FREE_SAFE_TERMINALIZED_1X_sa.pdsprj`
- Full byte analysis: `knowledge/i15_ctrl_s_totalmix_wire_normalization_audit_2026_07_15.md`

The replay has 38 placed packets, 178 active `$TERBIDIR` records, and 178
active `WIRE` records. Its final `ROOT.DSN` object chunk is byte-identical to
the user Ctrl+S control:

`0f14cc93511ceb0cf69315b64cbacf65e3bf8bdfaf2f2acec57dda4e9b6cdb53`

That comparison includes the corrected CAP order, the 14 MOSFET/BJT path
normalizations, final-address link rebasing, and the final `FF FF` terminator.

## Local Proteus gate — 2026-07-15

`11_local_proteus_gate/I18_POST_CTRL_S_PROFILE_TERMINALIZED_1X_GATE_COPY.pdsprj`
opened normally after 15 seconds and then cold-reopened after another 15
seconds. No Bad Object Record, Fatal Error, LXLCORE, or device-library dialog
appeared; the disposable-copy SHA-256 remained unchanged. No Ctrl+S was used.

The normal-open and cold-reopen screenshots are retained under
`../11_local_proteus_gate/`. User visual review remains the acceptance step for
spacing and terminal appearance.

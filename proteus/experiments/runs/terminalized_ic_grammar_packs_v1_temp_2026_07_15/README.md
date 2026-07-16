# Terminalized IC grammar packs (1x)

This is the user-requested manual-combination handoff. Every project was
freshly placed from the locked mega donor and terminalized through
`src/proteusgen/component_terminal_placer.py`; none is a copied terminalized
donor.

The ICs are deliberately split by the donor-proven object-stream grammar and
ROOT.CDB policy. This preserves the accepted solo routes while making each
file independently loader-safe for manual combination.

| Pack | Families | Terminals / WIREs | Delayed normal + cold Proteus gate |
| --- | --- | ---: | --- |
| `I01_APPEND_TAIL_4511_74HC151_1X` | 4511, 74HC151 | 28 / 28 | pass / pass |
| `I02A_DOUBLE_FF_74HC04_1X` | 74HC04 | 12 / 12 | pass / pass |
| `I02B_SINGLE_FF_QUAD_LOGIC_1X` | 74HC00, 74HC02, 74HC08, 74HC266, 74HC32, 74HC86 | 72 / 72 | pass / pass |
| `I03A_TERMINAL_LEADING_PRESERVE_CDB_1X` | 7447, 74HC157, 74HC160, 74HC174, 74HC192, 74HC283, 74HC85 | 98 / 98 | pass / pass |
| `I03B_TERMINAL_LEADING_NORMALIZED_CDB_7490_1X` | 7490 | 10 / 10 | pass / pass |
| `I04A_SUBPART_PRESERVE_CDB_4027_1X` | 4027 | 14 / 14 | pass / pass |
| `I04B_SUBPART_NORMALIZED_CDB_74HC74_74HC76_1X` | 74HC74, 74HC76 | 26 / 26 | pass / pass |

All listed projects have grid-aligned terminal contacts, terminal-to-pin short
WIREs, active rebased suffix links, no loader modal, and an unchanged
disposable-copy SHA-256 after normal and cold opens.

The matching non-IC circuit is:
`experiments/mixed_current_accepted_1x_v2_temp_2026_07_15/M01_CURRENT_ACCEPTED_30F_1X_TERMINAL_sa.pdsprj`.
It contains 30 fresh non-IC/current-group families, 70 terminal/WIRE pairs,
and previously passed the same normal/cold gate.

The deliberately unpublished attempts `I02_SINGLE_TAIL_74HC04_QUAD_LOGIC_1X`
and `I03_TERMINAL_LEADING_COUNTER_LOGIC_1X` have only no-terminal controls:
their mixed finalizer/CDB-policy combinations were rejected before a terminal
project was written. They are not handoff candidates.

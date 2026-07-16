# 74HC74 catalogue terminal evidence

This pack is generated from the locked `new_components_5x_mega.pdsprj` through
the normal component placer and the one shared terminal placer. It does not
copy component or terminal packets from the HC74 donor at runtime.

The authoritative active donor is:

`proteus_ic/donors/terminalized_catalogue_evidence/dil14_dual_d_ff/74HC74/74HC74_terminalized_primary.pdsprj`

Generated terminalized solos:

- 1x: 12 terminal/WIRE pairs
- 9x: 108 terminal/WIRE pairs
- 15x: 180 terminal/WIRE pairs

The shared profile serializes each package as donor-proven A and B attachment
blocks. Its HC74-specific catalogue facts normalize the locked-mega clean
tail's one byte of reserved link padding, retain the component/WIRE boundary,
and preserve the donor WIRE separators. The component packets themselves
remain those produced by the locked mega component placer.

Local Proteus 8.13 checks reached normal responsive schematic windows for the
1x cold reopen, 9x, 15x, and 1x boundary mix. Normal opens were not Ctrl+S
saved. The screenshot records are supplemental visual evidence; the actual
project files remain the test artifacts.

The boundary mix intentionally terminalizes only the frozen twenty two-pin
families. It includes 74HC74 as a bare placed component until an authoritative
combined donor proves a hybrid active stream order.

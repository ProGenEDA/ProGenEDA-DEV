# Value Changer Probe V1

Each generated project uses the real component placer and the new same-length value mutation stage.
Open each 15x project and inspect whether the visible values changed across the components.
The stage also patches matching CDB property rows when the selected row contains the old value token.

VSINE and VPULSE are intentionally blocked for binary value mutation in this pass because their selected packets do not expose a normal visible value token.

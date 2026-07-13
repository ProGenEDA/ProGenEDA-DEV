# DIL16 counter terminal evidence

This Proteus-only experiment is for `74HC160` and `74HC192`. It uses the
locked mega component placer and the existing shared terminal placer; it does
not introduce a family-specific terminal script.

`00_preflight_controls/` contains fresh 1x component-placer controls generated
from the locked mega. `knowledge/dil16_counter_donor_preflight_2026_07_14.md`
records the complete terminalized donor audit and the expected control-to-donor
deltas.

Status: preflight complete. The historic terminal donors have zero-length
WIREs, so they are grammar/geometry/link evidence only. No active terminalized
candidate is claimed until the shared placer produces nonzero grid-contact-to-
exact-pin WIREs and passes all three local loader stages.

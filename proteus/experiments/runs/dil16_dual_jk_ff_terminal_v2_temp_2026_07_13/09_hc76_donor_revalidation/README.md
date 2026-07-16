# 74HC76 1x donor revalidation

`S03_74HC76_1X_NO_TERMINAL.pdsprj` is the locked-mega
component-placer control. `S03_74HC76_1X_CATALOGUE_TERMINAL_sa.pdsprj`
is emitted by the existing shared terminal placer using the donor's
asymmetric multipart stream:

`12 terminal records -> A -> 7 WIREs -> 2 terminal records -> B -> 7 WIREs -> FF`

Actual DSN checks found fourteen terminal records, fourteen active equal-endpoint
grid WIREs, unique active suffixes, and both physical U41 halves. The candidate
opened and foregrounded cold-reopened in Proteus with no dialog:

- `G16_74HC76_1X_BEFORE_CLOSE.png`;
- `G17_74HC76_1X_COLD_REOPEN_BEFORE_CLOSE.png`.

Normal opens were not Ctrl+S-saved.

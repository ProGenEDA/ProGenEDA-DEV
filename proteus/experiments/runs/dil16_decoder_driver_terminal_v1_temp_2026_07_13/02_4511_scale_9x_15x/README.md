# 4511 9x and 15x scale evidence

Both scales are fresh outputs from the locked component-placement mega and the
same shared catalogue terminal placer used for the accepted 4511 1x route.
There is no component-specific terminal script and no donor-packet transplant.

| Output | Components | Active terminal/WIRE pairs | Local Proteus gate |
| --- | ---: | ---: | --- |
| `S02_4511_9X_CATALOGUE_TERMINAL_sa.pdsprj` | 9 | 126 | normal cold open and cold reopen; no save |
| `S03_4511_15X_CATALOGUE_TERMINAL_sa.pdsprj` | 15 | 210 | normal cold open and cold reopen; no save |

The paired `NO_TERMINAL` projects are the component-placer controls. Static
audits confirm grid terminal contacts, nonzero terminal-to-exact-pin WIREs,
unique final-address link suffixes, explicit stream finalizers, and unchanged
`ROOT.CDB` from each control.

No Bad Object Record appeared. The normal disposable-copy SHA-256 values stayed
identical to the generated active outputs: 9x
`05B32E9F52C3E5A324EE463B68547F2A84BF0D9F04561484771B4295CD40CCEC`; 15x
`2D0E205943685F017BE11DD13D1A5BFA9C4CA1485BA08ACADDF6918828776A91`.

The `local_proteus_gate/` screenshots are captured before each close. The two
15x captures visibly show repeated 4511s with their attached terminal stubs.

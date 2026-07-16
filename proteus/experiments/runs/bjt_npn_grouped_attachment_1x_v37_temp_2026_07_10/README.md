# NPN grouped attachment 1x V37

Test only:

`01_test_this_one/T001_NPN_1x_GROUPED_ATTACHMENT/T001_NPN_1x_GROUPED_ATTACHMENT_sa.pdsprj`

The matching no-terminal component-placer control is under
`00_no_terminal_control/`.

V37 fixes the structural mistake found by comparing the complete accepted NPN
donor contract. The locked-mega component packet remains first, but attachments
are no longer interleaved. The emitted object order is:

`component -> COLLECTOR terminal -> EMITTER terminal -> BASE terminal -> BASE WIRE -> COLLECTOR WIRE -> EMITTER WIRE`

Placement comes only from
`new_components_5x_mega.pdsprj`. The terminalized NPN donor is comparison
evidence only. The generated file contains one component, three active
grid-aligned terminals, three donor-proven on-pin WIRE units, valid final
ROOT.DSN address links, the locked-mega `00 00 FF` prefix, and an explicit
`FF FF` finalizer.

Proteus open/render acceptance is pending. Do not scale NPN or change PNP and
the NPN aliases until this one file is accepted.

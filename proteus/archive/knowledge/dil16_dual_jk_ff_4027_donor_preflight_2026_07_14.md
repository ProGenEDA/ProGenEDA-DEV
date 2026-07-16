# 4027 dual-JK fresh terminal preflight — 2026-07-14

## Authority and scope

This is Proteus-only work. The authoritative terminalized donor is
`proteus_ic/donors/terminalized_catalogue_evidence/dil16_dual_jk_ff/4027/4027_terminalized_primary.pdsprj`.
The only component-placement donor is
`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`.
The terminal implementation remains the shared
`src/proteusgen/component_terminal_placer.py`; no family-specific terminal
script or alternate workflow was added.

The user-provided recovered project
`experiments/dil16_dual_jk_ff_terminal_v2_temp_2026_07_13/01_solo_1x/S02_4027_1X/fixS02_4027_1X_CATALOGUE_TERMINAL_sa.pdsprj`
is useful negative evidence only. Its ROOT.DSN object chunk has one `U13:A`
half, seven terminal records, zero WIREs, and no B half: it is Proteus’s
post-recovery prefix, not a complete terminal donor and must not be copied or
used as a generation template.

## Complete donor and current-packet comparison

The actual donor’s ROOT.DSN chunk is 3,018 bytes with one final `FF`, fourteen
`$TERBIDIR` records, fourteen `7fWIRE` records, and two physical packets:

`7 terminals -> U1:A -> 7 WIREs -> 7 terminals -> U1:B -> 7 WIREs -> FF`.

Every accepted 4027 WIRE has equal start/end coordinates at an exact grid
intersection. This is a frozen native attachment exception, not an inactive
or label-only fallback: every terminal still has its matching active component
pin-link suffix and adjacent donor-ordered WIRE record.

The fresh locked-mega placer selects complete physical package `U13:A/B` for
1x. Its final shared-placer output is 3,020 bytes, exactly two bytes longer
than the donor because `U13:A/B` is one byte wider than `U1:A/B` for each
subpart. It retains the true reference width and removes only the one
donor-proven reserved zero before each active 28-byte link table. Its first
A/B WIRE marker positions are therefore `1160` and `2669`, versus the donor’s
`1159` and `2667`; final link suffixes are rebased from those final addresses.

## Loader diagnostic and final route

All native contacts are already on the Proteus grid. Consequently the shared
`native_pin_contact` and `grid_contact` diagnostics are byte-identical
(`FEEF41D36C637420AFBF490B379B4717E68DF8199C5EA000AB5764A822DEECB3`).
They contain terminal records without their required active links/WIREs and
both show the captured `VGDVC.DLL [000190DA]` fatal. They are rejected
diagnostics, not a terminal-placement repair target.

The fresh locked-mega no-terminal control, the authoritative donor, and the
complete active output all normal-opened unchanged after the 12-second
stability wait. The complete active route also cold-reopened normally at 1x,
9x, and 15x. Normal-opening disposable copies were not Ctrl+S-saved.

| Scale | Whole A/B packages | Terminal/WIRE units | Active loader result |
| ---: | ---: | ---: | --- |
| 1x | 1 | 14 | normal open and cold reopen |
| 9x | 9 | 126 | normal open and cold reopen |
| 15x | 15 | 210 | normal open and cold reopen |

The complete 15x package keys are `U13`, `U14`, `U15`, `U154`, `U155`,
`U156`, `U295`, `U296`, `U297`, `U436`, `U437`, `U438`, `U577`, `U578`, and
`U579`; intentionally split donor controls are never selected.

## Decision

Keep this exact catalogue-driven native zero-length attachment route frozen.
Do not attempt an unproven outward/nonzero WIRE rewrite merely to make this
family resemble another family: earlier 4027 short-wire attempts produced Bad
Object Record recovery, while the accepted donor and this full active route
open normally. User visual validation remains required; mixed terminal
emission remains deferred until every group has solo 1x/9x/15x evidence.

# New-component mega locked support evidence - 2026-07-08

This folder is the curated evidence set for the temporary stability rule:

`proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj`

is the only placement donor allowed by `src/proteusgen/component_placer.py`
during this recovery pass. Terminalized projects in this folder are evidence
for pin geometry and terminal naming; generated outputs must still start from
the locked placement donor and pass through the shared pipeline.

## Folder groups

- `00_locked_placement_donor/` - copied locked placement donor for easy opening.
- `01_two_pin_diode_zener_led_fuse/` - accepted two-pin diode-style terminal evidence.
- `02_two_pin_passive_source/` - accepted two-pin passive/source terminal evidence.
- `03_three_pin_transistor/` - transistor evidence; part-number aliases reuse the base symbol evidence.
- `04_three_pin_regulator_control_symbol/` - LM317T, OPAMP, POT-HG evidence.
- `05_four_pin_rectifier_transformer/` - BRIDGE and TRAN-2P2S evidence.
- `06_dil14_logic/` - DIL14 logic evidence.
- `07_dil16_logic/` - DIL16 logic/counter/decoder/mux/register evidence.
- `08_dil8_analog/` - LM741 and NE555 evidence.
- `09_display_terminal_evidence_placement_blocked_by_lock/` - display terminal evidence; folder name records the earlier blocked state before same-donor finalization was added.
- `10_missing_or_unverified_terminal_evidence/` - candidate files that are not terminal acceptance evidence yet.

## Strict-lock placement status

Static donor scan of the locked donor shows enough packets for 20x scaling for
most listed families. Most IC families have exactly 20 usable marker groups, so
20x is the maximum target for those families under this donor.

`CAP-ELEC` needs finalizable packet filtering inside the component placer; the
locked donor contains early non-finalizable CAP-ELEC packets and later
finalizable packets. The placer now skips the non-finalizable CAP-ELEC records.

The display families have terminalized evidence here. The locked donor contains
display rows and the D20 bridge, but no display row is donor-final. The
component placer now keeps the lock by finalizing the last selected display row
from this same donor instead of falling back to another mega donor. These
display outputs still need Proteus open/render testing before terminal work.

`SWITCH` is placeable from the locked donor, but this folder currently contains
only an unverified candidate control-component donor, not accepted terminal
evidence.

## Supported list normalized for this pass

Bracketed Proteus device-list aliases such as `[74HC00]` are treated as the
same family as `74HC00`.

- Two-pin diode/zener/LED/fuse: `1N4007`, `1N4148`, `1N4733A`, `1N6000B`,
  `40EPS08`, `BZX55C5V1`, `BZX79C5V1`, `BZY88C`, `DIODE`, `FUSE`, `LED-RED`.
- Two-pin passive/source: `CAP`, `CAP-ELEC`, `CSOURCE`, `REALIND`,
  `RESISTOR`, `VPULSE`, `VSINE`, `VSOURCE`.
- Three-pin transistor aliases: `NPN`, `PNP`, `NMOSFET`, `2N3904`, `2N4401`,
  `2N7000`, `BS170`.
- Three-pin/control symbols: `LM317T`, `OPAMP`, `POT-HG`.
- Four-pin symbols: `BRIDGE`, `TRAN-2P2S`.
- DIL14 logic: `74HC00`, `74HC02`, `74HC04`, `74HC08`, `74HC32`, `74HC74`,
  `74HC76`, `74HC86`, `74HC266`.
- DIL16 logic: `4027`, `4511`, `7447`, `7490`, `74HC85`, `74HC151`,
  `74HC157`, `74HC160`, `74HC174`, `74HC192`, `74HC283`.
- DIL8 analog: `LM741`, `NE555`.
- Displays: `7SEG-COM-AN-BLUE`, `7SEG-COM-CAT-BLUE`.
- Control pending terminal evidence: `SWITCH`.

## Target order

1. Prove the locked donor baseline: 1x component-placer output for every
   supported family, including displays through same-donor display-row
   finalization.
2. Re-run the already accepted two-pin families through full pipeline:
   JSON -> component placer -> beautifier -> shared terminal placer. Start with
   1x solo, then scale solo packs to 3x, 9x, 15x, and 20x where donor counts
   allow. Then generate mixed two-pin packs.
3. Work three-pin and four-pin discrete groups next: transistor aliases,
   LM317T/OPAMP/POT-HG, BRIDGE, TRAN-2P2S. For each group, prove 1x solo first,
   then re-run all previously accepted families in that group before scaling.
4. Work DIL14 logic by shared pin-structure group: quad gates first, then
   `74HC04`, `74HC74`, and `74HC76`.
5. Work DIL16 logic by shared pin-structure group. Put `74HC151` early because
   its prior terminal placement had known geometry issues.
6. Work DIL8 analog (`LM741`, `NE555`).
7. Solve `SWITCH` terminal evidence or create a Proteus-accepted terminalized
   donor from the locked placement donor.
8. Solve displays separately at the terminal stage: the component placer can
   emit no-terminal display controls from the locked donor, but the terminal
   placer must still ignore D20/display sentinel infrastructure and terminalize
   only real display pins.
9. After every group has accepted 1x solo output, build a 1x all-supported
   mixed pack, then larger mixed packs up to 20x per family where counts allow.

No terminal-placement behavior should be implemented in dated scripts or donor
collection utilities. New behavior belongs in
`src/proteusgen/component_terminal_placer.py` and the catalogue/profile source
of truth.

## 74HC00 locked-donor count note

`74HC00` currently defaults to offset 8 in `new_components_5x_mega` because
earlier Proteus testing recorded offsets 0 and 4 as failing/crashing, while
offsets 8 and 12 opened/simulated. That makes the production default expose 8
safe packages even though 16 complete packages are present in the donor.

The no-terminal diagnostic pack
`experiments/locked_mega_74hc00_offset_probe_no_terminal_temp_2026_07_08/`
generates offset 0/4/8/12 controls. If Proteus accepts offset 0 or 4 now, the
default can be changed and larger `74HC00`/mixed matrix cases regenerated.

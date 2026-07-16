# Complete component donor request

This is the complete donor plan for the component families currently named by
the Progen component placer and IC registries. It is not a claim to cover every
part in the full Proteus library, which contains vendor and device variants not
yet present in Progen's catalog.

Use Proteus 8.13 and create every donor manually in Proteus. Do not generate,
copy, or byte-edit a donor outside Proteus.

## Donor suite definitions

Use these suite codes in the inventories below.

### TP2: two-pin component suite

1. `<FAMILY>_D01_1X_BARE.pdsprj`: one bare component, default horizontal
   orientation.
2. `<FAMILY>_D02_1X_BIDIR_BOTH_PINS.pdsprj`: one component with one
   bidirectional terminal attached to each real pin through the shortest
   Proteus-created wire.
3. `<FAMILY>_D03_4X_BIDIR_BOTH_PINS.pdsprj`: four terminalized components,
   unique references and terminal labels, saved as one project.
4. `<FAMILY>_D04_15X_BIDIR_BOTH_PINS.pdsprj`: fifteen terminalized components,
   unique references and terminal labels, saved as one project.
5. `<FAMILY>_D05_4X_BIDIR_WITH_RCL_CONTROLS.pdsprj`: four terminalized target
   components plus one bare resistor, capacitor, and REALIND. This exposes
   mixed-family ordering without making R/C/L part of the target.

### MP4: multi-pin discrete/analog suite

1. `<FAMILY>_D01_1X_BARE.pdsprj`.
2. `<FAMILY>_D02_1X_ALL_PINS_BIDIR.pdsprj`: terminalize every visible
   electrical pin; do not invent hidden pins.
3. `<FAMILY>_D03_4X_ALL_PINS_BIDIR.pdsprj`.
4. `<FAMILY>_D04_4X_ALL_PINS_BIDIR_WITH_RCL_CONTROLS.pdsprj`.

For switches, potentiometers, transistors, regulators, op-amps, timers,
bridges, and transformers, every electrically usable pin must be represented.

### IC4: IC package suite

1. `<FAMILY>_D01_1PKG_BARE_ALL_UNITS.pdsprj`.
2. `<FAMILY>_D02_1PKG_ALL_VISIBLE_PINS_BIDIR.pdsprj`.
3. `<FAMILY>_D03_2PKG_ALL_VISIBLE_PINS_BIDIR.pdsprj`.
4. `<FAMILY>_D04_4PKG_ALL_VISIBLE_PINS_BIDIR.pdsprj`.
5. `<FAMILY>_D05_4PKG_BIDIR_WITH_RCL_CONTROLS.pdsprj`.

Place every unit belonging to the package, such as U1:A through U1:D. Attach
terminals to every visible logic, clock, reset, enable, carry, and power pin.
Keep Proteus-native references such as U1/U2; do not rename packages to A1 or
synthetic references.

### DSP4: display suite

1. One bare display.
2. One display with all segment/common pins terminalized.
3. Four displays with all pins terminalized.
4. Four displays plus the matching decoder IC, with all objects still
   electrically disconnected.

## Non-IC inventory

The first six families are already accepted. Do not recreate them unless a
fresh donor is specifically requested.

| Family | Suite | Current need |
|---|---:|---|
| RESISTOR | accepted | RESISTOR/v3 already passed |
| CAP | accepted | CAP/v2 already passed |
| CAP-ELEC | accepted | CAP-ELEC/v3 already passed |
| REALIND | accepted | REALIND/v2 already passed |
| VSOURCE | accepted | VSOURCE/v4 already passed |
| CSOURCE | accepted | CSOURCE/v4 already passed |
| DIODE | TP2 | required; highest priority |
| 1N4007 | TP2 | required |
| 1N4148 | TP2 | required |
| 1N4733A | TP2 | required |
| 1N6000B | TP2 | required |
| IRDIODE | TP2 | required |
| 40EPS08 | TP2 | required |
| BZX55C5V1 | TP2 | required |
| BZX79C5V1 | TP2 | required |
| BZY88C | TP2 | required |
| LED-RED | TP2 | required; highest priority |
| FUSE | TP2 | required; highest priority |
| VSINE | TP2 | required; highest priority because current evidence lacks general 1x/3x/15x final ordering |
| VPULSE | TP2 | required; highest priority |
| BRIDGE | MP4 | required |
| NPN | MP4 | required |
| PNP | MP4 | required |
| 2N3904 | MP4 | required |
| 2N4401 | MP4 | required |
| NMOSFET | MP4 | required |
| 2N7000 | MP4 | required |
| BS170 | MP4 | required |
| TRAN-2P2S | MP4 | required |
| LM317T | MP4 | required |
| LM741 | MP4 | required |
| OPAMP | MP4 | required |
| NE555 | MP4 | required |
| POT-HG | MP4 | required |
| SWITCH | MP4 | required |
| 7SEG-COM-AN-BLUE / 7SEGCOMA | DSP4 | required |
| 7SEG-COM-CAT-BLUE / 7SEGCOMK | DSP4 | required |

The immediate next two-pin batch is therefore:

`DIODE`, `1N4007`, `1N4148`, `1N4733A`, `1N6000B`, `IRDIODE`,
`40EPS08`, `BZX55C5V1`, `BZX79C5V1`, `BZY88C`, `LED-RED`, `FUSE`,
`VSINE`, and `VPULSE`.

## IC inventory

Every row uses the IC4 suite. Existing repository donors can be audited first,
but a row is not accepted by the shared terminal placer until its pin roles,
record order, suffix progression, multi-package boundary, open/render result,
and simulation result are separately recorded.

### Logic gates

| Family | Notes |
|---|---|
| 74HC00 | quad NAND |
| 74HC02 | quad NOR |
| 74HC04 | hex inverter |
| 74HC08 | quad AND |
| 74HC32 | quad OR |
| 74HC86 | quad XOR |
| 74HC266 | quad XNOR/open-collector family |

### Combinational, decoder, and arithmetic ICs

| Family | Notes |
|---|---|
| 74HC85 | comparator |
| 74HC283 | adder |
| 74HC151 | multiplexer |
| 74HC153 | exact clean family donor currently missing |
| 74HC157 | multiplexer |
| 4511 | seven-segment decoder/driver |
| 7447 / 74HC47 | observed Proteus marker is `7447` |
| 74HC48 | exact clean family donor currently missing |
| 4051 | exact clean family donor currently missing |
| 4008 | exact clean family donor currently missing; do not substitute 74HC283 |
| 4063 | exact clean family donor currently missing; do not substitute 74HC85 |

### Sequential, counter, and register ICs

| Family | Notes |
|---|---|
| 4027 | dual JK flip-flop |
| 4013 | exact clean family donor currently missing |
| 4017 | decade counter |
| 4020 | counter |
| 4518 | dual counter |
| 7490 | observed Proteus counter marker |
| 74HC74 | dual D flip-flop |
| 74HC76 | dual JK flip-flop |
| 74HC160 | counter |
| 74HC161 | counter |
| 74HC163 | counter |
| 74HC165 | parallel-in shift register |
| 74HC174 | register |
| 74HC175 | exact clean family donor currently missing; do not substitute 74HC174 |
| 74HC192 | counter |
| 74HC193 | counter |
| 74HC273 | register |
| 74HC4024 | counter |
| 74HC4040 | counter |
| 74HC4060 | use only the refreshed component family |
| 74HC4520 | counter |
| 74HC595 | serial-in shift register |

## Required construction rules

- Use a fresh project for each donor file.
- Keep the target component at its Proteus default value and orientation.
- Let Proteus allocate all object references and package units.
- Use bidirectional terminals for donor learning, including source and IC pins.
- Give every terminal a unique, short label.
- Use the shortest visible wire segment from terminal contact to the exact pin.
- Keep D01-D04 pure: no unrelated components, probes, generators, or rails.
- Add only the specified bare R/C/L controls in D05.
- Save, close, reopen, render, and run a minimal simulation/netlist check before
  delivering the project.
- Deliver original `.pdsprj` files, not screenshots, exported images, or
  extracted ROOT.DSN/ROOT.CDB files.

## Delivery order

1. Immediate TP2 batch: DIODE variants, LED-RED, FUSE, VSINE, VPULSE.
2. MP4 non-IC batch.
3. Existing IC-family audit and the missing exact-family IC donors.
4. Remaining IC4 suites.
5. DSP4 display suites.

This order unlocks the current shared terminal placer without mixing
unvalidated family behavior.

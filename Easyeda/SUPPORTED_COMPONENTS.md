# Supported EasyEDA Components

## Codex 5.6 Locked Catalogue

Codex 5.6 built this catalogue from exact authorized EasyEDA source records,
then drove every physical family through the 300-circuit qualification corpus.
That is why these are real donor-native symbols/devices/footprints rather than
approximations. The 5.6 delivery made support expandable by audited catalogue
rows and donor evidence instead of scattered component-specific generator code.

All entries resolve to exact source devices at generation time. Values may be
changed per instance; the locked donor footprint remains the catalogue
footprint unless a later audited profile explicitly adds package selection.
There are 59 logical entries: 57 physical donor families and two schematic
terminal families.

## Basic

`R`, `R_POT`, `C`, `CAP_ELEC`, `L`, `DIODE`, `1N4007`, `1N4148`, `LED`,
`SPST_SWITCH`.

## Electrical Engineering Lab and Digital

`NPN`, `PNP`, `NMOS`, `LM7805`, `LM317`, `BRIDGE_RECTIFIER`, `TRANSFORMER`,
`FUSE`, `TERMINAL_BLOCK`, `PIN_HEADER`, `GND`, `VCC`, `LM358`, `NE555`,
`74HC00`, `74HC04`, `74HC08`, `74HC32`, `74HC74`, `74HC595`.

## Embedded

`ESP32_WROOM`, `ESP12F`, `ATMEGA328P`, `STM32F103C8T6`, `CP2102`, `CH340`,
`BME280`, `DS3231`, `W25Q64`, `SSD1306`.

## Communications

`MAX485`, `SN65HVD230`, `SM24CANB`.

## I2C Expansion

`ADS1115`, `AT24C256`, `PCA9685`, `PCF8574`.

## Power and USB

`AP2112K_3V3`, `FERRITE_BEAD`, `PTC_FUSE`, `USBLC6_2SC6`,
`USB_C_RECEPTACLE`.

## PCB Utility

`HEADER_1X2`, `HEADER_1X6`, `HEADER_2X3`, `HEADER_2X5_1P27`,
`MOUNTING_HOLE_NPTH`, `MOUNTING_HOLE_PTH`, `TEST_POINT`.

Common accepted aliases are defined in [catalogue.py](catalogue.py). The
executable command `progen-easyeda catalogue` returns the machine-readable
locked list.

PCB inclusion is decided per circuit, not merely per component name. Every
used pin must map to a source footprint pad and the complete physical board
must pass the bounded router and validator. The hardened PCB limit is 32
physical components; the schematic limit is 80 total input components.

# Supported EasyEDA Components

All entries resolve to exact source devices at generation time. Values may be
changed per instance; the locked donor footprint remains the catalogue
footprint unless a later audited profile explicitly adds package selection.

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

Common accepted aliases are defined in [catalogue.py](catalogue.py). The
executable command `progen-easyeda catalogue` returns the machine-readable
locked list.

PCB inclusion is decided per circuit, not merely per component name. Every
used pin must map to a source footprint pad and the complete physical board
must pass the bounded router and validator.

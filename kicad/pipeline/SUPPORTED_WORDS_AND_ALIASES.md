# Supported Words And Aliases

Generated: 2026-07-10

This document lists the words the KiCad input fixer/placer can understand before generation. The generator still stores canonical normalized kinds in main JSON; these aliases are accepted so loose JSON can be repaired instead of rejected for small naming differences.

## Canonical Rule

- Preferred component field: `kind`.
- Accepted fallback fields: `type`, `name`, catalog aliases, and known reference/pin patterns.
- Kind matching is case-insensitive and punctuation-insensitive: spaces, hyphens, and slashes normalize to `_` where needed.
- If the fixer invents a net or rail, it names it `GUESS_TERMINAL_*` and forces terminal handling.

## Main JSON Shape

Full contract: `kicad/pipeline/MAIN_INPUT_JSON_CONTRACT.md`

Minimal useful shape:

```json
{
  "schema_version": "progen-kicad-circuit-ir/v1",
  "project": {"name": "example", "title": "Example"},
  "routing": {"mode": "combination"},
  "components": [
    {"id": "U1", "ref": "U1", "kind": "ARDUINO_NANO", "value": "Arduino Nano"},
    {"id": "R1", "ref": "R1", "kind": "RESISTOR", "value": "220 ohm"}
  ],
  "nets": {"NET_LED": ["U1.D13", "R1.1"]}
}
```

## Semantic Alias Families

These come from `kicad/pipeline/catelogues/component_catalogue.json` and are used by `input_json_validator_fixer.py` for loose JSON repair, common pin-role inference, and guessed rails.

| Family | Accepted Words | Pin Words |
| --- | --- | --- |
| `74HC595_DIP16` | `74HC595`, `74HC595_SHIFT_REGISTER` | `SER`, `14`, `serial_data_in`, `SHCP`, `11`, `clock`, `shift_clock`, `STCP`, `12`, `latch`, `Q0`, `15`, `parallel_output`, `bus_output`, `Q1`, `1`, `Q2`, `2`, `Q3`, `3`, `Q4`, `4`, `Q5`, `5`, `Q6`, `6`, `Q7`, `7`, `VCC`, `16`, `power`, `GND`, `8`, `ground` |
| `ArduinoNano_Module` | `ARDUINO_NANO` | `5V`, `27`, `power`, `GND`, `29`, `ground`, `D2`, `5`, `gpio`, `D3`, `6`, `pwm`, `D4`, `7`, `D5`, `8`, `D6`, `9`, `D13`, `16`, `clock`, `SDA`, `23`, `i2c`, `SCL`, `24` |
| `Capacitor_Electrolytic` | `CAP_ELEC`, `CAP-ELEC`, `CP_100UF`, `OUTPUT_CAPACITOR_BUCK`, `INPUT_CAPACITOR_BUCK` | `POS`, `1`, `positive`, `passive`, `NEG`, `2`, `negative` |
| `Capacitor_Generic` | `C`, `CAP`, `CAPACITOR`, `C_100NF_CERAMIC`, `DECOUPLING_CAPACITOR`, `C_100NF_FLASH`, `RESET_CAPACITOR`, `INPUT_CAPACITOR`, `OUTPUT_FILTER_CAPACITOR`, `C_22PF_X1`, `C_22PF_X2` | `1`, `passive`, `2` |
| `Connector_Generic` | `TERMINAL`, `TERMINAL_BLOCK`, `SCREW_TERMINAL_2`, `PIN_HEADER`, `HEADER_CONNECTOR`, `UART_HEADER`, `I2C_HEADER`, `PWM_HEADER`, `JST_CONNECTOR`, `CAN_TERMINAL`, `RS485_TERMINAL` | `1`, `connector`, `2`, `3`, `4` |
| `Diode_Axial` | `D`, `DIODE`, `1N4007`, `D_1N4007`, `1N4148`, `1N60`, `BZX55C5`, `BZX79C5`, `FLYBACK_DIODE`, `RELAY_FLYBACK_DIODE`, `SCHOTTKY_DIODE_BUCK`, `TVS_DIODE_RS485` | `A`, `1`, `anode`, `K`, `2`, `cathode` |
| `ESP32_WROOM_Module` | `ESP32_WROOM` | `3V3`, `2`, `power`, `GND`, `1`, `ground`, `EN`, `3`, `enable`, `IO0`, `25`, `boot`, `TXD0`, `35`, `uart`, `RXD0`, `34` |
| `GND_Symbol` | `GND`, `GROUND`, `GND_SYMBOL` | `1`, `ground` |
| `LED_Generic` | `LED`, `LED_INDICATOR`, `RELAY_INDICATOR_LED`, `CHARGING_LED`, `POWER_LED` | `A`, `1`, `anode`, `load_input`, `K`, `2`, `cathode`, `load_return` |
| `LM358_DualOpAmp` | `LM358`, `OPAMP` | `IN_PLUS`, `3`, `analog_input`, `IN_MINUS`, `2`, `feedback`, `OUT`, `1`, `analog_output`, `VCC`, `8`, `power`, `GND`, `4`, `ground` |
| `MAX485_SO8` | `MAX485` | `RO`, `1`, `uart_rx`, `RE`, `2`, `enable`, `DE`, `3`, `DI`, `4`, `uart_tx`, `A`, `6`, `differential_bus`, `B`, `7`, `VCC`, `8`, `power`, `GND`, `5`, `ground` |
| `NMOS_3Pin` | `NMOS`, `MOSFET`, `2N7000`, `BS170`, `IRLZ44N` | `G`, `1`, `gate`, `control`, `D`, `2`, `drain`, `load`, `S`, `3`, `source`, `return` |
| `NPN_3Pin` | `NPN`, `BC547` | `B`, `1`, `base`, `control`, `C`, `2`, `collector`, `load`, `E`, `3`, `emitter`, `return` |
| `Power_Symbol` | `VCC`, `VCC_SYMBOL`, `PWR_5V`, `PWR_3V3`, `+5V`, `+3V3` | `1`, `power` |
| `Regulator_3Pin` | `LM7805`, `LM317` | `IN`, `1`, `power_input`, `GND`, `2`, `ground`, `OUT`, `3`, `power_output` |
| `Resistor_Axial` | `R`, `RES`, `RESISTOR`, `R_220`, `R_10K_PULLUP`, `R_4K7_PULLUP`, `R_120_CAN`, `R_120_RS485`, `FEEDBACK_RESISTOR`, `SDA_PULLUP`, `SCL_PULLUP` | `1`, `passive`, `2` |
| `VSource_DC` | `VDC`, `VSOURCE`, `VSIN`, `VPULSE`, `CSOURCE` | `1`, `positive`, `source`, `2`, `negative`, `return` |
| `W25Q64_SOIC8` | `W25Q64` | `CS`, `1`, `chip_select`, `DO`, `2`, `spi`, `DI`, `5`, `SCK`, `6`, `clock`, `VCC`, `8`, `power`, `GND`, `4`, `ground` |

## Placement Kind Words

These are the canonical normalized kinds accepted by the component placer. Values like `220 ohm`, `10k`, `100nF`, etc. belong in `components[].value`; they do not require separate component kinds.

Total placement kinds: 163

| Kind | Display Name | Category | KiCad Symbol |
| --- | --- | --- | --- |
| `1N4007` | 1N4007 Diode | diode | `Diode:1N4007` |
| `1N4148` | 1N4148 Diode | diode | `Diode:1N4148` |
| `1N60` | 1N60 Diode | diode | `Device:D` |
| `2N7000` | 2N7000 NMOS | mosfet | `Transistor_FET:2N7000` |
| `4027` | 4027 Dual JK Flip-Flop | logic_ic | `4xxx:4027` |
| `4511` | 4511 BCD to 7-Segment Latch/Decoder | logic_ic | `4xxx_IEEE:4511` |
| `7447` | 7447 BCD to 7-Segment Decoder | logic_ic | `74xx_IEEE:7447` |
| `7490` | 7490 Decade Counter | logic_ic | `74xx_IEEE:7490` |
| `74HC00` | 74HC00 Quad NAND Gate | logic_ic | `74xx:74HC00` |
| `74HC02` | 74HC02 Quad NOR Gate | logic_ic | `74xx:74HC02` |
| `74HC04` | 74HC04 Hex Inverter | logic_ic | `74xx:74HC04` |
| `74HC08` | 74HC08 Quad AND Gate | logic_ic | `74xx:74LS08` |
| `74HC151` | 74HC151 8-Input Multiplexer | logic_ic | `74xx:74LS151` |
| `74HC157` | 74HC157 Quad 2-Input Multiplexer | logic_ic | `74xx:74LS157` |
| `74HC160` | 74HC160 Counter | logic_ic | `74xx:74LS160` |
| `74HC174` | 74HC174 Hex D Flip-Flop | logic_ic | `74xx:74LS174` |
| `74HC192` | 74HC192 Up/Down Counter | logic_ic | `74xx:74HC192` |
| `74HC266` | 74HC266 Quad XNOR Gate | logic_ic | `4xxx:4077` |
| `74HC283` | 74HC283 4-Bit Adder | logic_ic | `74xx:74LS283` |
| `74HC32` | 74HC32 Quad OR Gate | logic_ic | `74xx:74LS32` |
| `74HC595_SHIFT_REGISTER` | 74HC595 Shift Register | logic_ic | `74xx:74HC595` |
| `74HC74` | 74HC74 Dual D Flip-Flop | logic_ic | `74xx:74HC74` |
| `74HC76` | 74HC76 Dual JK Flip-Flop | logic_ic | `74xx:74LS76` |
| `74HC85` | 74HC85 4-Bit Comparator | logic_ic | `74xx:74HC85` |
| `74HC86` | 74HC86 Quad XOR Gate | logic_ic | `74xx:74HC86` |
| `7SEGCOMA` | 7-Segment Common Anode | display | `Display_Character:KCSA02-107` |
| `7SEGCOMK` | 7-Segment Common Cathode | display | `Display_Character:KCSC02-107` |
| `ACS712` | ACS712 Current Sensor | sensor | `Sensor_Current:ACS712xLCTR-20A` |
| `ARDUINO_NANO` | Arduino Nano | microcontroller_module | `MCU_Module:Arduino_Nano_v3.x` |
| `AUDIO_INPUT_JACK` | Audio Input Jack | connector | `Connector_Audio:AudioJack3` |
| `AUDIO_JACK` | Audio Jack | connector | `Connector_Audio:AudioJack3` |
| `BC547` | BC547 NPN Transistor | bjt | `Transistor_BJT:BC547` |
| `BME280` | BME280 Sensor | sensor | `Sensor:BME280` |
| `BOOT_PUSH_BUTTON` | BOOT Push Button | switch | `Switch:SW_Push` |
| `BRIDGE_RECTIFIER` | Bridge Rectifier | diode_bridge | `Device:D_Bridge_+-AA` |
| `BS170` | BS170 NMOS | mosfet | `Transistor_FET:BS170` |
| `BZX55C5` | BZX55C5 Zener Diode | zener_diode | `Device:D_Zener` |
| `BZX79C5` | BZX79C5 Zener Diode | zener_diode | `Device:D_Zener` |
| `CAN_TERMINAL` | CAN Terminal | terminal | `Connector:Screw_Terminal_01x03` |
| `CAP` | Capacitor | capacitor | `Device:C` |
| `CAPACITOR` | Capacitor | capacitor | `Device:C` |
| `CAP_ELEC` | Electrolytic Capacitor | capacitor | `Device:C_Polarized` |
| `CARD_DETECT_SWITCH` | Card Detect Switch | switch | `Switch:SW_SPST` |
| `CD4007` | CD4007 CMOS Array | logic_ic | `Transistor_FET:Q_Dual_NMOS_PMOS_G1S2G2D2S1D1` |
| `CH340` | CH340 USB-UART | interface_ic | `Interface_USB:CH340G` |
| `CHARGING_LED` | Charging LED | indicator | `Device:LED` |
| `CHIP_SELECT_JUMPER` | Chip Select Jumper | jumper | `Jumper:Jumper_2_Open` |
| `COIN_CELL_HOLDER` | Coin Cell Holder | battery_holder | `Device:Battery_Cell` |
| `CP2102` | CP2102 USB-UART IC | interface_ic | `Interface_USB:CP2102N-Axx-xQFN28` |
| `CP_100UF` | 100uF Electrolytic Capacitor | capacitor | `Device:C_Polarized` |
| `CR2032_BATTERY` | CR2032 Battery | battery | `Device:Battery_Cell` |
| `CRYSTAL_16MHZ` | 16MHz Crystal | crystal | `Device:Crystal` |
| `CRYSTAL_OSCILLATOR_CAN` | Crystal Oscillator | crystal | `Device:Crystal` |
| `CSOURCE` | Current Source | source | `Simulation_SPICE:IDC` |
| `C_100NF_CERAMIC` | 100nF Ceramic Capacitor | capacitor | `Device:C` |
| `C_100NF_FLASH` | 100nF Capacitor | capacitor | `Device:C` |
| `C_22PF_X1` | 22pF Capacitor x1 | capacitor | `Device:C` |
| `C_22PF_X2` | 22pF Capacitor x2 | capacitor | `Device:C` |
| `DC_BARREL_JACK` | DC Barrel Jack | connector | `Connector:Barrel_Jack` |
| `DC_MOTOR` | DC Motor | motor | `Motor:Motor_DC` |
| `DECOUPLING_CAPACITOR` | Decoupling Capacitor | capacitor | `Device:C` |
| `DECOUPLING_CAPACITOR_SD` | Decoupling Capacitor | capacitor | `Device:C` |
| `DIODE` | Diode | diode | `Device:D` |
| `DIP_SWITCH` | DIP Switch | switch | `Switch:SW_DIP_x08` |
| `DS3231` | DS3231 RTC | rtc_ic | `Timer_RTC:DS3231M` |
| `D_1N4007` | 1N4007 Diode | diode | `Diode:1N4007` |
| `EN_PUSH_BUTTON` | EN Push Button | switch | `Switch:SW_Push` |
| `ESP32_WROOM` | ESP32-WROOM Module | wireless_module | `RF_Module:ESP32-WROOM-32` |
| `FEEDBACK_RESISTOR` | Feedback Resistor | resistor | `Device:R` |
| `FLYBACK_DIODE` | Flyback Diode | diode | `Device:D` |
| `FUSE` | Fuse | protection | `Device:Fuse` |
| `GND_SYMBOL` | Ground Symbol | power_symbol | `power:GND` |
| `GROUND` | Ground | power_symbol | `power:GND` |
| `HEADER_CONNECTOR` | Header Connector | header | `Connector_Generic:Conn_01x04` |
| `I2C_HEADER` | I2C Header | header | `Connector_Generic:Conn_01x04` |
| `INPUT_CAPACITOR` | Input Capacitor | capacitor | `Device:C` |
| `INPUT_CAPACITOR_BUCK` | Input Capacitor | capacitor | `Device:C_Polarized` |
| `IRLZ44N` | IRLZ44N MOSFET | mosfet | `Transistor_FET:IRLZ44N` |
| `JST_CONNECTOR` | JST Connector | connector | `Connector_Generic:Conn_01x04` |
| `LED` | LED | indicator | `Device:LED` |
| `LED_ARRAY` | LED Array | indicator | `Connector_Generic:Conn_02x08_Odd_Even` |
| `LED_INDICATOR` | LED | indicator | `Device:LED` |
| `LEVEL_SHIFTER` | Level Shifter | interface_ic | `Logic_LevelTranslator:TXS0108EPW` |
| `LI_ION_BATTERY_CONNECTOR` | Li-Ion Battery Connector | connector | `Connector_Generic:Conn_01x02` |
| `LM2596` | LM2596 | buck_converter | `Regulator_Switching:LM2596S-ADJ` |
| `LM317` | LM317 Adjustable Regulator | regulator | `Regulator_Linear:LM317_TO-220` |
| `LM358` | LM358 Op-Amp | opamp | `Amplifier_Operational:LM358` |
| `LM393_COMPARATOR` | LM393 Comparator | comparator | `Comparator:LM393` |
| `LM741` | LM741 Op-Amp | opamp | `Amplifier_Operational:LM741` |
| `LM7805` | LM7805 Voltage Regulator | regulator | `Regulator_Linear:LM7805_TO220` |
| `MAX485` | MAX485 Transceiver | interface_ic | `Interface_UART:MAX485E` |
| `MCP2515` | MCP2515 CAN Controller | interface_ic | `Interface_CAN_LIN:MCP2515-xSO` |
| `MICRO_SD_SOCKET` | Micro SD Socket | connector | `Connector:Micro_SD_Card_Det1` |
| `MICRO_USB_CONNECTOR` | Micro USB Connector | connector | `Connector:USB_B_Micro` |
| `MOSFET` | MOSFET | mosfet | `Transistor_FET:IRLZ44N` |
| `MOUNTING_HOLE` | Mounting Hole | mechanical | `Mechanical:MountingHole` |
| `NE555` | NE555 Timer | timer_ic | `Timer:NE555P` |
| `NMOS` | NMOS Transistor | mosfet | `Transistor_FET:Q_NMOS_DGS` |
| `NPN` | NPN Transistor | bjt | `Transistor_BJT:Q_NPN_BCE` |
| `OPAMP` | Op-Amp | opamp | `Amplifier_Operational:LM741` |
| `OUTPUT_CAPACITOR_BUCK` | Output Capacitor | capacitor | `Device:C_Polarized` |
| `OUTPUT_FILTER_CAPACITOR` | Output Filter Capacitor | capacitor | `Device:C` |
| `PAM8403` | PAM8403 Amplifier | audio_ic | `Amplifier_Audio:PAM8403D` |
| `PIN_HEADER` | Pin Header | header | `Connector_Generic:Conn_01x08` |
| `PNP` | PNP Transistor | bjt | `Transistor_BJT:Q_PNP_BCE` |
| `POLYFUSE` | Polyfuse Resettable Fuse | protection | `Device:Polyfuse` |
| `POTENTIOMETER` | Potentiometer | potentiometer | `Device:R_Potentiometer` |
| `POT_HG` | Potentiometer | potentiometer | `Device:R_Potentiometer` |
| `POWER_INDUCTOR` | Power Inductor | inductor | `Device:L` |
| `POWER_LED` | Power LED | indicator | `Device:LED` |
| `PROGRAMMING_HEADER` | Programming Header | header | `Connector_Generic:Conn_01x14` |
| `PROTECTION_IC` | Protection IC | protection_ic | `Battery_Management:DW01A` |
| `PULLUP_RESISTOR_OLED` | Pull-up Resistor | resistor | `Device:R` |
| `PUSH_BUTTON` | Push Button | switch | `Switch:SW_Push` |
| `PWM_HEADER` | PWM Header | header | `Connector_Generic:Conn_01x04` |
| `PWR_3V3` | +3V3 Power Symbol | power_symbol | `power:+3V3` |
| `PWR_5V` | +5V Power Symbol | power_symbol | `power:+5V` |
| `REALIND` | Inductor | inductor | `Device:L` |
| `RELAY` | Relay | relay | `Relay:Relay_SPDT` |
| `RELAY_5V` | 5V Relay | relay | `Relay:Relay_SPDT` |
| `RELAY_FLYBACK_DIODE` | Relay Flyback Diode | diode | `Device:D` |
| `RELAY_INDICATOR_LED` | Indicator LED | indicator | `Device:LED` |
| `RES` | Resistor | resistor | `Device:R` |
| `RESET_CAPACITOR` | Reset Capacitor | capacitor | `Device:C` |
| `RESISTOR` | Resistor | resistor | `Device:R` |
| `RESISTOR_NETWORK` | Resistor Network | resistor | `Connector_Generic:Conn_02x08_Odd_Even` |
| `RS485_TERMINAL` | RS485 Terminal | terminal | `Connector:Screw_Terminal_01x03` |
| `RX_HEADER` | RX Header | header | `Connector_Generic:Conn_01x01` |
| `R_10K_PULLUP` | 10k Pull-up Resistor | resistor | `Device:R` |
| `R_120_CAN` | 120 ohm Termination Resistor | resistor | `Device:R` |
| `R_120_RS485` | 120 ohm Termination Resistor | resistor | `Device:R` |
| `R_220` | 220 ohm Resistor | resistor | `Device:R` |
| `R_4K7_PULLUP` | 4.7k Pull-up Resistor | resistor | `Device:R` |
| `SCHOTTKY_DIODE_BUCK` | Schottky Diode | diode | `Device:D_Schottky` |
| `SCL_PULLUP` | SCL Pull-up | resistor | `Device:R` |
| `SCREW_TERMINAL_2` | Screw Terminal 2-pin | terminal | `Connector:Screw_Terminal_01x02` |
| `SDA_PULLUP` | SDA Pull-up | resistor | `Device:R` |
| `SPEAKER` | Speaker | speaker | `Device:Speaker` |
| `SPI_HEADER_FLASH` | SPI Header | header | `Connector_Generic:Conn_01x08` |
| `SPI_HEADER_SD` | SPI Header | header | `Connector_Generic:Conn_02x03_Odd_Even` |
| `SSD1306_OLED` | SSD1306 OLED | display | `Display_Graphic:OLED-128O064D` |
| `SWITCH` | Switch | switch | `Switch:SW_SPST` |
| `TERMINAL` | Terminal | terminal | `Connector_Generic:Conn_01x02` |
| `TERMINAL_BLOCK` | Terminal Block | terminal | `Connector:Screw_Terminal_01x02` |
| `TERMINAL_BLOCK_4` | Terminal Block 4-pin | terminal | `Connector:Screw_Terminal_01x04` |
| `TEST_POINT` | Test Point | testpoint | `Connector:TestPoint` |
| `TJA1050` | TJA1050 CAN Transceiver | interface_ic | `Interface_CAN_LIN:SN65HVD1050D` |
| `TP4056` | TP4056 Charger IC | charger_ic | `Battery_Management:TP4056-42-ESOP8` |
| `TRANSFORMER` | Transformer | transformer | `Device:Transformer_1P_1S` |
| `TRIMMER_POTENTIOMETER` | Trimmer Potentiometer | potentiometer | `Device:R_Potentiometer_Trim` |
| `TVS_DIODE_RS485` | TVS Protection Diode | protection | `Device:D_TVS` |
| `TX_HEADER` | TX Header | header | `Connector_Generic:Conn_01x01` |
| `UART_HEADER` | UART Header | header | `Connector_Generic:Conn_01x05` |
| `USB_CONNECTOR` | USB Connector | connector | `Connector:USB_B_Micro` |
| `USB_CONNECTOR_UART` | USB Connector | connector | `Connector:USB_B_Micro` |
| `USB_C_CONNECTOR` | USB Type-C Connector | connector | `Connector:USB_C_Receptacle_USB2.0_16P` |
| `VCC_SYMBOL` | VCC Power Symbol | power_symbol | `power:VCC` |
| `VDC` | DC Voltage Source | source | `Simulation_SPICE:VDC` |
| `VOLUME_POTENTIOMETER` | Volume Potentiometer | potentiometer | `Device:R_Potentiometer` |
| `VPULSE` | Pulse Voltage Source | source | `Simulation_SPICE:VPULSE` |
| `VSIN` | Sine Voltage Source | source | `Simulation_SPICE:VSIN` |
| `VSOURCE` | Voltage Source | source | `Simulation_SPICE:VDC` |
| `W25Q64` | W25Q64 Flash IC | memory_ic | `Memory_Flash:W25Q32JVSS` |

## Legacy Backend Aliases

These older generator aliases are still recognized by the backend catalog normalization path.

| Loose Word | Canonical Backend Kind | Backend Symbol |
| --- | --- | --- |
| `CAP` | `C` | `Device:C` |
| `CAPACITOR` | `C` | `Device:C` |
| `DCV` | `VDC` | `Simulation_SPICE:VDC` |
| `ELECTROLYTIC` | `CP` | `Device:CP` |
| `GROUND` | `GND` | `power:GND` |
| `INDUCTOR` | `L` | `Device:L` |
| `MOS_N` | `NMOS` | `Device:Q_NMOS_GDS` |
| `MOS_P` | `PMOS` | `Device:Q_PMOS_GDS` |
| `PULSE` | `VPULSE` | `Simulation_SPICE:VPULSE` |
| `Q_NPN` | `NPN` | `Device:Q_NPN_BCE` |
| `Q_PNP` | `PNP` | `Device:Q_PNP_BCE` |
| `RESISTOR` | `R` | `Device:R` |
| `SINE` | `VSIN` | `Simulation_SPICE:VSIN` |

## Repair Behavior Summary

- Slightly different JSON field names are normalized into the main contract.
- Loose component names are normalized through semantic aliases and placement kinds.
- Missing component records referenced by nets can be created when the reference/pin pattern is clear.
- Dict endpoints such as `{ "ref": "U1", "pin": "D13" }` are converted to `U1.D13`.
- Duplicate endpoints are merged safely.
- Singleton nets are removed because they are not real connectivity.
- Guessed power/ground/rail nets are named `GUESS_TERMINAL_*` and forced into terminal routing.
- Conflicting explicit nets on the same physical pin are reported rather than guessed away.

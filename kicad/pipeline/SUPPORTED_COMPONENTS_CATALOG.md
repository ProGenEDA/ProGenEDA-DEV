# Supported KiCad Component Catalogue

Generated: 2026-07-10

This file is generated from `kicad/pipeline/placement_catalog.py`. It lists the normalized component kinds that the current placer can resolve without asking the main JSON for extra symbol details.

Total supported normalized kinds: 163

| # | Kind | Display Name | Category | Reference Prefix | KiCad Symbol |
| ---: | --- | --- | --- | --- | --- |
| 1 | `1N4007` | 1N4007 Diode | diode | `D` | `Diode:1N4007` |
| 2 | `1N4148` | 1N4148 Diode | diode | `D` | `Diode:1N4148` |
| 3 | `1N60` | 1N60 Diode | diode | `D` | `Device:D` |
| 4 | `2N7000` | 2N7000 NMOS | mosfet | `Q` | `Transistor_FET:2N7000` |
| 5 | `4027` | 4027 Dual JK Flip-Flop | logic_ic | `U` | `4xxx:4027` |
| 6 | `4511` | 4511 BCD to 7-Segment Latch/Decoder | logic_ic | `U` | `4xxx_IEEE:4511` |
| 7 | `7447` | 7447 BCD to 7-Segment Decoder | logic_ic | `U` | `74xx_IEEE:7447` |
| 8 | `7490` | 7490 Decade Counter | logic_ic | `U` | `74xx_IEEE:7490` |
| 9 | `74HC00` | 74HC00 Quad NAND Gate | logic_ic | `U` | `74xx:74HC00` |
| 10 | `74HC02` | 74HC02 Quad NOR Gate | logic_ic | `U` | `74xx:74HC02` |
| 11 | `74HC04` | 74HC04 Hex Inverter | logic_ic | `U` | `74xx:74HC04` |
| 12 | `74HC08` | 74HC08 Quad AND Gate | logic_ic | `U` | `74xx:74LS08` |
| 13 | `74HC151` | 74HC151 8-Input Multiplexer | logic_ic | `U` | `74xx:74LS151` |
| 14 | `74HC157` | 74HC157 Quad 2-Input Multiplexer | logic_ic | `U` | `74xx:74LS157` |
| 15 | `74HC160` | 74HC160 Counter | logic_ic | `U` | `74xx:74LS160` |
| 16 | `74HC174` | 74HC174 Hex D Flip-Flop | logic_ic | `U` | `74xx:74LS174` |
| 17 | `74HC192` | 74HC192 Up/Down Counter | logic_ic | `U` | `74xx:74HC192` |
| 18 | `74HC266` | 74HC266 Quad XNOR Gate | logic_ic | `U` | `4xxx:4077` |
| 19 | `74HC283` | 74HC283 4-Bit Adder | logic_ic | `U` | `74xx:74LS283` |
| 20 | `74HC32` | 74HC32 Quad OR Gate | logic_ic | `U` | `74xx:74LS32` |
| 21 | `74HC595_SHIFT_REGISTER` | 74HC595 Shift Register | logic_ic | `U` | `74xx:74HC595` |
| 22 | `74HC74` | 74HC74 Dual D Flip-Flop | logic_ic | `U` | `74xx:74HC74` |
| 23 | `74HC76` | 74HC76 Dual JK Flip-Flop | logic_ic | `U` | `74xx:74LS76` |
| 24 | `74HC85` | 74HC85 4-Bit Comparator | logic_ic | `U` | `74xx:74HC85` |
| 25 | `74HC86` | 74HC86 Quad XOR Gate | logic_ic | `U` | `74xx:74HC86` |
| 26 | `7SEGCOMA` | 7-Segment Common Anode | display | `DS` | `Display_Character:KCSA02-107` |
| 27 | `7SEGCOMK` | 7-Segment Common Cathode | display | `DS` | `Display_Character:KCSC02-107` |
| 28 | `ACS712` | ACS712 Current Sensor | sensor | `U` | `Sensor_Current:ACS712xLCTR-20A` |
| 29 | `ARDUINO_NANO` | Arduino Nano | microcontroller_module | `A` | `MCU_Module:Arduino_Nano_v3.x` |
| 30 | `AUDIO_INPUT_JACK` | Audio Input Jack | connector | `J` | `Connector_Audio:AudioJack3` |
| 31 | `AUDIO_JACK` | Audio Jack | connector | `J` | `Connector_Audio:AudioJack3` |
| 32 | `BC547` | BC547 NPN Transistor | bjt | `Q` | `Transistor_BJT:BC547` |
| 33 | `BME280` | BME280 Sensor | sensor | `U` | `Sensor:BME280` |
| 34 | `BOOT_PUSH_BUTTON` | BOOT Push Button | switch | `SW` | `Switch:SW_Push` |
| 35 | `BRIDGE_RECTIFIER` | Bridge Rectifier | diode_bridge | `BR` | `Device:D_Bridge_+-AA` |
| 36 | `BS170` | BS170 NMOS | mosfet | `Q` | `Transistor_FET:BS170` |
| 37 | `BZX55C5` | BZX55C5 Zener Diode | zener_diode | `D` | `Device:D_Zener` |
| 38 | `BZX79C5` | BZX79C5 Zener Diode | zener_diode | `D` | `Device:D_Zener` |
| 39 | `CAN_TERMINAL` | CAN Terminal | terminal | `J` | `Connector:Screw_Terminal_01x03` |
| 40 | `CAP` | Capacitor | capacitor | `C` | `Device:C` |
| 41 | `CAPACITOR` | Capacitor | capacitor | `C` | `Device:C` |
| 42 | `CAP_ELEC` | Electrolytic Capacitor | capacitor | `C` | `Device:C_Polarized` |
| 43 | `CARD_DETECT_SWITCH` | Card Detect Switch | switch | `SW` | `Switch:SW_SPST` |
| 44 | `CD4007` | CD4007 CMOS Array | logic_ic | `U` | `Transistor_FET:Q_Dual_NMOS_PMOS_G1S2G2D2S1D1` |
| 45 | `CH340` | CH340 USB-UART | interface_ic | `U` | `Interface_USB:CH340G` |
| 46 | `CHARGING_LED` | Charging LED | indicator | `D` | `Device:LED` |
| 47 | `CHIP_SELECT_JUMPER` | Chip Select Jumper | jumper | `JP` | `Jumper:Jumper_2_Open` |
| 48 | `COIN_CELL_HOLDER` | Coin Cell Holder | battery_holder | `BT` | `Device:Battery_Cell` |
| 49 | `CP2102` | CP2102 USB-UART IC | interface_ic | `U` | `Interface_USB:CP2102N-Axx-xQFN28` |
| 50 | `CP_100UF` | 100uF Electrolytic Capacitor | capacitor | `C` | `Device:C_Polarized` |
| 51 | `CR2032_BATTERY` | CR2032 Battery | battery | `BT` | `Device:Battery_Cell` |
| 52 | `CRYSTAL_16MHZ` | 16MHz Crystal | crystal | `Y` | `Device:Crystal` |
| 53 | `CRYSTAL_OSCILLATOR_CAN` | Crystal Oscillator | crystal | `Y` | `Device:Crystal` |
| 54 | `CSOURCE` | Current Source | source | `I` | `Simulation_SPICE:IDC` |
| 55 | `C_100NF_CERAMIC` | 100nF Ceramic Capacitor | capacitor | `C` | `Device:C` |
| 56 | `C_100NF_FLASH` | 100nF Capacitor | capacitor | `C` | `Device:C` |
| 57 | `C_22PF_X1` | 22pF Capacitor x1 | capacitor | `C` | `Device:C` |
| 58 | `C_22PF_X2` | 22pF Capacitor x2 | capacitor | `C` | `Device:C` |
| 59 | `DC_BARREL_JACK` | DC Barrel Jack | connector | `J` | `Connector:Barrel_Jack` |
| 60 | `DC_MOTOR` | DC Motor | motor | `M` | `Motor:Motor_DC` |
| 61 | `DECOUPLING_CAPACITOR` | Decoupling Capacitor | capacitor | `C` | `Device:C` |
| 62 | `DECOUPLING_CAPACITOR_SD` | Decoupling Capacitor | capacitor | `C` | `Device:C` |
| 63 | `DIODE` | Diode | diode | `D` | `Device:D` |
| 64 | `DIP_SWITCH` | DIP Switch | switch | `SW` | `Switch:SW_DIP_x08` |
| 65 | `DS3231` | DS3231 RTC | rtc_ic | `U` | `Timer_RTC:DS3231M` |
| 66 | `D_1N4007` | 1N4007 Diode | diode | `D` | `Diode:1N4007` |
| 67 | `EN_PUSH_BUTTON` | EN Push Button | switch | `SW` | `Switch:SW_Push` |
| 68 | `ESP32_WROOM` | ESP32-WROOM Module | wireless_module | `U` | `RF_Module:ESP32-WROOM-32` |
| 69 | `FEEDBACK_RESISTOR` | Feedback Resistor | resistor | `R` | `Device:R` |
| 70 | `FLYBACK_DIODE` | Flyback Diode | diode | `D` | `Device:D` |
| 71 | `FUSE` | Fuse | protection | `F` | `Device:Fuse` |
| 72 | `GND_SYMBOL` | Ground Symbol | power_symbol | `#PWR` | `power:GND` |
| 73 | `GROUND` | Ground | power_symbol | `#PWR` | `power:GND` |
| 74 | `HEADER_CONNECTOR` | Header Connector | header | `J` | `Connector_Generic:Conn_01x04` |
| 75 | `I2C_HEADER` | I2C Header | header | `J` | `Connector_Generic:Conn_01x04` |
| 76 | `INPUT_CAPACITOR` | Input Capacitor | capacitor | `C` | `Device:C` |
| 77 | `INPUT_CAPACITOR_BUCK` | Input Capacitor | capacitor | `C` | `Device:C_Polarized` |
| 78 | `IRLZ44N` | IRLZ44N MOSFET | mosfet | `Q` | `Transistor_FET:IRLZ44N` |
| 79 | `JST_CONNECTOR` | JST Connector | connector | `J` | `Connector_Generic:Conn_01x04` |
| 80 | `LED` | LED | indicator | `D` | `Device:LED` |
| 81 | `LED_ARRAY` | LED Array | indicator | `D` | `Connector_Generic:Conn_02x08_Odd_Even` |
| 82 | `LED_INDICATOR` | LED | indicator | `D` | `Device:LED` |
| 83 | `LEVEL_SHIFTER` | Level Shifter | interface_ic | `U` | `Logic_LevelTranslator:TXS0108EPW` |
| 84 | `LI_ION_BATTERY_CONNECTOR` | Li-Ion Battery Connector | connector | `J` | `Connector_Generic:Conn_01x02` |
| 85 | `LM2596` | LM2596 | buck_converter | `U` | `Regulator_Switching:LM2596S-ADJ` |
| 86 | `LM317` | LM317 Adjustable Regulator | regulator | `U` | `Regulator_Linear:LM317_TO-220` |
| 87 | `LM358` | LM358 Op-Amp | opamp | `U` | `Amplifier_Operational:LM358` |
| 88 | `LM393_COMPARATOR` | LM393 Comparator | comparator | `U` | `Comparator:LM393` |
| 89 | `LM741` | LM741 Op-Amp | opamp | `U` | `Amplifier_Operational:LM741` |
| 90 | `LM7805` | LM7805 Voltage Regulator | regulator | `U` | `Regulator_Linear:LM7805_TO220` |
| 91 | `MAX485` | MAX485 Transceiver | interface_ic | `U` | `Interface_UART:MAX485E` |
| 92 | `MCP2515` | MCP2515 CAN Controller | interface_ic | `U` | `Interface_CAN_LIN:MCP2515-xSO` |
| 93 | `MICRO_SD_SOCKET` | Micro SD Socket | connector | `J` | `Connector:Micro_SD_Card_Det1` |
| 94 | `MICRO_USB_CONNECTOR` | Micro USB Connector | connector | `J` | `Connector:USB_B_Micro` |
| 95 | `MOSFET` | MOSFET | mosfet | `Q` | `Transistor_FET:IRLZ44N` |
| 96 | `MOUNTING_HOLE` | Mounting Hole | mechanical | `H` | `Mechanical:MountingHole` |
| 97 | `NE555` | NE555 Timer | timer_ic | `U` | `Timer:NE555P` |
| 98 | `NMOS` | NMOS Transistor | mosfet | `Q` | `Transistor_FET:Q_NMOS_DGS` |
| 99 | `NPN` | NPN Transistor | bjt | `Q` | `Transistor_BJT:Q_NPN_BCE` |
| 100 | `OPAMP` | Op-Amp | opamp | `U` | `Amplifier_Operational:LM741` |
| 101 | `OUTPUT_CAPACITOR_BUCK` | Output Capacitor | capacitor | `C` | `Device:C_Polarized` |
| 102 | `OUTPUT_FILTER_CAPACITOR` | Output Filter Capacitor | capacitor | `C` | `Device:C` |
| 103 | `PAM8403` | PAM8403 Amplifier | audio_ic | `U` | `Amplifier_Audio:PAM8403D` |
| 104 | `PIN_HEADER` | Pin Header | header | `J` | `Connector_Generic:Conn_01x08` |
| 105 | `PNP` | PNP Transistor | bjt | `Q` | `Transistor_BJT:Q_PNP_BCE` |
| 106 | `POLYFUSE` | Polyfuse Resettable Fuse | protection | `F` | `Device:Polyfuse` |
| 107 | `POTENTIOMETER` | Potentiometer | potentiometer | `RV` | `Device:R_Potentiometer` |
| 108 | `POT_HG` | Potentiometer | potentiometer | `RV` | `Device:R_Potentiometer` |
| 109 | `POWER_INDUCTOR` | Power Inductor | inductor | `L` | `Device:L` |
| 110 | `POWER_LED` | Power LED | indicator | `D` | `Device:LED` |
| 111 | `PROGRAMMING_HEADER` | Programming Header | header | `J` | `Connector_Generic:Conn_01x14` |
| 112 | `PROTECTION_IC` | Protection IC | protection_ic | `U` | `Battery_Management:DW01A` |
| 113 | `PULLUP_RESISTOR_OLED` | Pull-up Resistor | resistor | `R` | `Device:R` |
| 114 | `PUSH_BUTTON` | Push Button | switch | `SW` | `Switch:SW_Push` |
| 115 | `PWM_HEADER` | PWM Header | header | `J` | `Connector_Generic:Conn_01x04` |
| 116 | `PWR_3V3` | +3V3 Power Symbol | power_symbol | `#PWR` | `power:+3V3` |
| 117 | `PWR_5V` | +5V Power Symbol | power_symbol | `#PWR` | `power:+5V` |
| 118 | `REALIND` | Inductor | inductor | `L` | `Device:L` |
| 119 | `RELAY` | Relay | relay | `K` | `Relay:Relay_SPDT` |
| 120 | `RELAY_5V` | 5V Relay | relay | `K` | `Relay:Relay_SPDT` |
| 121 | `RELAY_FLYBACK_DIODE` | Relay Flyback Diode | diode | `D` | `Device:D` |
| 122 | `RELAY_INDICATOR_LED` | Indicator LED | indicator | `D` | `Device:LED` |
| 123 | `RES` | Resistor | resistor | `R` | `Device:R` |
| 124 | `RESET_CAPACITOR` | Reset Capacitor | capacitor | `C` | `Device:C` |
| 125 | `RESISTOR` | Resistor | resistor | `R` | `Device:R` |
| 126 | `RESISTOR_NETWORK` | Resistor Network | resistor | `RN` | `Connector_Generic:Conn_02x08_Odd_Even` |
| 127 | `RS485_TERMINAL` | RS485 Terminal | terminal | `J` | `Connector:Screw_Terminal_01x03` |
| 128 | `RX_HEADER` | RX Header | header | `J` | `Connector_Generic:Conn_01x01` |
| 129 | `R_10K_PULLUP` | 10k Pull-up Resistor | resistor | `R` | `Device:R` |
| 130 | `R_120_CAN` | 120 ohm Termination Resistor | resistor | `R` | `Device:R` |
| 131 | `R_120_RS485` | 120 ohm Termination Resistor | resistor | `R` | `Device:R` |
| 132 | `R_220` | 220 ohm Resistor | resistor | `R` | `Device:R` |
| 133 | `R_4K7_PULLUP` | 4.7k Pull-up Resistor | resistor | `R` | `Device:R` |
| 134 | `SCHOTTKY_DIODE_BUCK` | Schottky Diode | diode | `D` | `Device:D_Schottky` |
| 135 | `SCL_PULLUP` | SCL Pull-up | resistor | `R` | `Device:R` |
| 136 | `SCREW_TERMINAL_2` | Screw Terminal 2-pin | terminal | `J` | `Connector:Screw_Terminal_01x02` |
| 137 | `SDA_PULLUP` | SDA Pull-up | resistor | `R` | `Device:R` |
| 138 | `SPEAKER` | Speaker | speaker | `LS` | `Device:Speaker` |
| 139 | `SPI_HEADER_FLASH` | SPI Header | header | `J` | `Connector_Generic:Conn_01x08` |
| 140 | `SPI_HEADER_SD` | SPI Header | header | `J` | `Connector_Generic:Conn_02x03_Odd_Even` |
| 141 | `SSD1306_OLED` | SSD1306 OLED | display | `DS` | `Display_Graphic:OLED-128O064D` |
| 142 | `SWITCH` | Switch | switch | `SW` | `Switch:SW_SPST` |
| 143 | `TERMINAL` | Terminal | terminal | `J` | `Connector_Generic:Conn_01x02` |
| 144 | `TERMINAL_BLOCK` | Terminal Block | terminal | `J` | `Connector:Screw_Terminal_01x02` |
| 145 | `TERMINAL_BLOCK_4` | Terminal Block 4-pin | terminal | `J` | `Connector:Screw_Terminal_01x04` |
| 146 | `TEST_POINT` | Test Point | testpoint | `TP` | `Connector:TestPoint` |
| 147 | `TJA1050` | TJA1050 CAN Transceiver | interface_ic | `U` | `Interface_CAN_LIN:SN65HVD1050D` |
| 148 | `TP4056` | TP4056 Charger IC | charger_ic | `U` | `Battery_Management:TP4056-42-ESOP8` |
| 149 | `TRANSFORMER` | Transformer | transformer | `T` | `Device:Transformer_1P_1S` |
| 150 | `TRIMMER_POTENTIOMETER` | Trimmer Potentiometer | potentiometer | `RV` | `Device:R_Potentiometer_Trim` |
| 151 | `TVS_DIODE_RS485` | TVS Protection Diode | protection | `D` | `Device:D_TVS` |
| 152 | `TX_HEADER` | TX Header | header | `J` | `Connector_Generic:Conn_01x01` |
| 153 | `UART_HEADER` | UART Header | header | `J` | `Connector_Generic:Conn_01x05` |
| 154 | `USB_CONNECTOR` | USB Connector | connector | `J` | `Connector:USB_B_Micro` |
| 155 | `USB_CONNECTOR_UART` | USB Connector | connector | `J` | `Connector:USB_B_Micro` |
| 156 | `USB_C_CONNECTOR` | USB Type-C Connector | connector | `J` | `Connector:USB_C_Receptacle_USB2.0_16P` |
| 157 | `VCC_SYMBOL` | VCC Power Symbol | power_symbol | `#PWR` | `power:VCC` |
| 158 | `VDC` | DC Voltage Source | source | `V` | `Simulation_SPICE:VDC` |
| 159 | `VOLUME_POTENTIOMETER` | Volume Potentiometer | potentiometer | `RV` | `Device:R_Potentiometer` |
| 160 | `VPULSE` | Pulse Voltage Source | source | `V` | `Simulation_SPICE:VPULSE` |
| 161 | `VSIN` | Sine Voltage Source | source | `V` | `Simulation_SPICE:VSIN` |
| 162 | `VSOURCE` | Voltage Source | source | `V` | `Simulation_SPICE:VDC` |
| 163 | `W25Q64` | W25Q64 Flash IC | memory_ic | `U` | `Memory_Flash:W25Q32JVSS` |

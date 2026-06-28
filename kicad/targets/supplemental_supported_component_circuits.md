# Supplemental Component Circuits

The uploaded PDF already covers many digital ICs and primitives. This file defines extra target circuits for catalog components that may not appear directly in the PDF or need separate smoke validation.

## Supplemental targets

- S01: DC resistor operating point using VDC, R, GND.
- S02: RC low-pass transient using VSIN, R, C, GND.
- S03: RL transient using VSIN, R, L, GND.
- S04: Diode clamp using VSIN, R, D, VDC reference, GND.
- S05: LED current indicator using VDC, R, LED, GND.
- S06: Zener shunt regulator using VDC, R, ZENER, load resistor, GND.
- S07: Schottky half-wave rectifier using VSIN, SCHOTTKY, R, C, GND.
- S08: VPULSE digital input into R-C debounce using VPULSE, R, C, SW_PUSH, GND.
- S09: NPN low-side switch using VDC, R, NPN, LED/load, GND.
- S10: PNP high-side switch using VDC, R, PNP, LED/load, GND.
- S11: NMOS low-side switch using VPULSE, R, NMOS, load, GND.
- S12: PMOS high-side switch using VDC, PMOS, R gate pull-up, load.
- S13: LM741 comparator threshold using LM741/OPAMP, R divider, VSIN or VDC input.
- S14: LM358 buffer/filter using LM358, R, C, VSIN.
- S15: NE555 astable using NE555, R, C, VDC, GND.
- S16: 7805 regulator block using L7805, input/output capacitors, GND.
- S17: LM317 adjustable regulator using LM317, two resistors, capacitors.
- S18: Connector smoke sheet using CONN_2, CONN_3, CONN_4, test points.
- S19: Logic smoke sheet using 74HC00/04/08/32/86 and rails.
- S20: Counter/display smoke sheet using 74HC90, 4511, 7-segment connector outputs.

These supplemental targets must be generated after C01-C55 unless the workflow input limits the run count.

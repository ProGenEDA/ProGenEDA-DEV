# PSpice

Reserved workspace for the PSpice generator track.

This is separate from the Proteus generator work.

## Current target source

Target reference: EE-215 Electronic Devices and Circuits lab manual.

The PSpice generator should create runnable SPICE/PSpice netlists for the lab-manual circuits and the outputs students are expected to observe or calculate.

## Generator direction

The intended pipeline is:

prompt to circuit JSON to PSpice netlist to runnable simulation output

The generator should focus on runnable simulation first, not OrCAD schematic drawing.

## Target output types

The generator should support these output requests:

- DC operating point values
- voltage and current measurements at named nodes/components
- DC sweep tables and I-V curves
- transient waveform plots for input and output voltages
- RMS, peak, peak-to-peak, average DC, ripple, and period/frequency calculations
- comparison-ready values matching lab manual blanks such as calculated, measured, and percent-difference fields

## EE-215 experiment target map

1. Basic lab equipment and signal concepts: sine, square, triangle sources; frequency, period, amplitude, RMS, DC offset, AC/DC coupling style outputs.
2. Diode characteristics: diode I-V curve using DC sweep; resistor voltage, diode voltage, diode current, threshold voltage, DC and AC resistance estimates.
3. Series and parallel diode circuits: DC bias networks, series diodes, parallel diode paths, diode logic, bridge diode networks, output voltage and branch current calculations.
4. Half-wave and full-wave rectification: sine source rectifiers, bridge rectifier, center-tapped rectifier, diode replacement tests, average DC level and waveform plots.
5. Clipping circuits: parallel and series clippers with square and sine inputs, biased clipping levels, output waveform plots.
6. Clamping circuits: diode-capacitor clamp networks, shifted waveform outputs, DC restoration behavior.
7. LED and Zener diode circuits: LED current/voltage, Zener regulation, load-line and regulation measurements.
8. BJT characteristics: input/output characteristic curves, base/collector currents, beta-related measurements.
9. Fixed and voltage-divider BJT bias: DC operating point, base/emitter/collector voltages and currents.
10. Emitter and collector feedback BJT bias: DC operating point and bias stability comparisons.
11. BJT bias design circuits: calculated design values and simulated Q-points.
12. Common-emitter amplifier: transient and AC small-signal gain, input/output waveforms, phase inversion.
13. Common-base and emitter-follower amplifiers: voltage gain, input/output waveforms, impedance-related observations.
14. Common-emitter amplifier design: target gain/bias constraints and simulation verification.
15. MOSFET characteristics: transfer/output curves and threshold behavior.
16. MOSFET DC biasing: Q-point and bias network verification.
17. MOSFET common-source amplifier: gain, waveform, and frequency-response style outputs.
18. Diode switching application: transient switching waveform generation and timing behavior.

## Initial implementation priority

Phase 1 should support:

- resistor
- capacitor
- inductor
- diode
- DC voltage source
- AC/sine voltage source
- pulse/square source
- ground node 0
- voltage probe declarations
- current measurement through voltage source or component-compatible method
- .OP, .DC, .TRAN, and basic .AC analyses

Phase 2 should add:

- Zener diode models
- LED diode models
- BJT models and bias/amplifier templates
- MOSFET models and bias/amplifier templates
- transformer approximations for rectifier labs

## Boundary

This folder is for PSpice work only. Proteus generator records remain outside this folder.

# Proteus Generator Circuit Test Set - KiCad Target Text

Source PDF uploaded by user: `daaaaaaaaaaaaaaaaaaaaaaadad.pdf`. The file is image-only, so this is a manually cleaned/OCR-derived target index. The original rendered PDF pages show C01-C55, each with functional components, generator input, and expected check.

Use this with `kicad/rules/kicad_circuit_ir_rulebook.json` to generate KiCad CircuitIR JSON.

## Circuit index from PDF

- C01: Emergency stop latch with manual reset
- C02: JK toggle fan-mode selector
- C03: Dual JK divider for alarm beeper
- C04: Six-sensor event capture register
- C05: Eight-bit output latch for appliance control
- C06: Serial LED pattern output expander
- C07: Parallel switch input serializer
- C08: Serial-in parallel-out to parallel-in loopback tester
- C09: Register-stored output bank with serial update
- C10: Input snapshot and stored alarm output
- C11: Single-digit decimal event counter
- C12: Presettable production batch counter
- C13: Four-bit synchronous binary counter monitor
- C14: Modulo-N controller with synchronous clear
- C15: Up/down people counter display driver
- C16: Bidirectional position counter with limit compare
- C17: One-of-ten step sequencer
- C18: Long-period divider for slow status beacon
- C19: Audio-rate divider for tone selection
- C20: Multi-second delay counter
- C21: Crystal-style oscillator divider using 4060
- C22: Dual BCD pulse counter
- C23: Dual binary event divider
- C24: Seven-segment BCD display using 4511
- C25: Common-anode BCD display driver
- C26: Segment display driver with active-high outputs
- C27: Two-source sensor bus selector
- C28: Eight-channel alarm selector
- C29: Dual four-input data selector
- C30: Eight-channel analog sensor scanner
- C31: Four-bit password equality checker
- C32: Cascadable magnitude comparator block
- C33: Four-bit adder with carry indicator
- C34: CMOS adder for small calculator input
- C35: Generic safety interlock logic
- C36: Parity and agreement checker
- C37: Garage door direction controller
- C38: Digital traffic-light stepper
- C39: Digital dice counter latch
- C40: Frequency divider and sample latch
- C41: Rotary encoder up/down counter
- C42: Small digital lock with serial key input
- C43: Power-on reset delay for synchronous counter
- C44: Capacitive touch latch
- C45: IR beam break counter
- C46: Elevator floor sequencer with compare
- C47: Running light with transistor output stages
- C48: Shift-register LED bank with high-side enable
- C49: Op-amp threshold controlled counter reset
- C50: Ripple divider alarm timer
- C51: Parallel load countdown timer
- C52: Binary up/down service counter
- C53: Oscillator-divider watchdog enable
- C54: Shift-register input logger
- C55: Combinational control feeding synchronous counter

## Generation instruction

For each C01-C55 circuit, the model must produce a connected CircuitIR JSON object, not a 50-component zoo sheet. The project name should start with the circuit number, e.g. `C01_emergency_stop_latch`. Use PDF component lists and generator input text as the source. The generated JSON must be saved beside the KiCad output project.

## Important PDF coverage summary

The page-1 coverage table includes common digital ICs and primitives such as 74HC74, 74HC76, 74HC273, 74HC174/175, 74HC165, 74HC595, 74HC192, 74HC193, 74HC161, 74HC163, 74HC153, 74HC151, 74HC47, 74HC48, 4511, 7490, 4017, 4020, 4024, 4040, 4060, 4518, 4520, 4051, 4063, 4008, 4093, LM741, NPN, PNP, capacitors, electrolytic capacitors, inductors, resistors, AND/OR/NOT/NAND/NOR/XNOR/XOR gates.

## Output folder contract

```text
kicad/experiments/runs/<run_id>/projects/<circuit>/
  input.json
  OPEN_THIS_PROJECT__<slug>__PROJECT_FILE.kicad_pro
  OPEN_THIS_PROJECT__<slug>__PROJECT_FILE.kicad_sch
  manifest.json
```

The user opens only the `.kicad_pro` file. The `.kicad_sch` is required internally by KiCad.

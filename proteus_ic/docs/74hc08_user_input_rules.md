# 74HC08 User Input Normalization Rules

Status: accepted input contract for the next temporary HC08 generator pack.

These rules convert user descriptions written like DIP14 breadboard wiring into
the Proteus subpart model proved by the V1 donor-learning pack.

## Core Rule

Users may describe `74HC08` as a physical 14-pin chip. The generator must not
emit it as a whole visible DIP package. It must normalize the physical pins into
Proteus subparts:

```text
U1:A
U1:B
U1:C
U1:D
```

Pins `14` and `7` are hidden supply pins in the accepted Proteus donor path:

```text
pin 14 / VCC / +5V -> ignore as IC supply
pin 7 / GND / 0V  -> ignore as IC supply
```

Do not create visible VCC/GND package-power pin connections for `74HC08` supply.
Power and ground terminals may still be generated when the user uses HIGH/LOW as
logic constants or when passive components need a ground reference.

## Physical Pin Map

```text
pin 1  / 1A -> U1:A IN1
pin 2  / 1B -> U1:A IN2
pin 3  / 1Y -> U1:A OUT

pin 4  / 2A -> U1:B IN1
pin 5  / 2B -> U1:B IN2
pin 6  / 2Y -> U1:B OUT

pin 8  / 3Y -> U1:C OUT
pin 9  / 3A -> U1:C IN1
pin 10 / 3B -> U1:C IN2

pin 11 / 4Y -> U1:D OUT
pin 12 / 4A -> U1:D IN1
pin 13 / 4B -> U1:D IN2
```

The normalized CircuitIR connection still uses package ref `U1` and the
physical signal pin number. The Proteus emitter later chooses the donor subpart
record that owns that pin.

## Naming Rules

Use stable net names for the user's signal meaning:

- External logic inputs: `A_IN`, `B_IN`, `TRIG`, `NOISY_B`, etc.
- Gate outputs: `Y1`, `Y2`, `Y3`, `Y4`, or a descriptive output name.
- Filter/delay nodes: `B_DELAY`, `ANALOG_OUT`, `FILTER_MID`, `FAST_RC`, `SLOW_RC`.
- Ground for passive shunts: `GND` with a ground terminal.
- VCC in user text is ignored for IC supply, but can exist as a power net only
  if used as a logic HIGH node or a passive supply node.

## Example Normalizations

### 1. Pure Digital AND Gate

User describes pins 14 and 7, but they are supply-only and ignored for the IC
symbol. The resulting logical connections are:

```text
U1 pin 1 -> A_IN
U1 pin 2 -> B_IN
U1 pin 3 -> Y1
```

### 2. RC Turn-On Delay on Gate 1

Pin 2 becomes the delayed node shared by the resistor, capacitor, and gate
input:

```text
U1 pin 1 -> A_IN
R1 pin 1 -> B_IN
R1 pin 2 -> B_DELAY
C1 pin 1 -> B_DELAY
C1 pin 2 -> GND
U1 pin 2 -> B_DELAY
U1 pin 3 -> Y_DELAY
```

### 3. LC Low-Pass Filtered Output on Gate 2

Gate 2 maps to subpart `U1:B`. Pin 6 is the digital output before the LC filter:

```text
U1 pin 4 -> A_FAST
U1 pin 5 -> B_FAST
U1 pin 6 -> GATE2_Y
L1 pin 1 -> GATE2_Y
L1 pin 2 -> ANALOG_OUT
C1 pin 1 -> ANALOG_OUT
C1 pin 2 -> GND
```

### 4. RLC Damped Noise Filter on Gate 3

Gate 3 maps to subpart `U1:C`. Note the physical DIP order: output pin 8 comes
before input pins 9 and 10.

```text
U1 pin 9  -> CLEAN_A
L1 pin 1  -> NOISY_B
L1 pin 2  -> FILTER_MID
R1 pin 1  -> FILTER_MID
R1 pin 2  -> FILTERED_B
C1 pin 1  -> FILTERED_B
C1 pin 2  -> GND
U1 pin 10 -> FILTERED_B
U1 pin 8  -> CLEAN_Y
```

### 5. Dual-RC Coincidence Timing Window on Gate 4

Gate 4 maps to subpart `U1:D`. The same trigger net feeds two RC branches:

```text
R1 pin 1  -> TRIG
R1 pin 2  -> FAST_RC
C1 pin 1  -> FAST_RC
C1 pin 2  -> GND
U1 pin 12 -> FAST_RC

R2 pin 1  -> TRIG
R2 pin 2  -> SLOW_RC
C2 pin 1  -> SLOW_RC
C2 pin 2  -> GND
U1 pin 13 -> SLOW_RC

U1 pin 11 -> WINDOW_Y
```

## Validator Rule

Fail closed if a user asks for unsupported package pins such as pin 15. Drop
only known hidden supply pins 7 and 14. Do not silently drop any signal pin.

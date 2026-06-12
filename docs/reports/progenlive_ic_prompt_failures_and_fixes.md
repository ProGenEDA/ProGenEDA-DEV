# ProgenLive IC Prompt Failures and Fixes

This note records prompt/backend failures observed while testing large Proteus IC logic generation from ProgenLive, plus temporary fixes and permanent backend fixes to implement later.

## 1. Long prompt caused frontend type crash

Observed frontend error:

```text
r.toLowerCase is not a function
```

Cause:

```text
The prompt exceeded the backend validation limit. FastAPI/Pydantic returned an error detail object/list, but the frontend error categorizer expected a string and called toLowerCase() on it.
```

Temporary fix:

```text
Increase backend prompt length limits from 4000 to 20000.
```

Permanent fix:

```text
Normalize backend error detail to a string before passing it into generationErrorCategory(). Also make generationErrorCategory accept unknown and convert with String(message ?? "").
```

## 2. Pin-level IC prompt failed CircuitIR validation

Observed backend error:

```text
70b could not produce valid CircuitIR after 4 attempts
```

Cause:

```text
The current IC backend expects combinational gate-level CircuitIR, not explicit package-pin instructions such as U_AND1 pin 1, pin 2, pin 3.
```

Other schema conflicts:

```text
Long package refs such as U_AND1 do not fit the current U1..U9 package convention.
Long net names such as CLK_N and A0_CALC do not fit the current two-character net-label convention.
The prompt asked for pin 14/VCC and pin 7/GND, but current Proteus IC mode treats IC power pins as hidden.
```

Temporary fix:

```text
Use Boolean/gate equations instead of pin-by-pin IC package instructions.
Use short two-character node labels.
Split the design into smaller parts.
```

Permanent fix:

```text
Add a separate pin-level IC CircuitIR schema and compiler path if pin-level package generation is required.
```

## 3. Boolean prompt failed when router did not enter IC mode

Cause:

```text
A Boolean-looking prompt can fail if it does not include explicit IC/logic trigger wording.
```

Temporary fix:

```text
Start prompts with:
This is a Boolean logic circuit using 74HC00 NAND gates, 74HC04 NOT gates, 74HC08 AND gates, and 74HC86 XOR gates.
```

Permanent fix:

```text
Improve routing so equations containing operators like `not`, `and`, `xor`, and assignments are routed to IC/logic mode even without explicit trigger phrases.
```

## 4. Extra instruction text caused generation failure

Observed:

```text
The flip-flop prompt failed when it included the extra natural-language line:
Do not use V0, V1, V2, V3 as signal names. They are not internal logic nodes.

The same prompt worked after that line was removed.
```

Likely cause:

```text
The model or parser treated the extra instruction as non-circuit text inside an equation-heavy prompt and produced invalid CircuitIR.
```

Temporary fix:

```text
Avoid extra prose inside the equation block. Apply renames directly in the equations instead of telling the model what not to do.
```

Permanent fix:

```text
Preprocess prompts into sections: instructions, terminals, equations, outputs. Ignore or separately handle non-equation instruction lines.
```

## 5. V0 name conflict caused +5V logic contention

Observed Proteus simulation message:

```text
Logic contention(s) detected on net +5V.
```

Cause:

```text
V0 was auto-associated with a power/voltage-style net in the generator/Proteus convention, while the same name was also used as an internal NAND latch node. A gate output then effectively drove the power rail.
```

Temporary fix:

```text
Do not use V0, V1, V2, V3 or other V* names for internal logic nodes. Rename them directly in the equations, for example:
V0 -> S0
W0 -> T0
V1 -> S1
W1 -> T1
```

Permanent fix:

```text
Reserve power-like names such as VCC, +5V, V0, P9, G0, GND, 0. Reject or rename internal nets that collide with reserved supply conventions.
```

## 6. Yellow/unknown digital state in Proteus

Observed:

```text
Some gate outputs or latch nodes show yellow/unknown during simulation.
```

Cause:

```text
Digital inputs or latch feedback nodes are initially undefined. Sequential feedback circuits do not always resolve to a stable 0/1 state without an initialization path. If D inputs are not connected yet, or CK/RS are floating, the result propagates as unknown.
```

Temporary fixes:

```text
Connect all external inputs to defined logic sources before running simulation.
Tie unused inputs to GND or VCC using proper Proteus digital constants/logic state sources.
Use a reset/startup sequence that forces the flip-flops to a known state.
If reset only affects D inputs, keep reset active and apply at least one clock edge so the zeros are loaded.
```

Note:

```text
A simple analog pull-down resistor may help in some mixed simulations, but the safer Proteus digital solution is a digital logic state, digital constant, or a proper pull-up/pull-down primitive compatible with digital inputs. For 74HC logic, avoid leaving any inputs floating.
```

Permanent fix:

```text
The generator should automatically add initialization helpers for generated sequential circuits:
- explicit CK input source or prompt-visible CK terminal
- explicit RS/reset source or terminal
- optional startup reset pulse template
- tie-offs for unused/floating inputs
- validation that every gate input has a driver or intentional constant
```

## 7. Reset only in D path does not initialize NAND slave latch

Observed:

```text
The D equations used NR = not RS and D = M and NR, but the cross-coupled NAND outputs could still begin yellow/unknown.
```

Cause:

```text
Masking D to zero is not the same as asynchronously clearing the NAND latch. It only makes D become 0. The actual A/N output latch still needs a clock transfer or a direct reset path.
```

Circuit fix:

```text
For each flip-flop, feed reset into the slave latch path. Use active-high RS and NR = not RS.

Old slave stage:
Sx = not (Lx and CK)
Tx = not (Ux and CK)
Ax = not (Sx and Nx)
Nx = not (Tx and Ax)

Reset-safe slave stage:
Qx = Lx and CK
Sx = not (Qx and NR)
Rx = not (Ux and CK)
Tx = Rx and NR
Ax = not (Sx and Nx)
Nx = not (Tx and Ax)
```

Behavior:

```text
When RS = 1, NR = 0:
Sx = 1
Tx = 0
Nx = 1
Ax = 0

When RS = 0, NR = 1:
The circuit behaves like the normal master-slave NAND D flip-flop.
```

Prompt rule:

```text
Do not permanently connect RS to G0 while testing reset behavior. RS must be driven high at startup to clear the latch, then driven low for normal counting.
```

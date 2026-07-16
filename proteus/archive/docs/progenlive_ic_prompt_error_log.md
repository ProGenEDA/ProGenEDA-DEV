# ProgenLive IC Prompt Error Log

This file records prompt/runtime failures observed while testing large 74HC logic prompts on ProgenLive, plus the working fixes or permanent-fix direction.

## 1. Frontend error: toLowerCase is not a function

Observed message:

```text
r.toLowerCase is not a function
```

Likely cause:

```text
Backend returned a non-string error detail, usually a validation array/object.
Frontend passed it into generationErrorCategory, which expected a string and called toLowerCase().
```

Immediate workaround:

```text
Raise backend prompt length limit so the exact long prompt is not rejected by Pydantic length validation.
```

Permanent fix:

```text
Normalize all backend error details to string before calling generationErrorCategory.
Use String(message ?? "") inside generationErrorCategory.
```

## 2. Long prompt rejected before generation

Observed situation:

```text
Large pin-level clock prompt around 12k characters failed before generation.
```

Cause:

```text
GenerateRequest prompt max_length was 4000.
PROMPT_SECURITY_MAX_CHARS was also 4000.
```

Temporary fix applied:

```text
Raise both to about 20000.
```

Permanent fix:

```text
Keep a larger configured prompt limit via environment variable.
Return clean string errors for length rejection.
Add UI character count and warning before submit.
```

## 3. Pin-level IC prompt failed valid CircuitIR generation

Observed message:

```text
70b could not produce valid CircuitIR after 4 attempts.
```

Cause:

```text
The current IC schema is combinational/gate-level, not package pin-level.
The prompt used package names such as U_INV1 and explicit pins such as pin 14, pin 7, pin 1, pin 2.
The current validator expects package refs like U1..U9 and gate subparts, not arbitrary named packages with pin connections.
```

Permanent fix:

```text
Add a separate pin-level IC schema, for example ic-pinlevel-circuit-ir/v0.1.
Represent packages, pins, terminals, and direct net ties explicitly.
Do not force pin-level prompts into the current combinational gate schema.
```

## 4. Boolean prompt failed because it did not enter IC mode

Observed situation:

```text
Boolean equations using only "and" and "not" failed or went to the wrong generator path.
```

Cause:

```text
Router looks for trigger words such as 74HC, nand, xor, boolean, logic circuit, not gate, and gate.
A prompt with equations only may be routed as a passive/RCL prompt instead of IC logic.
```

Working prompt fix:

```text
Start the prompt with:
This is a Boolean logic circuit using 74HC00 NAND gates, 74HC04 NOT gates, 74HC08 AND gates, and 74HC86 XOR gates.
```

Permanent fix:

```text
Improve router to detect equation syntax like X0 = A0 and A1, Y0 = not X0, Z0 = A0 xor B0.
Route equation-heavy prompts to IC mode even without explicit 74HC wording.
```

## 5. Timed packing sequence was not entered

Observed message:

```text
The project was not sent into the timed packing sequence.
```

Meaning:

```text
Backend returned an error before response.ok.
The frontend only enters the timed packing delay after a successful backend response.
```

Typical causes seen:

```text
Invalid CircuitIR.
Wrong schema route.
Compiler rejected generated JSON.
Too many packages for current IC backend.
```

Permanent fix:

```text
Show the actual backend error message in the UI.
Log backend validation stage: routing, LLM JSON, validation, packing, compiler.
```

## 6. Full ones+tens Boolean logic exceeded current IC backend size

Observed situation:

```text
Combined seconds ones and seconds tens next-state Boolean logic failed.
```

Cause:

```text
The design needs more IC packages than the current U1..U9 package-ref limit allows.
Current package refs are restricted to two characters.
```

Working workaround:

```text
Split into smaller blocks:
1. seconds ones next-state logic
2. seconds tens next-state logic
3. flip-flops separately
```

Permanent fix:

```text
Extend package refs while keeping two characters: U1..U9, UA..UZ.
Keep internal numeric package index independent from display ref.
```

## 7. Nested expressions should be flattened

Observed situation:

```text
C9 = A3 and (N2 and (N1 and A0))
```

Risk:

```text
LLM may emit invalid or over-nested JSON, or validator may expect two-input gates only.
```

Working fix:

```text
T0 = N1 and A0
T1 = N2 and T0
C9 = A3 and T1
```

Permanent fix:

```text
Add a preprocessor that decomposes nested Boolean expressions into two-input gates before asking the LLM or before validation.
```

## 8. Sequential feedback works only in smaller blocks

Observed result:

```text
Pure combinational next-state block worked.
Four flip-flops failed first, then worked after prompt cleanup and routing line.
```

Cause:

```text
Feedback loops are valid as gate connections but fragile for a combinational-style schema/prompt.
Large feedback blocks plus size/package limits increase failure risk.
```

Working fix:

```text
Use explicit routing line.
Remove extra descriptive section headings when possible.
Split flip-flops or keep equations clean.
Tell the model feedback loops are intentional if needed.
```

Permanent fix:

```text
Support explicit gate-connection graphs with cycles.
Do not treat feedback equations as acyclic expression trees.
Add tests for SR latch and master-slave D flip-flop.
```

## 9. Proteus simulation contention on +5V

Observed Proteus log:

```text
Netlist compilation completed OK.
Netlist linking completed OK.
Partition analysis completed OK.
Logic contention(s) detected on net +5V.
```

Likely cause:

```text
Internal signal names V0, V1, V2, V3 were used as latch nodes.
The generator or Proteus convention may treat V* as voltage/power-like nets, merging with a supply rail.
A gate output then drives the +5V net, causing logic contention.
```

Working fix:

```text
Avoid V*, P*, and G* for internal logic signals.
Rename V0/W0 to S0/T0, V1/W1 to S1/T1, and so on.
Reserve P9 for power terminal and G0 for ground terminal.
```

Permanent fix:

```text
Add reserved net-name rules:
- V* reserved or warned for power/voltage nets
- P* reserved or warned for power terminals
- G* reserved or warned for ground terminals
- internal generated nodes should use safe prefixes such as N, X, H, M, D, S, T, L, U
Add preflight lint for rail-name collisions before generation.
```

## 10. Prompt hygiene notes

Working patterns:

```text
Use two-character node labels when targeting current IC backend.
Use explicit two-input equations.
Use a clear first line that says Boolean logic circuit and names the 74HC families.
Split large circuits into independently generated blocks.
Avoid extra natural-language paragraphs in the middle of equation lists.
Avoid pin-level instructions until pin-level schema exists.
Avoid explicit pin 14/pin 7 power wiring in the current combinational IC backend because Proteus hides supply pins.
```

Permanent product fixes:

```text
1. Better router for Boolean equations.
2. Larger configured prompt limit with UI character counter.
3. Robust frontend error stringification.
4. Package refs beyond U9 using two-character sequence.
5. Pin-level schema for package/pin prompts.
6. Cyclic gate graph support for latches/flip-flops.
7. Reserved net-name linting to prevent +5V/GND contention.
8. Boolean preprocessor to flatten nested expressions.
9. Better backend stage-specific error reporting.
```

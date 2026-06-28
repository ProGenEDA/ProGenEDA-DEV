# Proteus Generator Circuit Test Set - Full OCR Text

Source: daaaaaaaaaaaaaaaaaaaaaaadad.pdf

Note: OCR may contain small recognition errors; use rendered PDF as final visual source.




## Page 1


Proteus Generator Circuit Test Set

155 real-life, generator-ready circuit prompts covering the requested ICs and primitives. Each circuit uses @ to 12 functional

‘components. Named terminals, VO/GO, and signal labels are connection helpers and are not counted as functional components.

Format rule: copy the text under GENERATOR INPUT into the generator. The sections before and after it are for human selection,

coverage, and verification

Supported component coverage in this set
Component IC Coveraae cample Count
anor C01, C10, 87, C38, 044, C50, 058 7
rancre om 1
21 cas 1
ance coe 1
rancor 6, 8, C24, C39, C4, C82 6
4ncsos 06, Co, c08, C48, 54 5
por co7, coe, 10, c#2, 54 5
1480 crt, c25,o48 3
ance crz css 2
rancret 13, 40, 648 3
ranctes cra, 43 2
ranctea 15, 26,651 3
ances cre, cat, 052 3
aor? HY, 8,638, 48,647 5
4020 cre, cao 2
024 ore 1
souo 20, 650 2
4060 21,083 2
aie cz 1
4820 cx 1
ust 19,620, 4, C48, C40 5
PN 04, 02,658, C04, 6,606, C27 (2 mre) 7
ne (04, C57. C6, C25. C28, C22, C36. (4 mor) 1
Capactor 04, 0,658, €04, Cs, 606, C27. (48 mre) 5
Elect capacior ot, 62, C6, C06. C58, 08, C1. (11 mor) 8
Inductor om 1
Resistor (01,652, C0, C04, C05 C06, C07. (48 mor) 56
AN sae 01, 02,653, C04, Cs, 656, C29. (48 mre) 2
OR gate ot, 604, CO, C08, C10, C12, C14. (0 mor) 37
NOR gate 08, 1,634, C36, 96, C42, C51. (+1 mee) 8
NANO goto (tz, C06, C1, C4, 620,635. C80. (+1 mor) 8
HOR ote 08,631, 34,636,036. ct 6
OR oie C08, C16, C33, C34, 63,638. C41. (1 mo) 8
NOT gate 001, 2,653, C25, 8, C57, C29. (80 mare) Fa
ances 12,618, C1, C31, C4, C42, C4.. (1 mor) 8
4063 cae 1
anctsr cer 1
cist ozs 1
"ans ozs 1
4081 20 1
it 15, 4, C48 3
1anca? zz. cas 2
7aHcas ozs 1
cass cas 1
008 ou 1

Page 1018


## Page 2


C01 - Emergency stop latch with manual reset
Reablife example: Industrial machine stop latch that remembers a fault until reset.
Functional components (10): 74HC7A U1, AND gate G1, OR gate G2, NOT gate G3, Resistor Rt 10k, Resistor R2 10k, Capacitor
C1 100nF, NPN Qi, Resistor R3 1k, Electrolytic capacitor EC1 10uF
(GENERATOR INPUT:

Resistor Ri 1k, Electrolytic capacitor SC1 10af. Use power terminal VO as logic HIGH and
Expected check: RUN_LATCH stays high after a valid clock until RESET clears it
C02 - JK toggle fan-mode selector
Reablife example: Two-button fan mode toggle using a JK flip-flop.
Functional components (9): 74HC76 U1, NAND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Capacitor C2 10nF, NPN Qi, Resistor R3 1k
(GENERATOR INPUT:
Expected check: Each clean button edge toggles FAN_RELAY.
C03 - Dual JK divider for alarm beeper
Real-life example: Divide a fast alarm pulse into slower alternating beeps.
Functional components (10): 4027 U1, AND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Electrolytic capacitor EC1 47uF, NPN Q1, Resistor R3 1k, Inductor L1 10mH_
GENERATOR INPUT:

Placeholder. Add R1/R2 as pull-ups for reset pins and C1/ECl fron reset/supply nodes to GD.
Expected check: Output BUZZER_LOW toggles slower than CLK_IN for a beeper drive
C04 - Six-sensor event capture register
Reablfe example: Capture six sensor states at one clock edge for a small securty panel
Functional components (10): 74HC174 U1, AND gate G1, OR gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Capacitor C2 100nF, NPN Q1, PNP Q2, Resistor R3 1k
(GENERATOR INPUT:
Expected check: One clock captures S1..S6; ALERT is high when selected stored sensors are active

Page 20115


## Page 3


C05 - Eight-bit output latch for appliance control
Reablfe example: Latch eight control cutpus for relays or indicators.
Functional components (11): 74HC273 U1, NAND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Electrolytic capacitor EC1 10uF, NPN Gi, NPN Q2, Resistor R@ 1k, Resistor R4 1k
(GENERATOR INPUT:

capacitor #1 10uf, NPN Ql, NPN Q2, Resistor R3 1k, Resistor Ri 1k. Use VO/G0. Connect

Gutput OUT Lon, Connect Ql to NEN G2 base through Rf and Q2 to OUT] Low. Add R1/S2 poll
Expected check: Eight outputs update together on LOAD_CLK; reset clears all outputs.
C06 - Serial LED pattern output expander
Real-life example: Drive eight pattern outputs from a serial control line.
Functional components (11): 74HC595 U1, NOT gate G1, AND gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF.
Electrolytic capacitor EC1 10uF, NPN Q1, NPN Q2, Resistor R3 1k, Resistor R4 1k
(GENERATOR INPUT:

Capacitor EC1 10uP, NEN Ql, NEN G2, Resistor 83 2k, Resistor Ad lk. Use 74HC595 Ul. Connect
Expected check: Serial data is shifted ito Ut and appears on Q0..Q7 after LATCH CLK.
C07 - Parallel switch input serializer
Reabife example: Read eight switch states through one serial data output
Functional components (10): 74HC165 U1, NOT gate G1, OR gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Capacitor C2 10nF, PNP Q1, NPN Q2, Resistor R3 1k
(GENERATOR INPUT:

SHIFT ENASLE and SCAN ENABLE for clock gating. Connect serial output Qu to DATA OUY terminal
Expected check: A load pulse captures SWO..SW7, then clock pulses shift them out at DATA_OUT.
C08 - Serial-in parallel-out to parallel-in loopback tester
Reablfe example: Test a simple digital cable by sending and reading an &-bit pattern
Functional components (10): 74HC595 U1, 74HC165 U2, XOR gate G1, XNOR gate G2, Resistor R1 10k, Resistor R2 10k,
Capacitor C1 100nF, Electrolytic capacitor EC1 10uF, NPN Qi, Resistor R3 tk
(GENERATOR INPUT:

to TélicltS U2 parallel inputs Al.# ao L0OP0,.L0087. Connect SERIAL IN, SHIFT. CUR, and
Expected check: The circuit checks ifthe serial output patter is retumed correctly through U2.

Page 30115


## Page 4


C09 - Register-stored output bank with serial update
Reablife example: Combine serial update and parallel latch for appliance channels.
Functional components (10): 74HC596 U1, 74HC273 U2, AND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k,
Capacitor C1 100nF, Electrolytic capacitor EC1 10uF, NPN Qi, Resistor R3 1k
(GENERATOR INPUT:

capacitor £1 10uf, NPN Ql, Resistor R3 Ik. Connect 74HC595 U1 Q0..07 to 74HC273 U2 D0..07

ow. Connect Uz Q0° through 83 £0 Nf 1 base and @i to QUT0_OW. Add Cl on UPDATE. SNABLE and
Expected check: Serial data loads Ut fist, then U2 stores the stable output bank
C10 - Input snapshot and stored alarm output
Real-life example: Capture parallel inputs and latch an alarm state.
Functional components (10): 74HC165 Ut, 74H1C74 U2, OR gate Gt, AND gate G2, NOT gate G3, Resistor R1 10k, Resistor R2
410k, Capacitor C1 100nF, NPN G1, Resistor R3 1k
(GENERATOR INPUT:
Expected check: Any detected serial input can be latched as an alarm output
C11 - Single-digit decimal event counter
Real-life example: Count events and output BCD/decade states.
Functional components (9): 7490 U1, NAND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Electrolytic capacitor EC1 10uF, NPN Q1, Resistor R3 1k
(GENERATOR INPUT:
Expected check: EVENT_CLK increments QA.QD as @ BCD count and resets atthe decoded stat.
C12 - Presettable production batch counter
Real-life example: Count products up toa preset number and raise DONE.
Functional components (10): 74HC160 U1, 74HC85 U2, AND gate G1, OR gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor
C1 100nF, NPN Q1, Resistor R3 1k, Electrolytic capacitor EC1 10uF
(GENERATOR INPUT:

counter. Connect SENSOR CLK to Clock. Tie enable inputs high using VO. Connect U1 Q0..03 to
Expected check: The counter raises DONE when the BCD count equals the target terminals.

Page 4015


## Page 5


C13 - Four-bit synchronous binary counter monitor
Reablfe example: Count pulses and assert a threshold output
Functional components (Q): 74HC161 U1, 74HC8S U2, AND gate G1, NOT gate G2, Resistor Rt 10k, Capacitor C1 100nF,
Capacitor C2 10nF, NPN Qi, Resistor R2 1k
(GENERATOR INPUT:
Expected check: OVER_LIMIT_LOW activates when the binary count exceeds the threshold
C14 - Modulo-N controller with synchronous clear
Reablfe example: Generate a programmable cycle reset for sequencing
Functional components (9): 74HC163 U1, NAND gate G1, AND gate G2, OR gate G3, Resistor R1 10k, Resistor R2 10k,
Capacitor C1 100nF, NPN Q1, Resistor R@ 1k
(GENERATOR INPUT:

Gi, AND gate G2, ON gate G3, Resistor Al 10k, Resistor &2 10k, Capacitor Cl 100nP, NEN Ol,
Expected check: The counter resets or reloads when the decoded cyole count s reached.
C15 - Upidown people counter display driver
Reablife example: Track room occupancy direction using upidown pulses.
Functional components (10): 74HC192 U1, 4511 U2, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 10k, Resistor R2 10k,
Capacitor C1 100nF, NPN Q1, Resistor R3 1k
(GENERATOR INPUT:
Expected check: The BCD count changes with entry/exit pulses and is decoded to seven-segment terminals.
C16 - Bidirectional position counter with limit compare
Reablife example: Track motor position up/down and assert end-imit
Functional components (10): 74HC193 U1, 74HC85 U2, XOR gate G1, AND gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor
C1 100nF, Capacitor C2 10nF, PNP 1, Resistor R3 1k
(GENERATOR INPUT:
Expected check: The ciruit tracks a 4-bit postion and lags when it equals the selected limit.

Page S015


## Page 6


C17 - One-of-ten step sequencer

Real-life example: Make a ten-steprelay/LED sequence controle.

Functional components (11) 4017 U1, AND gate G1, OR gate G2, NOT gate G3, Resistor Rt 10k, Resistor R2 10k, Capacitor C1
400nF, NPN Q1, NPN G2, Resistor RS tk, Resistor R4 1k
(GENERATOR INPUT:

(02, Resistor 83 1k, Resistor 8! 1k. Use 4017 Ul as decade sequencer. Connect STEP CLK to

Expected check: Each clock advances one active output across STEPO..STEPS

C18 - Long-period divider for slow status beacon

Real-life example: Divide a fast square input into a slow flashing output.

Functional components (9): 4020 U1, AND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Electrolytic capacitor EC1 47uF, NPN Q1, Resistor R3 1k
(GENERATOR INPUT:

Bei f7uF, NEW G1, Resistor Ad 1k. Use 4020 U1 as tipple divider. Connect, FAST_CLE to U1

Expected check; BEACON_LOW toggles at a divided-down rate from FAST_CLK.

C19 - Audio-rate divider for tone selection

Reablfe example: Create selectable divided clock outputs for atone generator stage.

Functional components (10): 4024 U1, OR gate G1, AND gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1 100nF,
Capacitor C2 10nF, LM741 U2, Resistor R3 10k, Capacitor C3 nF
(GENERATOR INPUT:

Expected check: The circuit selects a divided clock tone and buffers it with LM741

C20 - Multi-second delay counter

Real-life example: Generate a delayed enable after many clock pulses.

Functional components (10): 4040 U1, NAND gate G1, AND gate G2, NOT gate G3, Resistor R1 10k, Resistor R2 10k, Capacitor
C1 100nF, Electrolytic capacitor EC1 100uF, NPN Q1, Resistor R3 1k
(GENERATOR INPUT:

AND gate G2. Drive NPN Ql through RJ as ENABLE LOW output. Add Al/R2 pulls and C1/EC1 to.

Expected check: ENABLE_LOW becomes active only after the selected delay count is reached.

Page 6015


## Page 7


C21 - Crystal-style oscillator divider using 4060

Reabife example: Generate multiple timing taps from one RC oscilatordivider.

Functional components (10}: 4060 Ut, AND gate G1, OR gate G2, Resistor R1 100k, Resistor R2 10k, Capacitor C1 100nF,
Capacitor C2 10nF, Electrolytic capacitor EC1 10UF, NPN Qt, Resistor R3 1k
(GENERATOR INPUT:

Electrolytic capacitor £C1 10uF, NEN Ql, Resistor R3 1k. Use 4060 Ul with Rl, R2, Cl, and C2

Expected check: The 4060 produces divided timing outputs from its RC oscillator network.

C22 - Dual BCD pulse counter

Reabife example: Count two related event streams in one circu

Functional components (9): 4518 U1, 74HC47 U2, AND gate G1, OR gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1
100nF, NPN Qi, Resistor R3 1k
(GENERATOR INPUT:

Expected check: Counter A drives seven-segment terminals; counter B remains exposed as BCD terminals.

C23 - Dual binary event divider

Reabife example: Create two independent dvide-by-N contol channels

Functional components (10): 4520 U1, AND gate G1, AND gate G2, OR gate G3, Resistor R1 10k, Resistor R2 10k, Capacitor C1
400nF, Capacitor C2 1OnF, NPN Qt, Resistor R3 1k
(GENERATOR INPUT:

Expected check: Two independent divided outputs are produced from two clock inputs

C24 - Seven-segment BCD display using 4511

Real-life example: Decode a latched BCD value to a common-cathode seven-segment output.

Functional components (9): 4511 U1, 74HC273 U2, AND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1
100nF, NPN Q1, Resistor R3 1k.
GENERATOR INPUT:

Expected check: A stored 4-bit BCD value appears as seven-segment segment terminal.

age 716


## Page 8


C25 - Common-anode BCD display driver
Reallife example: Drive a common-anode style display from a decade counter.
Functional components (9): 74HC47 U1, 7490 U2, AND gate G1, OR gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor C1
100nF, PNP Qi, Resistor R3 1k
(GENERATOR INPUT:
Expected check: The 7490 count is decoded by 74HC47 to active-low segment output.
C26 - Segment display driver with active-high outputs
Reablfe example: Generate seven-segment outputs from an upldown count
Functional components (9): 74HC48 U1, 74HC192 U2, AND gate G1, NOT gate G2, Resistor R1 10k, Resistor R2 10k, Capacitor
C1 100nF, NPN Qi, Resistor R3 ‘ie
(GENERATOR INPUT:
Expected check: The BCD counts dieplayed through active-high segment outputs.
27 - Two-source sensor bus selector
Reablfe example: Choose between automatic and manual sensor buses
Functional components (9): 74HC157 U1, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 10k, Capacitor C1 100nF,
Capacitor C2 10nF, NPN Q’, Resistor R2 1k
(GENERATOR INPUT:

G1, OR gate G2, NO? gate G3, Resistor Rl 10k, Capacitor Cl 100nF, Capacitor C2 10nF, NPN Ql,
Expected check: MODE_SELECT chooses which 4-bit sensor bus appears on outputs YO..Y3.
28 - Eight-channel alarm selector
Real-life example: Select one of eight digital alarm sources.
Functional components (9): 74HC151 U1, NOT gate G1, AND gate G2, OR gate G3, Resistor R1 10k, Resistor R2 10k, Capacitor
(C1 100nF, NPN Qi, Resistor R3 1k
(GENERATOR INPUT:
Expected check: One selected alarm channel controls the alarm output.

Page 8015


## Page 9


29 - Dual four-input data selector
Reablife example: Select between multiple control sources for two channels.
Functional components (9): 746153 U1, AND gate G1, AND gate G2, OR gate G3, Resistor Rt 10k, Capacitor C1 100F,
Capacitor C2 10nF, PNP Qi, Resistor R2 tk
(GENERATOR INPUT:
Expected check: Two independent selected channels are produced using the same select address.
C30 - Eight-channel analog sensor scanner
Reablfe example: Scan analog sensor channels into an op-amp buffer.
Functional components (9): 4051 U1, LM741 U2, NOT gate G1, AND gate G2, Resistor R1 10k, Resistor R2 100k, Capacitor C1
400nF, Capacitor C2 10nF, Electroiytic capacitor EC 10uF
(GENERATOR INPUT:
Expected check: The selected sensor channel is buffered at OPAMP_OUT.
C31 - Four-bit password equality checker
Reablife example: Compare a stored 4-bit code with entered switches,
Functional components (9): 74HC85 U1, XNOR gate G1, XNOR gate G2, AND gate G3, AND gate G4, Resistor R1 10k, Capacitor
C1 100nF, NPN Qi, Resistor R2 te
(GENERATOR INPUT:
Expected check: UNLOCK is high only when the code matches.
32 - Cascadable magnitude comparator block
Reablife example: Compare two 4-bit values and expose greaterlequalless outputs.
Functional components (10): 4063 U1, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 10k, Resistor R2 10k, Capacitor C1
100nF, NPN Q1, PNP Q2, Resistor R3 1k
(GENERATOR INPUT:

through 83 aa GREATER. Low. Use ANP G2 ap high-side status for EQUAL. Add AI/32 pollo and CL

ebounce:
Expected check: The block outputs greater-than, equal, and less-than conditions.

Page 90115


## Page 10


33 - Four-bit adder with carry indicator
Reabife example: Add two 4-bit values and flag carry overtiow
Functional components (8): 7410283 U1, XOR gate G1, OR gate G2, AND gate G3, Resistor R1 10k, Capacitor C1 100nF, NPN
1, Resistor R2 tk
(GENERATOR INPUT:

Use 74HC263 Ul as 4-bit binary adder. Connect A0..A3 and BO..83 co input terminals. Connect
Expected check: The cireuit outputs a 4-bit sum and an overfiow/earry indicator.
34 - CMOS adder for small calculator input
Reabife exemple: Make a 4-bit calculator adder using 4008.
Functional components (10): 4008 U1, XOR gate G1, XNOR gate G2, AND gate G3, OR gate G4, Resistor R1 10k, Capacitor C1
100nF, Capacitor C2 10nF, NPN Qi, Resistor R2 1k
(GENERATOR INPUT:
Expected check: The 4008 computes the binary sum while gates produce a simple result ag
C35 - Generic safety interlock logic
Real-life example: Combine multiple safety switches into one permit output.
Functional components (11): AND gate G1, OR gate G2, NOR gate G3, NAND gate G4, XNOR gate G5, XOR gate G6, NOT gate
G7, Resistor R1 10k, Capacitor C1 100nF, NPN G1, Resistor R2 1k
(GENERATOR INPUT:

Capacitor €! 100m. MEN 91, Resistor R2 1k. Connect DOOR, CLOSED and GUARD. CLOSED to AND gate
Expected check: PERMIT only activates when interlocks are safe and redundant sensors agree
C36 - Parity and agreement checker
Real-life example: Check whether a small data bus has expected parity and matching copy.
Functional components (11): XOR gate G1, XOR gate G2, XNOR gate G3, XNOR gate G4, AND gate G5, OR gate G8, NOT gate
G7, Resistor R1 10k, Capacitor C1 100nF, PNP Q1, Resistor R2 1k
GENERATOR INPUT:

DRIAL with COPY1 using ROR gate Gl. Foed Go and Gi into AND gate GD for RESEBNENT. Use OR

Ekeough €2 fron F896, Add RI/Cl to CECK node
Expected check: PASS indicates valid panty and matching copied bits.

Pago 100F 15


## Page 11


C37 - Garage door direction controller
Reablife example: Control motor direction with remembered state and end stops.
Functional components (10): 74HC7A U1, AND gate G1, OR gate G2, NOT gate G3, NPN Q1, PNP Q2, Resistor R1 1k, Resistor
2 1k, Capacitor C1 100nF, Electrolytic capacitor EC1 47uF
(GENERATOR INPUT:

Greate CLOSE. STATE fron Q. Use AND gate Gi to combine UI Q wich NOT-TO® LIMIT for HOTOR UP.
Expected check: Motor control outputs change according to commands and limit sensors.
C38 - Digital traffic-light stepper
Reablfe example: Generate a traffclight sequence from a step clock
Functional components (12): 4017 U1, 74HC74 U2, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 10k, Capacitor C1
100nF, NPN Q1, NPN Q2, NPN Q3, Resistor R2 1k, Resistor R3 1k
(GENERATOR INPUT:

Salchs U2 to latch NIGHE MODE. Decode UL outputs 00/0: as GREEN, 02 as YELLOW, Q3/04 as RED
Expected check: Outputs cycle through green, yellow, and red states.
39 - Digital dice counter latch
Real-life example: Make a simple electronic dice state generator.
Functional components (11): 4017 Ut, 74HC273 U2, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 10k, Capacitor C1
100nF, NPN Q1, NPN G2, Resistor R2 th, Resistor R3 1k
(GENERATOR INPUT:
Expected check: When RELEASE_BUTTON is pressed, the current die pattem is latched.
C40 - Frequency divider and sample latch
Reablife example: Divide a signal and periodically latch its counter state.
Functional components (10): 4020 U1, 74HC161 U2, 74HC273 U3, AND gate G1, OR gate G2, Resistor R1 10k, Capacitor C1
100nF, Capacitor C2 10nF, NPN Qi, Resistor R2 tk
(GENERATOR INPUT:

Oven Anos. had Ri and ei/ez filters.
Expected check: The latch stores @ sampled counter value ata slower divided rate

Page 11 of 18


## Page 12


C41 - Rotary encoder up/down counter
Reablfe example: Decode direction pulses into a position count.
Functional components (10): 74HC 193 U1, XOR gate G1, AND gate G2, NOT gate G3, 74HC85 U2, Resistor R1 10k, Capacitor
C1 100nF, Capacitor C2 100nF, NPN Qi, Resistor R2 1k
(GENERATOR INPUT:

100nf, NPN Q1, Resistor R2 Ik. Connect encoder phase A and phase ® to XOR gate Gl for

i fron U2 4.80.8 through R2. Add Al pUll and C1/¢2 debounce on phases.
Expected check: The position count changes with encoder direction and flags the set limit.
C42 - Small digital lock with serial key input
Reablfe example: Load a serial key and compare selected bits.
Functional components (10): 74HC165 U1, 74HC85 U2, XNOR gate G1, XNOR gate G2, AND gate G3, NOT gate G4, Resistor R1
410k, Capacitor C1 100nF, NPN Qi, Resistor R2 1k
(GENERATOR INPUT:
Expected check: UNLOCK activates when the entered key matches the stored code.
C43 - Power-on reset delay for synchronous counter
Real-life example: Hold a counter reset during supply startup.
Functional components (9): 74HC163 U1, NOT gate G1, AND gate G2, Resistor R1 100k, Resistor R2 10k, Capacitor C1 100nF,
Electrolytic capacitor EC1 47uF, NPN Q1, Resistor R3 1k
(GENERATOR INPUT:
Expected check: The counter remains reset during startup and then begins counting
C44 - Capacitive touch latch
Reabife example: Convert a touch pulse into a latched digital ouput
Functional components (10): LM741 U1, 74HC74 U2, NOT gate G1, AND gate G2, Resistor R1 1M, Resistor R2 100k, Capacitor
Ct On, NPN Qi, Resistor R3 1k, Electrolytic capacitor EC 10uF
(GENERATOR INPUT:

Not @: fron U2 @ thrown 83. Add Sct from VO to cO
Expected check: A touch event is conditioned by LM741 and latched by 74HC7A.

Pago t20f 18


## Page 13


C45 - IR beam break counter
Reablife example: Count objects passing an IR sensor and show BCD output
Functional components (10): LM741 U1, 7490 U2, 4511 U3, NOT gate G1, AND gate G2, Resistor R1 10k, Resistor R2 100k,
Capacitor C1 100nF, NPN Qi, Resistor R@ 1k
(GENERATOR INPUT:

Resistor R3 1K. Use LM741 Ul as threshold comparator for IR SENSOR node. Set reference with
Expected check: Each beam break increments the displayed count.
C46 - Elevator floor sequencer with compare
Reabife example: Sequence floor requests and compare current floor
Functional components (10): 4017 U1, 74HC85 U2, OR gate G1, AND gate G2, NOT gate G3, Resistor R1 10k, Capacitor C1
100nF, NPN Q1, PNP Q2, Resistor R2 1k
(GENERATOR INPUT:

active floor externally to REQ0..A503 terminals. Connect current floor CURD. .CUR3 and
Expected check: The controller steps through floors and asserts ARRIVED when current equals request
C47 - Running light with transistor output stages
Reablife example: Use a decade counter to drive staged transistor outputs
Functional components (11): 4017 U1, NPN Q1, NPN Q2, NPN Q3, PNP Q4, Resistor R1 1k, Resistor R2 1k, Resistor R3 1k,
Resistor R4 1k, Capacitor C1 100nF, Electrolytic capacitor EC1 10uF
(GENERATOR INPUT:

cleck te G0 and Ec2 rom VO to G0,
Expected check: Loads turn on one by one with each 4017 step,
C48 - Shift-register LED bank with high-side enable
Reabife example: Drive an output bank with serial data and high-side control
Functional components (11): 74HC595 U1, PNP Q1, NPN Q2, NPN Q3, AND gate G1, NOT gate G2, Resistor R1 1k, Resistor R2
1k, Resistor R3 10k, Capacitor C1 100nF, Electrolytic capacitor EC1 10uF
(GENERATOR INPUT:
Expected check: Serial data controls muttipe transistor outputs with a global high-side enable

Pago 18018


## Page 14


C49 - Op-amp threshold controlled counter reset
Reablife example: Reset a counter when analog voltage crosses threshold.
Functional components (10): LM741 U1, 74HC161 U2, OR gate G1, NOT gate G2, AND gate G3, Resistor R1 100k, Resistor R2
410k, Capacitor C1 100nF, NPN Qi, Resistor R3 1k
(GENERATOR INPUT:

ENABLE. Drive NEW Ql through K3 fron C3. Add Cl to SENSOR V.
Expected check: The analog threshold resets or gates the digital counter.
C50 - Ripple divider alarm timer
Reablfe example: Delay an alarm using ripple divider and latch
Functional components (10): 4040 U1, 74HC74 U2, NAND gate G1, AND gate G2, NOT gate G3, Resistor R1 10k, Capacitor C1
100nF, Electrolytic capacitor EC1 47uF, NPN Q1, Resistor R2 1k
(GENERATOR INPUT:
Expected check: Alarm output latches after the delay count expires.
C51 - Parallel load countdown timer
Real-life example: Load a preset time and count down to zero.
Functional components (9): 74HC192 U1, 74HC8S U2, NOR gate G1, AND gate G2, OR gate G3, Resistor R1 10k, Capacitor C1
400nF, NPN 1, Resistor R2 1k
(GENERATOR INPUT:
Expected check: The timer counts down from a preset BCD value and asserts DONE at zero.
C52 - Binary up/down service counter
Reablife example: Track service count with reset and overflow terminals.
Functional components (9): 74HC193 U1, 74HC273 U2, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 10k, Capacitor C1
100nF, NPN 1, Resistor R2 1k
(GENERATOR INPUT:
Expected check: The current count can be saved into a register and exposed as stored outputs

Page 14 of 18


## Page 15


C53 - Oscillator-divider watchdog enable
Real-life example: Use divider output to periodically refresh a watchdog node.
Functional components (11): 4060 Ut, 74HC74 U2, AND gate G1, OR gate G2, NOT gate G3, Resistor R1 100k, Resistor R2 10k,
Capacitor C1 100nF, Capacitor C2 10nF, NPN Q1, Resistor RQ 1k
(GENERATOR INPUT:

Capacitor €2 10nF, NPN Ql, Resistor A3 1k. Configure 4060 UI oscillator with Rl, R2, Cl, and
Expected check: A period divider tick sets a watchdog enable latch
C54 - Shift-register input logger
Reablfe example: Capture eight parallel bits and shift them to a status register.
Functional components (10): 74HC165 U1, 74HC595 U2, XOR gate G1, AND gate G2, OR gate G3, Resistor R1 10k, Capacitor
C1 100nF, Capacitor C2 10nF, NPN QI, Resistor R2 tk
(GENERATOR INPUT:
Expected check: Parallel inputs are serialized and re-expanded into alogged output register.
C55 - Combinational control feeding synchronous counter
Real-life example: Use gate logic to qualify a counter clock and reset.
Functional components (10): 74HC160 U1, AND gate G1, OR gate G2, NOR gate G3, NAND gate G4, NOT gate GS, Resistor R1
410k, Capacitor C1 100nF, NPN G1, Resistor R2 1k
(GENERATOR INPUT:

NeW Q2, ‘Resistor Re Ik. Use AND gate Cl to conbine SHNGOR OK and RUN ENABLE. Use OR gate c2
Expected check: The BCD counter counts only when several safety conditions are satisfied.

Pago 15of 18
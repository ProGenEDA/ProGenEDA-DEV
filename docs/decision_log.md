# Decision Log

Status: **reset to stable pre-CEP scope**.

This file preserves only stable project decisions confirmed before the speculative Project 2 Level 1 trial sequence.

## D001: Use terminal-based topology first

Decision: prefer terminal/net-label based connections before attempting arbitrary routed wiring.

Reason:

- Same-name terminals are intended to act as virtual connections in Proteus.
- Terminal labels were confirmed to be represented in ROOT.DSN.
- This reduces early generation complexity.

## D002: Treat ROOT.DSN as visual/topology authority

Decision: generation must handle ROOT.DSN for visible objects and topology.

Evidence:

- CDB-only extra resistor entries did not create visible components.
- DSN with additional visible resistors opened even when CDB was incomplete.
- Series/parallel transformations followed ROOT.DSN.

## D003: Treat ROOT.CDB as component metadata authority

Decision: ROOT.CDB matters for polished metadata such as resistor refs and values.

Evidence:

- CDB-only resistor value/ref edits were authoritative.
- DSN-only resistor value/ref edits were normalized back from CDB.

## D004: Patch both PROJECT.XML and ROOT.DSN version fields when targeting Proteus 8.13

Decision: target-version normalization requires both PROJECT.XML and ROOT.DSN header fields.

Evidence:

- PROJECT.XML-only patch did not remove the later-version warning.
- ROOT.DSN header patch at offsets 167/169 removed the warning in the repack control.

## D005: Use E001 empty project as the default clean base only when generation resumes

Decision: prefer the user-provided E001 empty project as base because it is known-good Proteus 8.13.

Reason:

- It has clean PROJECT.XML metadata.
- It has clean ROOT.DSN version fields.
- It has minimal ROOT.CDB.

## D006: Keep composed 74HC08 rendering gated on a clean D05 oracle

Decision: expose the AND reference circuit in CircuitIR and generate only validated whole-template outputs until `HC08_D05_exact_picture_manual_control.pdsprj` is supplied and passes Proteus 8.13 comparison testing.

Evidence:

- D01-D03 are clean donor projects but do not include the target pull-up/pull-down resistor rails.
- The previous file labelled `G04_FINAL_picture_circuit_full_cdb` is byte-equivalent to D03 and is not the target circuit.
- Arbitrary `ROOT.DSN` composition was the suspected source of prior ISIS failures.

## D007: Use donor-derived power bridge for resistor V9 power nodes

Decision: the main resistor generator must connect power with one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge and leave powered resistor endpoints as ordinary `$TERINPUT(V0)` terminals. Ground stays as `$TERGROUND(G0)` on right endpoints with the normal short wire.

Evidence:

- `memory/final/power_bridge_ground_shortwire_method.md` records the user-confirmed clean 6R and R21 bridge/ground attempts.
- The promoted generator reproduces `CLEAN_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE` `ROOT.DSN` and `ROOT.CDB` byte-for-byte.
- The regenerated 15 requested resistor circuits passed static validation and guarded Proteus 8.13 Wine open-smoke checks without early loader exits.

## D008: Disable standalone visual wires and stretch dense resistor layouts

Decision: production resistor generation must skip `layout.visual_wires` and stretch dense manual component coordinates to the safe V9 grid until standalone wire records are validated from a Proteus-created donor.

Evidence:

- The user reported VGDVC.dll failures beginning with the parallel generated circuit, matching the first requested cases that emitted experimental standalone visual wires.
- The safe-layout batch generated all 15 requested resistor circuits with `visual_wire_count=0`, recorded skipped visual wires in manifests, and stretched dense positions where required.
- All 15 safe-layout outputs stayed alive through guarded Proteus 8.13 Wine open-smoke and none of the captured stderr logs contained `VGDVC`.
- After user visual acceptance, vertical safe spacing was increased from `1524000` to `2540000` internal units so stacked divider components have more distance between component/terminal groups without changing terminal-to-component offsets.

## D009: Lock resistor generator as the main generator path

Decision: the spacing-adjusted V9 resistor generator is the main accepted resistor generator for the current scope. Development now moves to capacitor support.

Evidence:

- The main CLI path imports `src/proteusgen/resistor_v9.py`.
- The 15 spacing-adjusted locked-method outputs generated with zero static validation issues.
- OBJECT DATA audit confirmed one `$TERPOWER` bridge, `$TERINPUT` resistor power endpoints, `$TERGROUND` right ground endpoints, and zero emitted standalone visual wires.
- The user reported that the checked generated projects gave no errors and matched the requested circuits.

## D010: Keep capacitor in temporary diagnostics until Proteus acceptance

Decision: capacitor generation is not main yet. The first capacitor pass uses a temporary V4 diagnostic pack with exact donor reproduction guards before any patched or duplicated capacitor record is considered.

Evidence:

- Previous V2/V3 capacitor attempts produced Proteus VGDVC/library errors and remain negative evidence.
- The V4 script verifies that generated one-cap `ROOT.CDB` matches CAP_T01 byte-for-byte.
- The V4 script verifies that a generated terminal-cap-terminal object chunk matches CAP_T02 byte-for-byte.
- Static generation produced five ordered diagnostics with zero static validation issues, but manual Proteus testing is still pending.

## D011: Use cap3 free capacitor records before retrying terminal-attached multi-cap generation

Decision: after V4 T05 failed, the capacitor lane moves to the user-supplied `cap3.pdsprj` donor and isolates free capacitor CDB/object expansion before reintroducing endpoint terminals and wires.

Evidence:

- User reported V4 T04 opened and V4 T05 gave a Proteus error.
- `cap3.pdsprj` contains three capacitor CDB records and three free capacitor visual records without terminal endpoint groups.
- V5 reproduces the `cap3` `ROOT.CDB` and object chunk byte-for-byte before generating two-cap and translated/renamed three-cap diagnostics.
- This suggests the next unknown is multi-cap free-record acceptance, not resistor-style terminal-group duplication.

## D012: Reintroduce capacitor terminals only after V5 free-cap acceptance

Decision: user acceptance of all V5 cap3 diagnostics confirms free multi-cap CDB/object generation. Terminal-attached capacitor topology remains experimental and must be tested with V6 variants before promotion.

Evidence:

- User reported all V5 diagnostics work.
- V4 T05 remains negative evidence for naive duplicated terminal-cap-terminal groups.
- V6 generates terminal/free coexistence tests first, then two-terminal-cap variants with different suffix families and object orders.

## D013: V6 terminal reintroduction rejected; isolate from V4 T04 baseline

Decision: V6 is rejected as negative evidence. The next terminal-attached capacitor diagnostics must start from a byte-exact reproduction of the known-opening V4 T04 single terminal-cap object chunk, then change one variable at a time.

Evidence:

- User reported all V6 cases gave VGDVC errors.
- Local audit found terminal-last V6 variants appended an extra final FF byte instead of replacing the final wire terminator.
- V7 T01 object chunk matches V4 T04 byte-for-byte, so it is the new sanity gate.

## D014: Test V9-style ordering for multiple terminal-attached capacitors

Decision: V7 is mixed evidence, not promotable. V8 must test multiple terminal-attached capacitors using the accepted resistor V9 ordering: all input terminals, all output terminals, one separator byte, then component/wire groups.

Evidence:

- User reported V7 T01, T02, T03, and T05 worked.
- User reported V7 T04 and T06 failed.
- User screenshot for V7 T07 showed the file opened but only a partial two-terminal-cap circuit appeared, with C1 plus a dangling/partial N4 side.
- V7 T05 working while T04 failed means free capacitor records can coexist with a terminal-attached capacitor only in the observed free-first/terminal-last order so far.
- V7 T07 partially opening suggests object ordering is closer than sequential duplicated groups but still missing the V9 separator/layout pattern.

## D015: V8 rejects synthesized two-terminal-cap ordering

Decision: do not keep guessing at multi terminal-attached capacitor composition from one-cap donors. Start deeper VGDVC/DLL/log and user-corpus analysis, and request a real manually made two-terminal-cap donor if the current corpus does not contain one.

Evidence:

- User reported only V8 T01 worked.
- V8 T01 is the V7 T05 reproduction: one free capacitor before one terminal-attached capacitor.
- V8 T02-T06 all attempted two terminal-attached capacitors using V9-style ordering, suffix variants, CDB flag variants, and vertical staggering; all failed according to user.
- This means the safe capacitor method currently covers free multi-cap records and a single terminal-attached capacitor, not two synthesized terminal-attached capacitor groups.

## D016: Test unique capacitor visual index byte for terminal-attached multi-cap

Decision: V9 must test the concrete byte-level bug found after V8: every duplicated terminal-attached capacitor copied the donor cap visual index byte 344 as `1`, while accepted free multi-cap records patch that byte to `1, 2, 3`.

Evidence:

- `cap3` accepted free-cap records have byte 344 values `1, 2, 3`.
- `CAP_V7_T06`, `CAP_V7_T07`, and `CAP_V8_T02` failing/partial terminal-cap variants had byte 344 equal to `1` in both C1 and C2 cap visual records.
- This duplicate hidden visual index explains the observed partial rendering better than suffix/order alone.
- V9 T02 is the minimal V7 T06 shape with only the terminal-attached capacitor visual indexes corrected to `1, 2`.

## D017: Lock mixed resistor/capacitor passive generation

Decision: promote mixed resistor/capacitor passive generation into main code for the current scope.

Evidence:

- User accepted the mixed 6-component and 21-component diagnostics with odd-indexed components as resistors and even-indexed components as capacitors.
- The accepted method uses one donor-derived `$TERPOWER -> $TEROUTPUT(V0)` bridge and `$TERGROUND(G0)` right endpoints.
- Static checks for the locked main pack produced no object-count, CDB-marker, suffix, or terminator issues.
- The full Python suite passed after promotion.

Implementation:

- Main code: `src/proteusgen/mixed_passive.py`.
- Input parser: `src/proteusgen/mixed_passive_ir.py`.
- CLI: `proteusgen generate-mixed-passives`.
- Spacing was reduced from the temporary `3810000` grid to the locked `2540000` safe grid. Duplicate manual positions are shifted so components are never emitted on top of each other.

## D018: Keep topology-aware beautification opt-in until Proteus acceptance

Decision: add one shared deterministic layout planner before binary emission,
but keep `legacy` as the omitted-strategy default until the representative
legacy-versus-beautified pack passes manual Proteus testing.

Evidence:

- The planner changes coordinates only and keeps all record construction inside
  the accepted route emitters.
- Automated tests verify deterministic output, exact manual placement, legacy
  DSN/CDB parity, branch separation, seven-slot wrapping, source proximity, and
  zero beautified placement overlaps.
- Eleven representative legacy/beautified pairs generate with clean static
  validation and identical `ROOT.CDB` files within each pair.
- Manual Proteus open, visual, and simulation testing is still pending, so this
  evidence is not sufficient to change the production default.

## D019: Correct source geometry and prefer repeated-node continuity

Decision: retain V1 as historical evidence and issue a focused V2 pack for
source clearance, complete AC-source translation, and repeated-label lane
continuity.

Evidence:

- User reported V1 was very good overall, but two sources could overlap and the
  AC source body was far from its terminals with long visual connections.
- Record inspection found that V1 translated AC terminal and wire coordinates
  but omitted the `VSINE` body and visible value coordinate fields.
- V2 translates those fields, uses a dedicated source column with `5080000`
  anchor clearance, and follows directed CircuitIR endpoint order when deriving
  levels and lanes.
- Static V2 checks show zero overlaps, unchanged record identities and CDB
  bytes, compact AC body-to-anchor offsets, and one-lane continuity for repeated
  series node labels. Manual Proteus testing remains pending.

## D020: Promote the accepted V2 beautifier as the default

Decision: lock the exact V2 placement algorithm into production. Omitted layout
uses `beautify`; payloads with explicit positions but no strategy use `manual`;
explicit `legacy` remains available.

Evidence:

- The user confirmed the focused V2 projects worked and explicitly approved
  locking the exact code.
- V2 separates multiple sources, keeps AC source records together, and prefers
  same-name node continuity without changing electrical record identities.
- The existing full automated suite passed before promotion, including legacy
  parity, deterministic placement, source clearance, wrapping, and overlap
  checks.

## D021: Test bidirectional terminals through endpoint-record substitution

Decision: keep production input/output terminal emitters unchanged while testing
one generic temporary conversion stage. Replace only ordinary `$TERINPUT` and
`$TEROUTPUT` records with donor-derived `$TERBIDIR` records; preserve special
power/ground terminals, components, sources, wires, labels, coordinates, object
order, and endpoint suffix links.

Evidence:

- The user supplied 27 Proteus 8.13 projects covering empty 0/180-degree
  terminals, 1/2/4 scaling, resistor/capacitor/inductor/RCL circuits, DC voltage,
  DC current, two-source, and AC-voltage cases.
- All 170 bidirectional terminal records reconstruct byte-for-byte from two
  empty orientation templates plus label, coordinates, suffix, and active-link
  state.
- The V1 pack converts ten current-generator outputs with zero remaining
  ordinary terminal markers, unchanged component/source/wire marker counts,
  unchanged suffix occurrence counts, and clean static validation.
- Manual Proteus open and simulation testing is still required before promotion.

## D022: Correct bidirectional orientation and rebuild DCV from clean units

Decision: retain V1 as historical evidence and issue a focused V2 experiment.
Map ordinary outputs to the 0-degree bidirectional donor and ordinary inputs to
the 180-degree donor. For DC voltage sources, append complete clean
bidirectional source units and emit source-specific CDB pin mappings instead of
converting the older malformed source output.

Evidence:

- The user reported every V1 case except two-DCV T09 worked, but V1 displayed
  only 0-degree bidirectional terminals.
- The supplied passive and source donors consistently use 0 degrees on ordinary
  output-role endpoints and 1800 tenths on input-role endpoints.
- The supplied one- and two-DCV projects encode each voltage source CDB row as
  `+ -> 1` and `- -> 2`; V1 instead encoded voltage sources as passive `1/2`
  parts, explaining the repeatable bad-object warning.
- T09 also contains two disconnected negative nets. V2 keeps that topology as a
  diagnostic and adds a shared-negative case to distinguish binary-record
  validity from a SPICE singular-matrix failure.
- Production remains unchanged pending manual V2 acceptance.

## D023: Require one broad pre-lock bidirectional regression pack

Decision: treat the focused V2 method as manually confirmed, but delay
production promotion until one expanded pack covers scale, topology, every
passive family, DC current, AC voltage, and one through three DC voltage
sources.

Evidence:

- The user reported every V2 case worked, including the true 180-degree
  resistor endpoint, one clean DCV source, isolated two-DCV topology, and
  shared-negative two-DCV topology.
- V3 reuses the exact V2 conversion and clean-DCV functions; it does not
  reconstruct the accepted method.
- Eleven V3 cases cover a 20-resistor mesh, six-component R/C, capacitor-only,
  inductor-only, Wheatstone, corrected 21-component RCL, DC current, AC voltage,
  one-DCV bridge, larger two-DCV, and three-DCV circuits.
- Static checks show zero ordinary endpoint records, role-correct bidirectional
  angles, zero layout overlaps, valid source CDB rows and links, deterministic
  output, and a clean existing regression suite.

## D024: Promote V3 bidirectional endpoints and compact the beautifier grid

Decision: make the exact user-confirmed V3 endpoint method the production
default across resistor, mixed-passive, mixed-RCL, and source-driven routes.
Ordinary input/output records are no longer emitted. Keep power and ground
special terminals, use donor-native bidirectional DCV units, and reduce only
the component layout grid to `3175000` horizontal by `2032000` vertical units.

Evidence:

- The user confirmed all eleven V3 projects opened, rendered, and simulated.
- V3 covered R, C, L, RC, RCL, bridge, 21-component, DCI, ACV, and one through
  three DCV cases.
- The production implementation copies the accepted V3 helpers into the
  package and runs conversion only at the final object-stream boundary.
- Multi-source clearance remains `5080000`; the denser component grid passes
  deterministic placement and overlap checks.

## D025: Start IC generation with donor learning, not production emission

Decision: keep IC support in the temporary `proteus_ic` workspace until the
generated IC packs pass Proteus open, save/reopen, and simulation checks. Use
ordinary input/output terminals for IC pins, preserve hidden IC supply behavior,
and reject DC/AC source components for IC generation.

Evidence:

- The imported HC08 all-four donor contains four `74HC08` subpart symbols,
  eight `$TERINPUT` records, four `$TEROUTPUT` records, twelve short wires, and
  no `$TERBIDIR` records.
- The imported HC08 two-package donor contains `U1:A` and `U2:A` package rows,
  which makes it the first package-scaling control.
- The imported HC32 all-four donor is a true `74HC32`/`74OR2.MDF` donor, while
  the supplied HC32 single-gate file internally contains `74HC08`/`74AND2.MDF`
  and is rejected as HC32 evidence.
- The imported HC08 RCL-load donor contains `$TERBIDIR` records in the passive
  load section, so it is diagnostic only under the IC no-bidirectional-terminal
  rule.

## D026: Accept V1 HC08/HC32 donor-learning pack as the IC baseline

Decision: treat `IC_HC08_HC32_V1_TEMP_2026_06_07` as the accepted baseline for
ordinary-terminal quad two-input gate donor transforms. This unlocks the next
temporary step: a production-style HC08 pack that composes requested gate counts
from complete accepted donor records. It does not yet promote production IC
generation into the main generator.

Evidence:

- The user reported all V1 cases worked in Proteus.
- V1 covered exact donor repack, E001 transplant, repeated transplant,
  all-four HC08 transplant, label-only HC08 mutation, two-package HC08 control,
  two-package label mutation, HC08 power/ground logic constants, diagnostic HC08
  RCL load transplant, HC32 all-four transplant, and HC32 label-only mutation.
- Pure IC cases use ordinary input/output terminals and zero `$TERBIDIR`
  records; the only `$TERBIDIR` case remains explicitly diagnostic.
- The HC32 single-gate donor remains rejected as HC32 evidence because its
  internal records are HC08/AND records.

## D027: Normalize 74HC08 DIP pin descriptions before IC generation

Decision: allow users to describe `74HC08` circuits using ordinary DIP14 pin
language, but normalize that input before CircuitIR/generation. Drop pin 14/VCC
and pin 7/GND as hidden IC supply connections, then map signal pins to the
accepted Proteus subparts.

Evidence:

- User supplied five representative `74HC08` circuits: pure gate 1 AND, gate 1
  RC input delay, gate 2 LC output filter, gate 3 RLC input filter, and gate 4
  dual-RC timing window.
- Proteus donor learning confirmed visible IC symbols are subparts such as
  `U1:A`, `U1:B`, `U1:C`, and `U1:D`, not one full DIP14 package.
- The normalized pin rule is now captured in `proteus_ic/registry/74hc08.json`,
  `proteus_ic/docs/74hc08_user_input_rules.md`, and
  `src/proteusgen/ic_pinmap.py`.
- The rule fails closed on unsupported pins; only known hidden supply pins are
  ignored.

## D028: Split IC terminal policy and start AND-expression synthesis

Decision: keep ordinary `$TERINPUT`/`$TEROUTPUT` records only for IC signal
pins. In mixed IC/passive circuits, R/C/L endpoints must use the accepted
donor-derived bidirectional terminal method, while power/ground terminals keep
their special accepted handling. Start Boolean expression synthesis with an
AND-only parser that maps reductions onto `74HC08` subparts.

Evidence:

- The user confirmed all five `IC_HC08_REAL_V1_TEMP_2026_06_07` production-style
  HC08 circuits worked in Proteus.
- User clarified that only IC pins should remain ordinary input/output
  terminals; non-IC endpoints must follow the bidirectional production policy.
- `src/proteusgen/logic_expression.py` now parses AND-only expressions and
  builds deterministic two-input reduction trees.
- The user confirmed `IC_HC08_LOGIC_V1_TEMP_2026_06_08` worked in Proteus for
  the requested 15-input AND expression as fourteen `74HC08` gates across four
  packages.

## D029: Keep compact mixed-IC layout, reject passive G0 as bidirectional

Decision: keep IC pins directional and keep passive G0 on the previous donor
`$TERGROUND` method. The passive-G0-as-`$TERBIDIR` experiment failed for T29,
so it must not be promoted. Compact small mixed-IC placement is accepted only
with legacy ground restored.

Evidence:

- The user reported the final 30 combinational IC acceptance pack worked, then
  requested a compacting pass for small IC/passive circuits and bidirectional
  ground handling.
- `IC_FINAL_LAST2_LAYOUT_GROUND_V2_TEMP_2026_06_08` regenerated T29 and T30
  with passive G0 converted to `$TERBIDIR`.
- User testing reported T29 failed and T30 worked. T30 did not exercise a
  passive G0 endpoint, so this rejects the passive-G0 conversion, not the
  compact placement.
- `IC_FINAL_T29_LEGACY_GROUND_V3_TEMP_2026_06_08` restores `$TERGROUND(G0)`
  while keeping the compact small-circuit placement.
- User testing reported the V3 T29 retest worked. It preserves
  `$TERINPUT`/`$TEROUTPUT` for IC pins, keeps ordinary R/C/L endpoints as
  `$TERBIDIR`, and emits one `$TERGROUND` record for passive G0.
- Active tests pass with `python -m pytest tests -q`.

## D030: Add 74HC04 as unary inverter subparts

Decision: treat `74HC04` as a hex unary inverter family using subparts
`U1:A` through `U1:F`, not as an explicit DIP14 supply-pin object. The visible
function model is `74INV.MDF`; pin 14/VCC and pin 7/GND remain hidden-supply
metadata and are ignored during generation.

Evidence:

- User supplied five `74HC04` donors: one gate, all six gates, two packages,
  logic constants, and RCL load.
- Donor analysis shows `74HC04` records use `74INV.MDF`, six subparts, and one
  signal input plus one signal output per subpart.
- The manual HC04 input terminal labels are one-character labels, so the
  temporary generator uses a dedicated resizable label patch for HC04 only.
- `IC_HC04_ALL7_V1_TEMP_2026_06_08` is static-clean and active-tests-clean. It
  covers single NOT, all-six NOT, logic constants, NOT with RCL load, and the
  final all-seven-family circuit.
- User testing reported the full HC04/all-seven pack worked.
- `src/proteusgen/ic_combinational.py` promotes the accepted donor-derived
  route into the main CLI as `generate-ic-combinational`.
- The production smoke regenerated the accepted all-seven circuit and direct
  15-input AND/OR gate JSON through the main CLI with zero static issues; the
  AND/OR object and CDB hashes match the earlier accepted expression packs.

## D031: Reject standalone mixed wires and require native attachment units

Decision: reject `MIXED/short-wire-v6-temp`. Mixed terminal attachment must
serialize each wire as part of the accepted native attachment unit: active
terminal suffix, matching active component pin-link suffix, and donor-derived
WIRE records immediately beside the patched component. Keep all six researched
families in the shared terminal placer.

Evidence:

- The user reported V6 still raised Bad Object Record and rendered no wires.
- The accepted `RESISTOR/v3` stream proves that its patched component is
  immediately followed by two 50-byte wire records; the terminal and component
  carry the same active suffix.
- V7 reproduces the accepted three-component object chunk byte-for-byte for
  RESISTOR, CAP, CAP-ELEC, REALIND, VSOURCE, and CSOURCE.
- V7 mixed 1x/3x/15x static checks pass with DIODE, NPN, and 74HC08 preserved
  and terminal-free. Mixed Proteus acceptance remains pending.

## D032: Rebase terminal links from final WIRE addresses

Decision: reject V7 mixed N07-N09 and do not replace them with a new runtime
donor/order. Preserve the beautified component stream. Encode terminal and
WIRE records from the known Proteus schema, serialize ROOT.DSN, and then write
both copies of every active link from the final WIRE address:

```text
(object_chunk_absolute_start + full_wire_marker_offset - 24) & 0xffff
```

Evidence:

- The user reported V7 N07, N08, and N09 failed.
- All 25 terminals in the accepted 4x RCL file and all 21 terminals in the
  accepted mixed-analog file satisfy the formula exactly.
- V7 N07 has twelve terminal/component suffix pairs and all twelve disagree
  with their final WIRE addresses.
- Regenerating N07 with the shared schema encoder changes only active link
  bytes; component packets, coordinates, WIRE geometry, and object length stay
  unchanged.

## D033: Snap terminal contacts to the Proteus grid

Decision: reject mixed V9. Preserve the component and its exact pin
coordinates, snap each terminal contact to the nearest `254000 x 254000`
Proteus grid intersection, and emit a short WIRE from the snapped contact to
the exact pin. Do not make beautification place components for the terminal
stage.

Evidence:

- The user reported every mixed V9 case failed.
- Manual placement showed that a terminal can be placed on the nearby grid and
  connected to an off-grid resistor/source pin with a short wire.
- Every terminal coordinate in accepted bidirectional source and mixed-analog
  files is divisible by `254000`; terminal contact is one grid unit from the
  stored terminal symbol coordinate.
- V10 keeps component packets in their beautified stream and validates every
  terminal symbol/contact grid coordinate and every contact-to-exact-pin WIRE.
- All V10 cases use the unchanged FUSE/POT-HG mega donor as component-placer
  input. The shared terminal placer and beautifier have no runtime donor-path
  dependency.

## Inactive / removed

The earlier post-CEP decisions about large speculative Project 2 Level 1 packs, no-DLD packs, and big-leap circuit assembly have been removed from active memory. Rebuild that direction only with explicit user guidance.

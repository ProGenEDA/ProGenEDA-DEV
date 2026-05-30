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

## Inactive / removed

The earlier post-CEP decisions about large speculative Project 2 Level 1 packs, no-DLD packs, and big-leap circuit assembly have been removed from active memory. Rebuild that direction only with explicit user guidance.

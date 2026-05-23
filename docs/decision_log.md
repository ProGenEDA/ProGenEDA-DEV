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

## Inactive / removed

The earlier post-CEP decisions about large speculative Project 2 Level 1 packs, no-DLD packs, and big-leap circuit assembly have been removed from active memory. Rebuild that direction only with explicit user guidance.

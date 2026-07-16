# Value & Properties Editor - V1

This pack validates the one shared post-terminal editor:
`src/proteusgen/component_value_changer.py` /
`edit_project_values_and_properties`.

It never edits terminal placement. Each mutation is an equal-byte-length,
numeric replacement made in both the selected `ROOT.DSN` packet and its
matching `ROOT.CDB` property row, so terminal records, WIRE records, and their
address-derived links remain unchanged.

## Artifacts

| Directory | Input and result | Coverage |
| --- | --- | --- |
| `00_authoritative_donor_grammar_probe` | Accepted terminalized user donor -> `ALL_CURRENT_GROUP_VALUES_PROPERTIES_sa.pdsprj` | Seven visible values plus `ESR`, `POS`, `GAIN`, and `RSC`; 67 terminals and 67 WIREs preserved. |
| `01_generated_native_two_pin_value_matrix` | Fresh current component placer -> beautifier -> shared terminal placer -> `V01_NATIVE_SIX_EDITABLE_VALUES_PROPERTIES_sa.pdsprj` | `RESISTOR`, `CAP`, `CAP-ELEC`, `REALIND`, `VSOURCE`, and `CSOURCE`, plus `REALIND.ESR`; 12 terminals and 12 WIREs preserved. |
| `03_cross_family_numeric_property_matrix` | Accepted terminalized user donor -> `ALL_CURRENT_GROUP_CROSS_FAMILY_NUMERIC_PROPERTIES_sa.pdsprj` | Diode/zener breakdown/current, LED forward voltage, NMOSFET geometry, potentiometer, inductor, op-amp, and LM317T numeric properties; 67 terminals and 67 WIREs preserved. |

All three outputs normal-opened and cold-reopened in local Proteus 8 after the
required delayed stability check, with no Bad Object Record, library dialog,
Fatal Error, or LXLCORE dialog. The `02_local_proteus_gate` copies are
disposable gate inputs and are intentionally not source artifacts.

## Current safe contract

Use reference-based JSON:

```json
{
  "values": {"R1": "47k", "C1": "2nF"},
  "properties": {"L1": {"ESR": "0.3"}, "RV1": {"POS": "75"}}
}
```

The new text must have exactly the same byte length as the current text. For
example, `10k -> 47k` is accepted, while `10k -> 100k` is rejected. Device
models, packages, loader properties, ambiguous fields, and the unproven
`VSINE`/`VPULSE` value grammar are rejected rather than guessed.

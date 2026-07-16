# Three-pin control terminal V20 full WIRE-unit shape repair

V20 is generated through `src/proteusgen/component_terminal_placer.py` only. It fixes the V19 rejection by preserving donor WIRE unit envelopes and full polyline point lists.

Proteus open/render status: pending user test. Static validation is not Proteus acceptance.

## Files to test
- `experiments\three_pin_control_terminal_v20_wire_unit_shape_temp_2026_07_09\01_terminalized_sa\R001_POT_HG_1x_WIRE_UNIT_SHAPE_sa.pdsprj`
- `experiments\three_pin_control_terminal_v20_wire_unit_shape_temp_2026_07_09\01_terminalized_sa\R002_LM317T_1x_WIRE_UNIT_SHAPE_sa.pdsprj`
- `experiments\three_pin_control_terminal_v20_wire_unit_shape_temp_2026_07_09\01_terminalized_sa\R003_OPAMP_1x_WIRE_UNIT_SHAPE_sa.pdsprj`

## Static gates
- no-terminal base comes from the locked new-components mega donor
- component stream before the first terminal differs only at documented component pin-link fields
- terminal labels, symbol coordinates, angles, trailers, and record sizes match donor evidence except rebased suffix bytes
- full WIRE unit records match donor evidence in order, including point count and all polyline coordinates
- final object chunk ends with explicit `ff ff`

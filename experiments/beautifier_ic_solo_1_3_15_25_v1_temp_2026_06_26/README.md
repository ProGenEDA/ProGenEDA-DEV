# IC Solo Beautifier Acceptance Pack

Generated on 2026-06-26.

This pack tests each IC family separately at 1x, 3x, 15x, and 25x.
There are no terminals or wires. The purpose is to prove bare packet selection
and coordinate mutation before any IC families are combined.

## Important

- D20 is not part of this IC pack and is now immutable everywhere.
- Each family has its own 25-packet byte profile in `ic_coordinate_research.json`.
- Similar-looking ICs are not assumed identical; packet sizes, subpart counts,
  coordinate counts, CDB backing, and finalization are checked per family.
- Every generated project contains a production `generated_output_validator`
  report in its manifest.

## Test Order

1. `BEAUTIFIER_74HC00_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC00` (donor inventory 123)
2. `BEAUTIFIER_74HC02_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC02` (donor inventory 121)
3. `BEAUTIFIER_74HC04_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC04` (donor inventory 120)
4. `BEAUTIFIER_74HC08_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC08` (donor inventory 150)
5. `BEAUTIFIER_74HC32_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC32` (donor inventory 120)
6. `BEAUTIFIER_74HC74_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC74` (donor inventory 120)
7. `BEAUTIFIER_74HC76_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC76` (donor inventory 120)
8. `BEAUTIFIER_74HC85_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC85` (donor inventory 120)
9. `BEAUTIFIER_74HC86_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC86` (donor inventory 120)
10. `BEAUTIFIER_74HC151_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC151` (donor inventory 120)
11. `BEAUTIFIER_74HC157_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC157` (donor inventory 120)
12. `BEAUTIFIER_74HC160_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC160` (donor inventory 120)
13. `BEAUTIFIER_74HC174_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC174` (donor inventory 120)
14. `BEAUTIFIER_74HC192_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC192` (donor inventory 120)
15. `BEAUTIFIER_74HC266_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC266` (donor inventory 120)
16. `BEAUTIFIER_74HC283_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `74HC283` (donor inventory 120)
17. `BEAUTIFIER_4027_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `4027` (donor inventory 150)
18. `BEAUTIFIER_4511_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `4511` (donor inventory 120)
19. `BEAUTIFIER_7447_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `7447` (donor inventory 120)
20. `BEAUTIFIER_7490_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `7490` (donor inventory 120)
21. `BEAUTIFIER_LM741_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `LM741` (donor inventory 600)
22. `BEAUTIFIER_NE555_COORDINATE_PROBE_IC_SOLO_V1_TEMP_2026_06_26.zip` - `NE555` (donor inventory 120)

## Inside Each Family ZIP

- one beautified 1x project
- one beautified 3x project
- one beautified 15x project
- one beautified 25x project
- payload JSON, manifest, byte probe, summary, and inspection notes

For each family, report the first failing count and whether Proteus crashed,
showed a DLL/bad-object error, detached text, wrong package/subpart count,
or failed simulation startup.

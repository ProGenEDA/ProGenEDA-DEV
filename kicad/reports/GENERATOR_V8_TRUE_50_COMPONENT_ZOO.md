# KiCad generator V8 — true 50-component visual smoke sheet

## Why this exists

V7 only proved the component catalog and repeated the already verified symbols.  That was not enough.  The requested target is a real KiCad project containing about 50 unique component kinds together so the visual backend can be tested at scale.

## V8 deliverable

V8 adds a generator for one all-together KiCad schematic containing exactly 50 unique component kinds:

1. VDC
2. VSIN
3. R
4. L
5. C
6. CP
7. R_POT
8. FERRITE
9. FUSE
10. PTC
11. MOV
12. TVS
13. D
14. LED
15. ZENER
16. SCHOTTKY
17. BRIDGE
18. VPULSE
19. VAC
20. IDC
21. ISIN
22. IPULSE
23. NPN
24. PNP
25. NMOS
26. PMOS
27. JFET_N
28. JFET_P
29. OPAMP
30. LM741
31. LM358
32. LM393
33. NE555
34. L7805
35. LM317
36. 74HC00
37. 74HC04
38. 74HC08
39. 74HC32
40. 74HC86
41. 74HC74
42. 74HC76
43. 74HC90
44. 74HC157
45. 74HC192
46. 4511
47. 4017
48. CONN_2
49. CONN_3
50. CONN_4

## Important honesty

Only the already proven stock KiCad symbols are treated as verified upstream-stock embedded symbols:

- `Simulation_SPICE:VDC`
- `Simulation_SPICE:VSIN`
- `Device:R`
- `Device:L`

The other 46 components are rendered with project-local `Progen50:<kind>` generic symbols.  This is intentional: it proves KiCad parsing, placement, project-local symbol embedding, and pin-endpoint wiring for the 50-kind scale test without lying that all stock KiCad symbol-cache blocks have already been extracted.

## Next promotion rule

Each generic symbol must be promoted to a real stock KiCad symbol only after donor/source extraction confirms:

1. exact `lib_symbols` cache block;
2. exact pin numbers;
3. exact pin endpoint coordinates;
4. one GUI-open test;
5. one generated smoke-test project.

## Generator file

`kicad/generator/component_zoo_50_generator.py`

## Expected output folder

`all_50_unique_components_together/`

Open:

```text
OPEN_THIS_FIRST__OPEN_THIS_PROJECT__v8_50_unique_components_together__PROJECT_FILE__PROJECT_FILE.kicad_pro
```

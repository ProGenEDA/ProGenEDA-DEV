# Stress And Limit Suite V1

Date: 2026-07-01

## What Was Tested

Generated the requested stress and limit suite:

- Test 1 through Test 10.
- Limit A through Limit D.
- Limit E at 25, 50, 75, 100, 150, 200, 300, and 400 components.

## Outcome

Historical failed direction.

- 22 schematics generated.
- 2747 requested components.
- 20 passed KiCad quality.
- 2 failed KiCad quality: `LIME050` and `T10`.

The failures were useful: they showed that the placer grid was still too tight
for real large symbols, causing pin-overlap ERC blockers between adjacent-row
symbols.

## Next

Superseded by:

```text
kicad/examples/placer_run_2026_07_01_stress_limit_suite_v2
```

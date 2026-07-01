# Mixed terminal append-overlay V3 temporary pack

The previous V1 pack failed because it rebuilt independently accepted family
blocks into a new mixed object order. This V3 pack uses the older order that
the user confirmed opened successfully:

`beautified component stream -> appended terminals -> appended wires`

The component stream stays first and keeps its original component order.
Accepted RESISTOR, CAP, REALIND, CAP-ELEC, VSOURCE, and CSOURCE link fields are
patched in place. DIODE, NPN, and 74HC08 remain byte-preserved and terminal-free.

The beautifier now places 74HC08 on an upper IC band and all non-IC components
on a lower band with 5,080,000 internal units of clearance.

## Test in order

1. `T00`: exact-copy all-bare control; inspect IC/non-IC separation.
2. `T01`: appended terminals only. This reproduces the historically opening
   record order but deliberately leaves terminals unattached.
3. `T02`: intended temporary fix: all six accepted families attached with
   donor-derived wire records.
4. `T03`: passive-only attachment ablation.
5. `T04`: source-only attachment ablation.

Report open, render, attachment, and simulation separately for every case.
T01 is a positive order control, not the desired final attachment result.

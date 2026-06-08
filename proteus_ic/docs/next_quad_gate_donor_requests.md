# Next Quad-Gate Donor Requests

Accepted baseline before these donors:

- IC package supply pins are hidden. Do not wire physical pin 14 or pin 7 as IC supply.
- IC signal inputs use input terminals.
- IC signal outputs use output terminals.
- R/C/L and other passive endpoints use bidirectional terminals.
- Same-name input, output, and bidirectional terminal labels connect in Proteus.
- Power and ground terminals are only logic HIGH/LOW ties or passive references.

For each new two-input quad family, make the same donor shapes. Keep terminal
labels short ASCII, ideally two characters where possible.

## Families

Required:

- `74HC00`: quad 2-input NAND.
- `74HC02`: quad 2-input NOR.
- `74HC86`: quad 2-input XOR.

XNOR:

- Use the exact XNOR part that exists in your Proteus library.
- Prefer a quad 2-input XNOR if available, commonly named `74HC266` or
  `74HC4077` depending on library support.
- If both exist, make donors for both and we will choose the cleaner one.

## Donor Set Per Family

Use these filenames, replacing `HCxx` with the family name, for example
`IC_HC00_M01_ONE_GATE_IO.pdsprj`.

1. `IC_HCxx_M01_ONE_GATE_IO.pdsprj`
   - One package, gate A only.
   - Input terminal `A0` to input 1.
   - Input terminal `B0` to input 2.
   - Output terminal `Y0` from output.
   - No explicit pin 14 or pin 7 supply wiring.

2. `IC_HCxx_M02_ALL4_IO.pdsprj`
   - One package, all four gates A/B/C/D.
   - Gate A: `A0`, `B0` -> `Y0`.
   - Gate B: `A1`, `B1` -> `Y1`.
   - Gate C: `A2`, `B2` -> `Y2`.
   - Gate D: `A3`, `B3` -> `Y3`.
   - No explicit pin 14 or pin 7 supply wiring.

3. `IC_HCxx_M03_TWO_PACKAGES_IO.pdsprj`
   - Two packages of the same family.
   - At least gate A on each package.
   - Package 1 gate A: `A0`, `B0` -> `Y0`.
   - Package 2 gate A: `A1`, `B1` -> `Y1`.
   - This proves package-reference scaling.

4. `IC_HCxx_M04_LOGIC_CONSTANTS_PG.pdsprj`
   - One package, at least two gates.
   - Tie one input HIGH using a power terminal label such as `V0`.
   - Tie one input LOW using a ground terminal label such as `G0`.
   - Outputs use ordinary output terminals.
   - This proves power/ground are logic constants only.

5. `IC_HCxx_M05_RCL_LOAD.pdsprj`
   - One gate output drives an R-C-L load.
   - IC pins remain input/output terminals.
   - R/C/L endpoints are bidirectional terminals.
   - Same output label, for example `Y0`, should connect the IC output terminal
     to the first passive bidirectional endpoint.

## Minimum If You Want To Move Fast

If time is tight, make only these first for each family:

- `M02_ALL4_IO`
- `M03_TWO_PACKAGES_IO`
- `M05_RCL_LOAD`

That should usually be enough to extract all four gate subparts, learn package
scaling, and prove mixed passive connectivity.

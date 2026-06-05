MIXED_RCL_V9_RL_BOUNDARY_TEMP_2026_06_01

Open in order and stop at the first case that works after a failing control:
1. T01-T02: minimal R+L no-power order controls.
2. T03-T07: R+L no-power index/suffix hypotheses.
3. T08: connected-label R+L no-power check.
4. T09-T10: add capacitor only after R+L hypotheses.
5. T11: add V0/G0 only after an all-terminal R+L/C result works.

If T01-T08 all fail, the next required evidence is a Proteus-created manual donor containing a terminal-attached resistor and terminal-attached inductor in the same project.

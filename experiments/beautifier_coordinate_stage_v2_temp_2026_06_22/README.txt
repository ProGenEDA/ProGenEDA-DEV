Beautifier coordinate stage V2 test pack

Open each .pdsprj in order. Each case folder has WHAT_TO_CHECK.txt.
The rejected pruned-CDB/CDB-slice variant is intentionally not included.
If a hidden case opens, verify the requested components remain visible while only the infrastructure dummy is moved away.

Cases:
- B00_CONTROL_METADATA_ONLY: Baseline control case. It should open/simulate. The manifest should mark one extra SWITCH and one extra POT-HG as hidden dummy controls, but this case does not move their binary coordinates.
- B01_SWITCH_DUMMY_LINKED_RELATIVE: SWITCH-only hiding check. One requested switch should remain usable/visible; the extra dummy switch should be moved away by the beautifier coordinate stage.
- B02_POTHG_DUMMY_LINKED_RELATIVE: POT-HG-only hiding check. One requested potentiometer should remain usable/visible; the extra dummy POT-HG should be moved away by the beautifier coordinate stage.
- B03_SWITCH_AND_POTHG_DUMMIES_LINKED_RELATIVE: Combined control hiding check. Both requested controls should remain visible/usable, while the first extra SWITCH and first extra POT-HG are moved away.
- B04_DISPLAY_D20_VISIBLE_CONTROL: Display bridge control. This intentionally keeps the D20 bridge visible. You should see one user-requested diode plus the D20 display bridge infrastructure, and one anode plus one cathode 7-segment display.
- B05_DISPLAY_D20_HIDDEN_LINKED_RELATIVE: D20 hiding check. The requested diode and both displays should remain visible. The D20 bridge should be moved away by the beautifier coordinate stage.
- B06_CONTROLS_AND_DISPLAY_HIDDEN_LINKED_RELATIVE: Full hidden-infrastructure check. The requested SWITCH, POT-HG, diode, and displays should remain visible. The extra SWITCH/POT-HG and D20 bridge should be moved away.
- B07_WIRING_PLAN_LAYOUT_ONLY_NO_BINARY_MOVE: Layout-plan-only case. This does not move binary coordinates. Check the manifest wiring_plan and layout_plan: same-net groups should list A/Y1/LOAD and the beautifier should produce deterministic placements.

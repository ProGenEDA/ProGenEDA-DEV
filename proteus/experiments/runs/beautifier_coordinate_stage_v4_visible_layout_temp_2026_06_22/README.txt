Beautifier coordinate stage V4 visible-layout test pack

This evolves the V3 script. It still calls the actual component placer generator.
Open the small_controls cases first, then spot-check large_rules_01_30 and large_rules_31_60.
Every case folder has WHAT_TO_CHECK.txt.
Control dummies are no longer sent to runaway coordinates.
D20 uses display_small_relative, which moves the bridge by about 350,000 coordinate units.
Visible non-control component packets are translated by the shared beautifier grid stage.
Cases marked R91_SAFE intentionally reduce RESISTOR count to the accepted 91 limit.

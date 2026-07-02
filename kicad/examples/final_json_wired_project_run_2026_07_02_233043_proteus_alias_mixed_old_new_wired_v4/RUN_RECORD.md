# Run Record

Purpose: accepted wired KiCad project run for the mixed old/new component suite.

Outcome:
- Static checks passed.
- Internal no-cross/no-touch geometry validation passed:
  - 0 unresolved pins.
  - 0 routing unresolved pins.
  - 0 geometry violations.
- KiCad quality passed for all 3 schematics.
- Netlist export succeeded for all 3 schematics.
- ERC still has tolerated `pin_not_connected`, `pin_not_driven`, and `power_pin_not_driven` warnings because this suite is a component-support and routing test, not a complete polished reference design.

Notes:
- Geometry-repair fallback converted unsafe routed nets to local labels and recorded the converted nets in each project manifest.

Next:
- Improve the wire planner so more of those fallback nets become clean routed wires without weakening validation.

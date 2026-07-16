# Interrupted T10 Local Netlist Merge Repair Probe

This folder is an incomplete generated record. It was started after adding
cross-net endpoint-touch rejection to `kicad_wire_maker.py`, but the run was
stopped manually after roughly 4.5 minutes because candidate path validation was
still rechecking all existing wires for each candidate.

No KiCad project was emitted here. Keep this folder only as evidence of the
performance regression that led to the follow-up optimization: candidate path
validation now checks only the candidate segments against component bodies, plus
explicit wrong-pin and cross-net endpoint-touch rules.

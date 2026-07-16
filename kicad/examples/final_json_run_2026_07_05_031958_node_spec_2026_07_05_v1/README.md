# Node-Spec Final JSON Run

This folder is an immutable generated record. It contains canonical final CircuitIR JSON, component-only placement inputs derived from that JSON, and per-circuit reports from the arrangement decider, beautifier, and wire planner.

The final JSON was compiled from pasted arrow-node text where `NET_*` labels are electrical nodes and `REF.PIN` tokens are component pins.

The final JSON was compiled by `kicad.pipeline.final_circuit_builder`, not by a one-shot AI prompt. Compiler repairs are recorded inside each JSON under `generation_notes.compiler_repairs`.

Do not overwrite this folder. Generate a new `final_json_run_*` folder for any changed component, net, coordinate, route, value, or schema behavior.

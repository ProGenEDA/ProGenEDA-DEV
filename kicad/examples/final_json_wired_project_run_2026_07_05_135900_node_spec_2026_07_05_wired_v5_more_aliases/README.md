# Final JSON To KiCad Wired Project Run

This folder is an immutable generated record. It takes connected final JSON files, runs the arrangement decider, beautifier, wire planner, and KiCad wire maker, then writes openable KiCad projects with real embedded symbols plus wire objects. Terminal/local-label objects are only valid when the run is generated in terminal or combination mode.

The wire planner is fed exact KiCad source-symbol pin points through `routing_inputs/` when those pins can be resolved. The wire maker uses the same source-backed KiCad pin geometry when possible. Any unresolved pin aliases, unroutable nets, strict-wire connectivity violations, local expected-net comparison failures, wire crossings, and wire/component body contacts are recorded in each project manifest.

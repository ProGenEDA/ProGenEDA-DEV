# Final JSON To KiCad Wired Project Run

This folder is an immutable generated record. It takes connected final JSON files, runs the arrangement decider, beautifier, wire planner, and KiCad wire maker, then writes openable KiCad projects with real embedded symbols plus wire/label objects.

The wire maker uses source-backed KiCad pin geometry when possible. Any unresolved pin aliases or deferred route-limit nets are recorded in each project manifest.

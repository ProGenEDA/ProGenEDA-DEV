# Current accepted mixed 1x - 2026-07-15

`M01_CURRENT_ACCEPTED_30F_1X_TERMINAL_sa.pdsprj` contains one each of the
20 accepted native two-pin/source routes and 10 catalogue-driven
control/transistor routes.  It was placed from the locked mega and terminalized
once by `attach_mixed_component_and_catalogue_bidir_terminals_to_project` in
the shared terminal placer.

- 30 placed component families
- 70 active terminal records and 70 short WIRE records
- normal Proteus open: passed
- cold reopen: passed
- no modal error and no disposable-copy mutation

The gate record and screenshots are in `04_local_proteus_gate/`.  The copied
gate project is intentionally not versioned.

# GUI Acceptance

This immutable run was used for the first successful EasyEDA Pro 3.2.149 open
acceptance after fixing generated project branch and membership metadata.

Observed result:

- EasyEDA opened the project without the historical-project-data error.
- The project tree contained the generated Schematic and PCB documents.
- The schematic rendered the eight real source-library components, physical
  wires, and native terminals.
- The PCB rendered the source-library footprints, board outline, pads, and
  generated tracks.
- EasyEDA migrated the opened `.eprj` into its normal `.eprj2` working copy and
  retained `.eprj_backup`.

The unopened replacement deliverable is in the later generated run. This folder
is retained as GUI acceptance evidence and must not be reused as generator
output.

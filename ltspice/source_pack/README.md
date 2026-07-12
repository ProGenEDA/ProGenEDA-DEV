# LTspice Source Pack Policy

LTspice is proprietary, so this backend does not vendor or modify the LTspice
executable or its `lib/sym` directory.

Instead, the backend authors small vector `.asy` symbols from the profile
catalogue and writes only the used assets next to each generated `.asc` file.
The exact generated ASY files are parsed back before acceptance. Primitive
behavior comes from the owned symbol `Prefix`, `Value`, and `SpiceOrder`
attributes; project-local generic models are generated from
`pipeline/ltspice_model_map.json`.

The implementation is informed by:

- the raw donor ASC files under `Documents/Ltspice/Donor`;
- LTspice 26's installed symbol geometry used only as test/oracle evidence;
- KiCad's LTspice importer format documentation; and
- LTspice's local help for pin order, values, and simulation directives.

No proprietary ASY or model file is committed here. When a future profile uses
a vendor model, its source, licensing, pin order, and content digest must be
recorded before it can become `project_local_model`.

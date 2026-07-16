# Final JSON To KiCad Project Run

This folder is an immutable generated record. It takes canonical connected final JSON files, derives component-only placer input from each one, and writes openable KiCad projects using real embedded KiCad symbols.

The final JSON files still contain the full connected net information. The `.kicad_sch` files in `projects/` are placement schematics only because the EDA-specific wire maker is not implemented yet. Do not overwrite this folder; create a new `final_json_project_run_*` folder for any changed output.

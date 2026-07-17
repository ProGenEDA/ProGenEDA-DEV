# EasyEDA Pro Deployment Checklist

1. Extract this handoff and run `python3 apply_handoff.py WEBSITE_ROOT --dry-run`.
2. Resolve any baseline hash conflict intentionally; do not use `--force`
   without reviewing the changed website file.
3. Apply the overlay and confirm `vendor/easyeda/progen-easyeda` is executable.
4. Run `npm run build`.
5. Run `npm run test:easyeda:integration`.
6. Start the API and confirm `/api/examples?service=EA` reports 300 examples.
7. Generate one EasyEDA example through `/api/generate/stream`; verify eight
   stage events, a successful `EA-A-...` serial, and an `.eprj` download.
8. Open JSON Lab as admin/demo, edit a value and reference, validate, regenerate,
   and confirm the original circuit remains immutable.
9. Run `npm run test:easyeda:corpus` for the complete API-level corpus gate.
10. Verify the Supported Components page shows EasyEDA Pro, 59 logical entries,
   80 schematic inputs, 32 PCB components, and all three routing modes.
11. Keep the executable's private internal ZIP and validation reports in server
    storage; expose only the `.eprj` download to normal users.

Release acceptance is blocked by any input repair drift, source hash failure,
missing pin, netlist mismatch, geometry violation, invalid SQLite project, or
failed offered PCB. A withheld PCB is acceptable only when the `.eprj`
schematic passes and the reported boundary explains why no PCB was included.

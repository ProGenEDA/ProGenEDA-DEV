# PDF 200-circuit placement-control run — 2026-07-17

## Purpose

This run turns the supplied *Proteus Wiring Specifications for 200 Circuits*
PDF into a verified corpus.  The source fixture is
[`Proteus_200_Circuits_Complete_Pin_Wiring.pdf`](../../../active/fixtures/circuit_specs/Proteus_200_Circuits_Complete_Pin_Wiring.pdf)
with SHA-256
`B5762DAA7E88C7E24FB0AFD492F2D77A0CB935132C50F218F85599F653DEB8AA`.

Each canonical JSON under
[`../../../active/examples/proteus_200_circuits/specifications`](../../../active/examples/proteus_200_circuits/specifications)
preserves every PDF component, value, pin-to-net assignment, net endpoint,
and reported pin audit.  The parser independently verifies that the component
table, net table, and reported audit agree before it writes a JSON file.

## Execution boundary

The current executable deliberately rejects arbitrary physical net/wire
requests because the shared physical Wire Maker has not yet been promoted.
Accordingly, this run sends the separately derived
[`placement_controls`](../../../active/examples/proteus_200_circuits/placement_controls)
to the executable with `--no-terminals`.  The resulting projects prove native
placement and loader validity; the canonical source JSON remains the complete
wiring specification for the future shared wiring stage.  This run makes no
claim that those physical nets have been emitted or simulated.

## Results

- 200 of 200 canonical PDF circuit specifications passed the table/net/audit
  validation.
- 200 of 200 placement-control JSON files generated a native `.pdsprj` through
  the current portable executable.
- The ten highest-complexity circuits passed two real Proteus cold opens each,
  with 20-second stability windows, no loader dialog, the expected schematic
  title, and unchanged disposable-copy hashes.
- The final artifact audit verified every generated project SHA-256 and the
  required native container members: `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, and
  `SCRIPTS/PWRRAILS.DAT`.

The ten loader-gated circuits were 180 (Op-Amp LED Level Indicator), 173
(State-Variable Filter), 139 (Three-Op-Amp Instrumentation Amplifier), 73
(Four-Stage Cockcroft-Walton Multiplier), 155 (Precision Full-Wave Rectifier),
108 (Two-Stage NMOS Amplifier), 156 (Op-Amp Absolute-Value Circuit), 171
(Active Notch Filter), 196 (Op-Amp NMOS Electronic Fuse), and 193
(Zener-Referenced Op-Amp NMOS Regulator).

## Recorded artifacts

- [`execution_report.json`](execution_report.json) — one executable result per
  circuit, including each native project hash.
- [`cold_open_candidates.json`](cold_open_candidates.json) — deterministic
  top-ten complexity selection.
- [`cold_open_results.json`](cold_open_results.json) — both cold-open phases
  for every selected circuit.
- [`artifact_verification.json`](artifact_verification.json) — final 200-file
  native-container and cold-open evidence audit.
- [`generated_projects`](generated_projects) — the 200 resulting native
  placement projects.

## Reproduce

From the repository root:

```powershell
$env:PYTHONPATH = "proteus/active/src"
python proteus/active/tools/build_pdf_200_circuit_corpus.py
python proteus/active/tools/build_pdf_200_circuit_corpus.py --check
python proteus/active/tools/run_pdf_200_circuit_corpus.py --jobs 3
python proteus/active/tools/run_pdf_200_circuit_corpus.py --cold-open
python proteus/active/tools/run_pdf_200_circuit_corpus.py --check --require-cold-open
```

# Ten terminalized complex circuits — current executable

These are fresh `.pdsprj` projects generated with
`proteus/active/release/ProgenProteus.exe` on 2026-07-17, not the earlier
placement-only corpus outputs. Generation used each existing placement control
without `--no-terminals` and without `--allow-unterminalized`.

The executable SHA-256 was
`41C15EAE737E4A5617E79504C136129C3B970B376C127DDAD0454EC709086388`.

| Rank | Circuit | Terminalized components | Short terminal-to-pin WIREs | Cold-open gate |
| ---: | --- | ---: | ---: | --- |
| 01 | Op-Amp LED Level Indicator | 19 | 42 | pass twice |
| 02 | State-Variable Filter | 16 | 35 | pass twice |
| 03 | Three-Op-Amp Instrumentation Amplifier | 15 | 33 | pass twice |
| 04 | Four-Stage Cockcroft-Walton Multiplier | 18 | 36 | pass twice |
| 05 | Precision Full-Wave Rectifier | 15 | 32 | pass twice |
| 06 | Two-Stage NMOS Amplifier | 16 | 34 | pass twice |
| 07 | Op-Amp Absolute-Value Circuit | 12 | 26 | pass twice |
| 08 | Active Notch Filter | 13 | 27 | pass twice |
| 09 | Op-Amp NMOS Electronic Fuse | 12 | 26 | pass twice |
| 10 | Zener-Referenced Op-Amp NMOS Regulator | 12 | 26 | pass twice |

Each project has a generated inspection report. The three long-name reports
are in `reports/` with shortened names to stay below the Windows path limit.
`screenshots/` contains two delayed cold-open captures per circuit; all twenty
had a schematic title, stayed alive, showed no loader dialog, and retained the
same disposable-copy hash across the cold reopen.

These are terminalized component projects: labels identify intended nodes, and
every exposed terminal uses a nonzero short WIRE to its component pin. They do
not claim that the larger circuit netlist has been physically routed; the
shared physical Wire Maker remains a separate stage.

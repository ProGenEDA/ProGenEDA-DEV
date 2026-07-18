# Gate-route executable revalidation — 2026-07-18

## Purpose

This run revalidates the existing shared, catalogue-driven terminal route for
the DIL14 gate families through the current portable executable. It does not
introduce a new terminal workflow, edit `component_terminal_placer.py`, or
alter any already accepted non-IC route.

The executable used for every generation was
`proteus/active/release/ProgenProteus.exe` (SHA-256
`D32D06E4935EAAC1E8439807472871E1A706F299AE4A1DF7839CBC4E8534FEAD`).

## Donor evidence examined first

| Family | Authoritative terminalized donor | SHA-256 |
| --- | --- | --- |
| 74HC00 | `dil14_quad_2input_logic/74HC00/74HC00_user_terminalized_july04.pdsprj` | `2C5D4C668003CE062826211C8F22E549065996C74CFA10AD26CD9714F436C6A0` |
| 74HC02 | `dil14_quad_2input_logic/74HC02/74HC02_user_terminalized_july04.pdsprj` | `FBE6AACC10FEE2952EF11CB6A83FF56E1C9AB9EF93FBD2C7CF60760E96D30A70` |
| 74HC04 | `dil14_hex_inverter/74HC04/74HC04_terminalized_primary_hc04_all7.pdsprj` | `3C1CC46286F817174E48EC373F23625565150A42E18A1668D05E6BB3F31AC4CE` |
| 74HC08 | `dil14_quad_2input_logic/74HC08/74HC08_user_terminalized_july04.pdsprj` | `77AD463BD2DAF1AF54C60C3BC45FCCA0CA56E487F03E913338C367AE1EFB42AF` |
| 74HC32 | `dil14_quad_2input_logic/74HC32/74HC32_user_terminalized_july04.pdsprj` | `857676C3B08D86B922159420B924B0A5D42AB3C09A8EF80FCB4294B0BD71ECA5` |
| 74HC86 | `dil14_quad_2input_logic/74HC86/74HC86_user_terminalized_july04.pdsprj` | `77E3E299CB807FAB4CA75A7C22228F7FCB4C26BD494EB6C6B0088E15C10238BE` |
| 74HC266 | `dil14_quad_2input_logic/74HC266/74HC266_user_terminalized_july04.pdsprj` | `0E87991E5206E52CA782A35B7D8E23D236F0102CBBBC735EADF1D9EB44A60C90` |

All donors were read as complete archives including `ROOT.DSN`, `ROOT.CDB`,
project metadata, terminal records, pin links, WIRE records, and trailers.

## Fresh executable generation and validation

Each `input_*.json` file was generated from scratch by the executable. Its
`.progen_report.json` confirms, for every output:

- one active terminal and one nonzero short WIRE for each exposed pin;
- grid-aligned terminal contacts;
- active terminal-to-component suffix links allocated after final `ROOT.DSN`
  addresses; and
- valid terminal/WIRE path-contact checks.

| Family | Executable 1× | Current executable ceiling | Added terminals / WIREs at ceiling | Local Proteus gate |
| --- | --- | --- | --- | --- |
| 74HC00 | `G01_74HC00_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 8× (`G02_74HC00_8X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 96 / 96 | passed twice |
| 74HC02 | `G_74HC02_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 4× (`G_74HC02_4X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 48 / 48 | passed twice |
| 74HC04 | `G_74HC04_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 10× (`G_74HC04_10X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 120 / 120 | passed twice |
| 74HC08 | `G_74HC08_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 10× (`G_74HC08_10X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 120 / 120 | passed twice |
| 74HC32 | `G_74HC32_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 10× (`G_74HC32_10X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 120 / 120 | passed twice |
| 74HC86 | `G_74HC86_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 10× (`G_74HC86_10X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 120 / 120 | passed twice |
| 74HC266 | `G_74HC266_1X_EXECUTABLE_TERMINALIZED_sa.pdsprj` | 10× (`G_74HC266_10X_EXECUTABLE_TERMINALIZED_sa.pdsprj`) | 120 / 120 | passed twice |

The local gate used `invoke_local_proteus_gate.ps1` on a disposable copy of
each generated file: cold launch, 12-second stability wait, forced close,
then a second cold launch. Every listed project had a schematic title, stayed
alive, showed no Bad Object Record, Fatal Error, LXLCORE, or library dialog,
and retained an unchanged SHA-256 on the disposable copy. No Ctrl+S was used.

The `screenshots/` directories contain both cold-open captures for every
ceiling. They show the terminal symbols beside their gate pins and the short
horizontal attachment WIREs. Automated screenshots are supporting evidence;
user visual acceptance remains the final layout criterion.

Focused automated regressions also passed: `tests/test_proteus_app.py` (19
tests) and the seven donor-contract tests covering the shared 74HC00, 74HC02,
74HC04, 74HC08, 74HC32, 74HC86, and 74HC266 emitters. `python -m compileall -q
src tests tools` completed without errors.

## Scope and remaining work

These are **current portable-executable limits**, not a claim that the locked
mega donor or source placer cannot hold more packages. The executable purposely
keeps lower ceilings while this terminal route is being revalidated.

Mixed gate-family generation remains deliberately unsupported. It needs a
separate, authoritative mixed donor and a fresh additive mixed-route audit;
this solo-family proof must not be extrapolated into mixed support.

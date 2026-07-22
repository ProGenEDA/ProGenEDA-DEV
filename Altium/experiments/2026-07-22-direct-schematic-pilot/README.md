# Direct Altium Schematic Pilot - 2026-07-22

## Purpose

Establish a direct, source-backed Altium schematic path from canonical JSON.
This experiment does not create or convert an EasyEDA project.

## Source Evidence

- Locked source: `Altium/source_pack/donors/logic_trainer_ascii_seed.SchDoc`
- SHA-256: `bfc862eff7dc73bcc787fde8d6fdfc37e283b6249a6e029ee946abf681c2dde8`
- Native source record forms used: component `RECORD=1`, pin `RECORD=2`,
  net label `RECORD=25`, wire `RECORD=27`, and sheet `RECORD=31`.
- Component root IDs in the source use the compact `pge<number>` form. The
  writer allocates unique IDs in that same source-observed form.

## Direct Runs

All runs created fresh temporary directories and passed the saved-file direct
validator plus ZIP package inspection.

| Input | Mode | Evidence |
| --- | --- | --- |
| `direct_rc_filter.json` | `wire` | 3 components, 6 pins, 17 physical wire segments, 0 labels. |
| `direct_led_indicator.json` | `wire` | 3 components, 6 pins, LED aliases `A`/`C` resolved to source pins `1`/`2`. |
| `direct_rc_filter.json` | `terminal` | 3 components, 6 pins, 6 source-backed terminal labels. |
| `direct_74hc04_breakout.json` | `combination` | 8 components, 28 pins, 43 physical segments, 22 labels for 11 fully terminalized fallback nets. |
| generated all-catalogue NC smoke | `combination` | 12 source templates, 98 pins explicitly assigned to `NC_*`, 0 wires, 0 labels. |

Strict `wire` mode was also forced on the 74HC04 breakout. It correctly failed
on the first unresolved net rather than silently emitting labels.

## Negative Validation

After a passing combination run, one generated `RECORD=25` label was changed
from `IO_02` to `WRONG_NET`. The independent saved-file validator rejected the
candidate because the label was not declared as a terminalized expected net.

## Conversion Engine Finding

The installed Chameleon registry advertises `altium` as both a decoder and an
encoder. A raw direct `.SchDoc` round-trip was nevertheless lossy: its output
kept wire records but omitted component records and did not include a
`.PrjPcb`. The converter is therefore research-only and is not used by the
direct generation or validation path.

## Remaining Acceptance Gate

The local Altium Designer download was incomplete during this experiment.
Desktop open/render/compile evidence remains required before a
desktop-qualified claim. This pilot is also schematic-only: a direct
`.PcbDoc` writer requires separate native board donor evidence.

## Tooling Note

`python -m compileall -q Altium` passed. The base environment did not contain
`pytest` or `pip`, so the pytest suite could not be executed or packaged here;
the same assertions were exercised through standard-library/CLI regression
runs.

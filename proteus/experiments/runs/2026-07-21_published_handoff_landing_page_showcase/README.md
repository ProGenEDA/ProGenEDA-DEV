# Published handoff landing-page showcase

These are four high-complexity Proteus projects produced by the published
handoff executable, [`ProgenProteus.exe`](../../../active/release/ProgenProteus.exe),
not by an experimental Python-only route. Each folder keeps the exact input
placement control, executable result, and generated report. Disposable
loader-gate copies and automated screen captures are intentionally excluded.

| Project | Source corpus control | Components | Terminal/WIRE units | Loader result |
| --- | --- | ---: | ---: | --- |
| `01_op_amp_led_level_indicator` | #180 Op-Amp LED Level Indicator | 19 | 42 | Two 12-second cold opens passed |
| `02_cockcroft_walton_multiplier` | #073 Four-Stage Cockcroft-Walton Multiplier | 18 | 36 | Two 12-second cold opens passed |
| `03_two_stage_nmos_amplifier` | #108 Two-Stage NMOS Amplifier | 16 | 34 | Two 12-second cold opens passed |
| `04_open_loop_nmos_sepic_converter` | #200 Open-Loop NMOS SEPIC Converter | 11 | 23 | Two 12-second cold opens passed |

Every emitted terminal is grid-aligned and connected to its component pin by a
nonzero short Proteus wire.  The executable placement reports show no visible
component-body overlap for all four designs.

The loader gate's window/dialog check is authoritative. Proteus can render
through a path that the Windows capture helper cannot reliably reproduce, so
automated screenshots are not included as layout evidence.

The current published handoff intentionally does **not** create arbitrary
physical inter-component nets.  The terminal names retain the source circuit's
logical node names; physical routing remains a later Wire Maker stage.

The SEPIC project was accepted by the same normal-open/cold-reopen gate as the
other three, with no loader dialog and an unchanged disposable copy.

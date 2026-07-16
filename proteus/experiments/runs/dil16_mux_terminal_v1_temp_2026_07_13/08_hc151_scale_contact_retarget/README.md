# 74HC151 scale contact retargeting

Status: local Proteus loader gate passed for 9x and 15x; user visual
acceptance pending.

These outputs use the locked component-placement mega donor, the existing
shared terminal placer, and the 74HC151 catalogue profile. No donor project is
copied into the output and no family-specific terminal generator exists.

## Files

- `S04_74HC151_9X_NO_TERMINAL.pdsprj` and
  `S04_74HC151_15X_NO_TERMINAL.pdsprj` are component-placer controls.
- `S04_74HC151_9X_CATALOGUE_TERMINAL_sa.pdsprj` and
  `S04_74HC151_15X_CATALOGUE_TERMINAL_sa.pdsprj` are terminalized candidates.
- `local_proteus_gate/G05_74HC151_15X_initial_before_close.png` and
  `G07_74HC151_15X_cold_reopen_before_close.png` are the retained large-case
  visual gate captures.

## Why the contact retarget is required

The ninth and later HC151s start a new beautifier row. Their physical pins may
not be grid intersections, which is valid. The terminal must be on a grid
intersection and its short WIRE must reach that exact pin. The profile therefore
uses the shared `wire_coordinates_retarget_to_current_contacts` rule: it keeps
each donor WIRE's two- or three-point topology and pin endpoint, while moving
only its terminal-side contact to the planned grid coordinate.

## DSN audit

| Scale | Terminals / WIREs | Two-point / three-point paths |
| --- | ---: | ---: |
| 9x | 126 / 126 | 72 / 54 |
| 15x | 210 / 210 | 120 / 90 |

For both outputs terminal suffixes and WIRE suffixes are unique and match,
each follows the final ROOT.DSN WIRE-address formula, every terminal contact
is grid aligned and appears in its active WIRE, and every WIRE is nonzero.

Both copied files visibly cold-opened and cold-reopened after the stability
wait with no modal dialog. Neither normal open was Ctrl+S-saved; each copy
remained SHA-256-identical to its candidate.

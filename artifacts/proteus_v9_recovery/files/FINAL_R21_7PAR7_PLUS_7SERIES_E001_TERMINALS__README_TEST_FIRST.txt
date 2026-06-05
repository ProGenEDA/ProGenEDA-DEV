FINAL R21 resistor-terminal circuit, E001 base only

Topology:
  Branch A: R1..R7 in series from N0 to M0
  Branch B: R8..RE in series from N0 to M0, parallel with Branch A
  Tail:     RF..RL in series from M0 to Z0

This implements: 7 in series || 7 in series, then 7 more in series.

Test first:
  FINAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_CDB_TRUE_SAFE_VISIBLE.pdsprj

This is built from E001 PROJECT.XML + E001 PWRRAILS + generated ROOT.CDB + generated/rebuilt ROOT.DSN.
It is not using a full R4 project as base.

Actual CDB values:
  R1=1k, R2=2k, ..., R9=9k, RA=10k, RB=11k, ..., RL=21k.

Visible-safe labels:
  1k..9k then Ak..Lk. This is intentional to preserve the fixed-width visible resistor record.

Optional:
  OPTIONAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_TRUE_VISIBLE_VALUES.pdsprj
  This tries true visible labels 10k..21k by variable-length value fields. Test only after the safe file.

No explicit wire records are included. Terminals are placed at resistor pin-contact positions and repeated terminal labels define shared nodes.

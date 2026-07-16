# Local Proteus Gate

- Candidate: `ALL_ACCEPTED_TERMINALIZED_CURRENT_GROUP_UNTERMINALIZED_1X_sa.pdsprj`
- Gate copy: `ALL_ACCEPTED_TERMINALIZED_CURRENT_GROUP_UNTERMINALIZED_1X_GATE.pdsprj`
- Loader wait: 24 seconds after each cold launch.
- First cold open + Ctrl+S: no modal error.
- Cold reopen + Ctrl+S: no modal error.
- Checked modal classes: Fatal Error, LXLCORE, Bad Object Record and device-library dialogs.

## Structural audit

- Archive members remained unchanged: `PROJECT.XML`, `ROOT.DSN`, `ROOT.CDB`, and `SCRIPTS/PWRRAILS.DAT`.
- Object stream changed only through Proteus canonicalization: 19,101 to 19,100 bytes; 49 terminals and 49 WIRE records remained unchanged.
- `ROOT.CDB` changed from 28 to 30 pin rows, adding two blank Proteus rows; property rows remained 28.
- This was observed only in the saved gate copy. The handed-off donor output remains the original generated file.

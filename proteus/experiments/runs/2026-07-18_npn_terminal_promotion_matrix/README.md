# NPN terminal promotion matrix v1 — retained failure evidence

This historical pack records the initial NPN executable-promotion attempt. It
must not be used as accepted output.

The NPN solo cases and several non-diode controls opened, but the asymmetric
NPN+diode cases stopped on a malformed device/library dialog. Donor analysis
isolated the defect to an unproven stream boundary: the NPN terminal/WIRE tail
was inserted between later diode packets and the stream ended with a fallback
double `FF`.

The corrected, loader-gated replacement is
[`../2026-07-18_npn_terminal_promotion_matrix_v2`](../2026-07-18_npn_terminal_promotion_matrix_v2).
V2 moves the donor-proven NPN tail after the ordinary component stream and
uses NPN's explicit single-`FF` finalizer for the isolated non-IC route.

No file in this folder is a current support claim; it is kept for byte-level
comparison and regression diagnosis.

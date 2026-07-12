# Accepted Terminal Route Analysis — 2026-07-12

## Frozen routes

The following paths were already user-tested and must not be changed while researching later groups:

- all accepted two-pin families, including the generic diode/fuse/LED/switch route;
- POT-HG, LM317T and OPAMP;
- NMOSFET, 2N7000, BS170, NPN, PNP, 2N3904 and 2N4401 when tested in their accepted solo/group evidence.

The actual user-accepted donor remains authoritative over this note.

## Mixed-stream facts collected from accepted files

- `P002_FINAL_ZONE_1X_sa.pdsprj` is the authoritative pre-save R/C + controls + BJT control stream.
- Its R/C + controls + BJT regenerated control was made byte-identical before further work.
- `T01_NATIVE_CONTROLS_sa.pdsprj` is the all-native + control structural control.
- These facts are limited to their proven stream contexts. They do not authorize modifying frozen generic two-pin pin geometry to make a new BJT mix work.

## Rejected path

An attempted generic two-pin pin/contact geometry rewrite was made from a Ctrl+S observation. It caused user-reported diode failures in `14_native_bjt_boundary_clusters`; it was reverted. Ctrl+S canonicalization is diagnostic evidence only and cannot override a user-accepted pre-save route.

The shared mixed emitter now refuses a request that combines any extra native
family (such as `DIODE`) with the terminal-leading BJT zone. The only currently
proven pre-save native prefix for that zone is `RESISTOR` + `CAP`. This guard
prevents a future caller from generating a speculative broken diode pack; it
does not alter any accepted diode packet, terminal, link or WIRE behavior.

## Manual donor produced after the revert

`experiments/manual_current_group_terminal_donor_1x_v1_temp_2026_07_12/ALL_ACCEPTED_TERMINALIZED_CURRENT_GROUP_UNTERMINALIZED_1X_sa.pdsprj` contains:

- terminalized: all accepted two-pin families plus POT-HG, LM317T and OPAMP;
- intentionally unterminalized: NMOSFET, 2N7000, BS170, NPN, PNP, 2N3904 and 2N4401.

It opened, saved and cold-reopened locally without a Proteus modal error. The user can add terminals to the intentionally unterminalized group to create the next authoritative mixed donor.

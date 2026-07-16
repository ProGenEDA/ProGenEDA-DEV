# V30 terminal isolation pack

Use this after rejected V29 to isolate whether failure is solo-family, mixed two-pin-only, or mixed POT-HG/LM317T/OPAMP only.

Test order:

1. `01_solo_1x_sa_test_first` ? every family in scope, one component each.
2. `02_mixed_two_pin_only_sa` ? accepted two-pin families mixed at 1x/9x/15x/24x-capped.
3. `03_mixed_pothg_lm_op_sa` ? POT-HG + LM317T + OPAMP mixed at 1x/9x/15x/24x.

Do not use V29 as proof for this pass; V30 is intentionally split into layers.

24x two-pin-only caps are from the locked mega donor terminalizable-packet limits: `CAP-ELEC=21`, `DIODE=22`, `CSOURCE=21`, `FUSE=22`, `REALIND=20`.

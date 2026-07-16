MIXED_RCL_LOCKED_T02_21_RULE_TOPOLOGY

Open this generated mixed R/C/L project in Proteus 8.13.

Project: MIXED_RCL_LOCKED_T02_21_RULE_TOPOLOGY.pdsprj
Groups: 9 (RCL, RC, LC, RCL, RL, RC, RCL, LC, RL)
Components: 21 (7R, 7C, 7L)
Static validation issues: []

Locked endpoint rules:
- V0/power uses the accepted donor-derived $TERPOWER -> $TEROUTPUT bridge.
- Component starts use $TERINPUT terminals.
- Component ends use $TEROUTPUT, except G0 endpoints use $TERGROUND.
- R/C/L, RC, LC, RL, and C-only blocks are made by removing whole subgroups from accepted donor units.

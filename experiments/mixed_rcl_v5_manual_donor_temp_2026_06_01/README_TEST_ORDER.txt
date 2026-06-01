MIXED_RCL_V5_MANUAL_DONOR_TEMP_2026_06_01

Test in order:
1. T01, T02, T03, T04 first. These are donor controls.
2. If T01 fails, the supplied donor/repack path is bad; stop.
3. If T01 works but T02-T04 fail, report which E001 insertion variant fails first.
4. Only then test T05-T10. These reintroduce generated terminal topology around L/R/C.

T05 and T06 are the key resistor/inductor boundary checks: same L/R/C object order, donor CDB vs generated CDB.

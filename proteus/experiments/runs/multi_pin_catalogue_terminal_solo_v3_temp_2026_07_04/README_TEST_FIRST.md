# Multi-pin catalogue terminal solo V3 - coordinate-frame fix

Open each `.pdsprj` in the case folders. These were generated only through `src/proteusgen/component_terminal_placer.py`.

V3 fixes the V2 visual bug where terminals could appear far away from the component. Pin coordinates are now decoded as:

`current component body bbox min + catalogue component-relative pin offsets`

The donor WIRE rows are still used, but only for byte/link identity and record patching. They are not used as placement coordinates.

Requested 3x/13x/23x is still reduced to 1x for this checkpoint because duplicated native packets do not yet preserve a safe per-pin component-link table. Mixed one-each remains blocked for the same reason recorded in V2: the mixed component placer path currently emits bare mega-donor packets without the WIRE/link skeleton required by the safe emitter.

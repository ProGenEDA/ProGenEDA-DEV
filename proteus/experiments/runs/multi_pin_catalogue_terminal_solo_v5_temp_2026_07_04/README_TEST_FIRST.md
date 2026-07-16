# Multi-pin catalogue terminal solo V5 - parsed IC placement + marker-anchor terminals

Open each `.pdsprj` in the case folders. These were generated only through shared modules, with terminal behavior in `src/proteusgen/component_terminal_placer.py`.

V5 keeps the V4 Bad Object Record fix: explicit double-`FF` ROOT.DSN object-stream ending.

V5 fixes the user-reported V4/V3 placement issue for the affected counters/registers/decoder families by moving them off the rejected broad `component_text_or_body` scanner and onto parsed IC coordinate extraction. Terminal positions are calculated from component marker-anchor coordinates plus catalogue pin offsets.

Requested 3x/13x/23x is still reduced to 1x for this checkpoint because duplicated native packets do not yet preserve a safe per-pin component-link table. Mixed one-each remains blocked because the mixed component placer path currently emits bare mega-donor packets without the WIRE/link skeleton required by the safe emitter.

# Multi-pin catalogue terminal solo V4 - Bad Object Record fix

Open each `.pdsprj` in the case folders. These were generated only through `src/proteusgen/component_terminal_placer.py`.

V4 fixes the Bad Object Record warning seen in V3. The cause was a missing explicit final ROOT.DSN object-stream terminator. Proteus saved files normalize the stream to end with `FF FF`; V4 now emits that directly.

V4 also keeps the V3 coordinate-frame fix:

`current component body bbox min + catalogue component-relative pin offsets`

The donor WIRE rows are still used only for byte/link identity and record patching. They are not used as placement coordinates.

Requested 3x/13x/23x is still reduced to 1x for this checkpoint because duplicated native packets do not yet preserve a safe per-pin component-link table. Mixed one-each remains blocked because the mixed component placer path currently emits bare mega-donor packets without the WIRE/link skeleton required by the safe emitter.

# Multi-pin catalogue terminal solo V2 - Proteus test pack

Open each `.pdsprj` in the case folders. These were generated only through `src/proteusgen/component_terminal_placer.py`.

Requested 3x/13x/23x pattern is reduced to 1x for this checkpoint because duplicated native packets do not yet preserve a safe per-pin component-link table. Do not treat this as solved for multi-copy until that mapping is researched.

Mixed one-each is blocked for this checkpoint because the current component placer selects a mega donor for mixed IC requests and those bare packets do not contain the existing WIRE/link skeleton required by the safe catalogue emitter.

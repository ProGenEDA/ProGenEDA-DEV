# Altium Source Pack

The direct schematic writer embeds one compact, audited native source seed:

```text
donors/logic_trainer_ascii_seed.SchDoc
SHA-256 bfc862eff7dc73bcc787fde8d6fdfc37e283b6249a6e029ee946abf681c2dde8
```

It is a line-oriented `Protel for Windows - Schematic Capture Ascii File
Version 5.0` document captured from the authorized logic-trainer donor. The
catalogue reads it at generation time and refuses to run if its hash changes.

The compact pack provides complete native record payloads for the locked
component families plus native examples of:

- sheet record `RECORD=31`;
- wire record `RECORD=27`; and
- net-label record `RECORD=25`.

It also provides source pin designators, native pin names, coordinates, and
escape directions derived from `PINCONGLOMERATE`. The generator copies the
actual source records and rebases their owner/index/coordinate data into a
fresh document. It does not draw a generic replacement symbol or manufacture a
record grammar from scratch.

Only records needed by the audited direct catalogue are used. Adding another
family requires source evidence, a hash update, catalogue parsing coverage,
and a focused direct-generation regression.

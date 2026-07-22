# Altium Source Pack

The direct schematic writer embeds two compact, audited native source seeds:

```text
donors/logic_trainer_ascii_seed.SchDoc
SHA-256 bfc862eff7dc73bcc787fde8d6fdfc37e283b6249a6e029ee946abf681c2dde8

donors/nodemcu_project_seed.PrjPcb
SHA-256 ab26512b221a97af8f2f39342ecf886d134b24b685a8cb1a196720e0cc9b9f96
```

It is a line-oriented `Protel for Windows - Schematic Capture Ascii File
Version 5.0` document captured from the authorized logic-trainer donor. The
catalogue reads it at generation time and refuses to run if its hash changes.

The project descriptor seed is an exact-section extraction from the real
MIT-licensed NodeMCU Altium project. Its provenance, source commit, original
hash, and retained license are recorded beside it. The writer changes only the
single `DocumentPath` field and preserves the donor-native `Design`,
`Preferences`, `Document1`, and `Configuration1` grammar.

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

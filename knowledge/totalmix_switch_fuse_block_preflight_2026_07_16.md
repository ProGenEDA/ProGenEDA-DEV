# Totalmix Switch/Fuse Block Preflight — 2026-07-16

## Scope

The user directed that `SWITCH` and `FUSE` be removed from the current
terminalized mixed-route support and explicitly blocked while work continues
on every other family. This is a route-support withdrawal, not a geometry or
binary-grammar repair.

## Evidence

- The 43-family 3× terminalized stream with all terminal units reaches the
  Proteus library parser failure (`Device '$¤\x06\x07=¼#t' used but not in
  library`). The apparent device name is not stored literally in `ROOT.DSN`,
  `ROOT.CDB`, or another archive member; it is parser-derived after malformed
  stream interpretation.
- Keeping the `SWITCH` component packet but suppressing only its terminals
  permits a normal loader cold-open/cold-reopen. That loader result is not a
  visual terminal-coverage acceptance, and the user reported that multiple
  catalogue families were still visibly unterminated.
- Therefore the temporary fallback must not silently emit a partially
  terminalized component set. The blocked families must be rejected at the
  totalmix entry point so the component placer receives a deliberate 41-family
  request instead.

## Proposed additive change

1. Add a `TOTALMIX_BLOCKED_FAMILIES` policy containing only `SWITCH` and
   `FUSE`.
2. In `totalmix_combined_v1`, fail clearly if either family is present in the
   selected placed-design stream or requested for terminal attachment.
3. Leave every frozen standalone family serializer, geometry, WIRE order,
   terminal suffix route, and historical accepted file unchanged.
4. Regenerate the mixed candidates from a component-placer request that
   excludes those two families, then audit all remaining emitted terminal
   attachment positions against their catalogue offsets before calling any
   loader pass a visual acceptance.

## Backup

`backups/component_terminal_placer/component_terminal_placer_20260716_171408_before_totalmix_switch_fuse_block.py`


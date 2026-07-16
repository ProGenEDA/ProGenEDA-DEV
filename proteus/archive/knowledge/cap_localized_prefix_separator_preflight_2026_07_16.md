# CAP localized-prefix separator preflight — 2026-07-16

## Scope

Repair only the shared mixed terminal emitter's boundary between a localized
CAP leading terminal record and CAP's second terminal record.  No component
packet order, donor packet, coordinate, ROOT.CDB member, accepted family
geometry, or link allocation rule is in scope.

## Authoritative binary evidence

| Project | Loader result | Relevant ROOT.DSN sequence |
| --- | --- | --- |
| `experiments/terminal_recovery_solo_1x_temp_2026_07_08/S002_CAP_1X_ACCEPTED_TERMINAL/S002_CAP_1X_ACCEPTED_TERMINAL_sa.pdsprj` | accepted CAP solo | `C1 terminal` → `C0 terminal` → `00` → `C1 component` → two WIREs |
| `experiments/mixed_all_terminalized_hybrid_v46_temp_2026_07_12/01_pilot_final_zone_1x/P002_FINAL_ZONE_1X_sa.pdsprj` | accepted mixed donor | terminal records are contiguous; the single `00` sits immediately before the next component packet |
| `experiments/totalmix_38_growth_missing7_v1_temp_2026_07_15/05_tran_2p2s_43f/G02_42F_PLUS_TRAN_2P2S_TERMINALIZED_1X_sa.pdsprj` | local clean open | `C1`, resistor terminals, `00`, resistor packet; CAP's local `C0` has its own `00` immediately before CAP |
| `.../family_domain_isolation_v2/D06_CAP_POT_ONLY_1X_LEGACY_TERMINALIZED_sa.pdsprj` | `VGDVC.DLL` Fatal Error | `C1 terminal` → **extra `00`** → `C0 terminal` → `00` → CAP packet |
| `.../family_domain_isolation_v2/D07_RES_CAP_POT_ONLY_1X_LEGACY_TERMINALIZED_sa.pdsprj` | delayed local gate accepted | leading prefix terminates immediately before the resistor packet; no extra separator splits the CAP pair |

The D06 bare control opened normally.  A D08 diagnostic changing only CAP
link trailers from `02 00` to `01 00` still failed.  Thus the active-link
trailer is not the corrective factor.

## Complete observed difference set for the narrow D06/D07 question

- D06 and accepted CAP solo both have valid grid-aligned terminal contacts and
  nonzero short WIREs.
- D06 has unique final low-16 WIRE suffixes and matching terminal/component
  link fields.
- D06 is the only compared stream that inserts a standalone `00` *between*
  the localized CAP leading terminal and CAP's local terminal.
- The source emits this byte unconditionally at the localized R/C prefix in
  `attach_mixed_component_and_catalogue_bidir_terminals_to_project`, even if
  the current component still has locally emitted terminal records.

## Evidence-backed repair

Emit the localized-prefix separator only when the immediately following local
record is a component packet.  If the same group has local terminal records
(CAP's second terminal), leave the prefix records contiguous and let the
existing CAP branch emit its proven `00` before the component packet.

This rule derives from record class, not donor slot, family count, reference,
or component-stream order.  It supports uneven counts without copying or
duplicating any component bytes.

## Required gates after change

1. Fresh D06 CAP+POT 1× normal and cold reopen.
2. Fresh D07 R+CAP+POT 1× normal and cold reopen to protect the accepted
   prefix case.
3. Focused static mixed/totalmix regressions.
4. Fresh original-order 43-family 3× gate only after the two small controls
   pass.

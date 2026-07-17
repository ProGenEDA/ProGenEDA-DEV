# KiCad Website Integration Handoff

This package contains the KiCad generator executable and the files/notes needed
to add KiCad support to `newwebsite`.

Artifacts in this release:

- `../progen-kicad-portable-2026_07_17_kq26_clearance_v1.zip`: portable KiCad executable folder.
- `website_files/packages/component-registry/registries/KC-A.json`: KiCad serial
  registry with 103 supported component words.
- `website_files/apps/api/src/services/kicad-executable-service.mjs`: Node adapter
  for invoking the executable from the website API.
- `website_files/src/generation/kicadSupportedComponents.json`: frontend-ready
  KiCad supported component groups.
- `NEWEBSITE_KICAD_AUDIT.md`: exact Proteus-only points found in the website.
- `IMPLEMENTATION_CHECKLIST.md`: ordered implementation steps.

The current KiCad schematic pipeline is ready for the supported combination and
terminal flows. The bounded source-backed PCB stage is also ready: the same
main JSON can emit an accepted native board inside the project archive or through
the direct PCB-only endpoint. The website still needs integration work because
its generation UI and temporary backend bridge currently force Proteus.

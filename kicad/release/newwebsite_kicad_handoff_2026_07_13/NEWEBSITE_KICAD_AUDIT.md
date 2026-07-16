# newwebsite KiCad Integration Audit

Analyzed folder: `/home/zaruka/Documents/newwebsite`

## Already service-aware

- `apps/api/src/server.mjs` accepts `targetService` and whitelists `KC`.
- `apps/api/src/services/circuit-service.mjs` already maps `KC` to `KiCad`.
- `packages/serial-system/index.mjs` parses generic `<SERVICE>-<TABLE>-...`
  serials and can load service-specific registries.

## Proteus-only or Proteus-shaped points to change

- `packages/component-registry/registries/PR-A.json` is the only registry. Add
  `KC-A.json` from this handoff. KiCad uses uppercase Base36 component codes so
  the current website decoder does not collide lowercase Base62 codes.
- `src/temp/legacyGeneratorClient.ts` posts `targetService: 'PR'` and assumes
  `.pdsprj` fallback names. Add a selected target service and use `KC` when the
  user chooses KiCad.
- `apps/api/src/services/temp-generator-service.mjs` always calls the temporary
  Proteus bridge and does not pass `service`. Route `service === 'KC'` to the
  provided `generateWithKiCadExecutable` adapter.
- Add a PCB-only selection that routes `service === 'KC'` and output type
  `pcb_only` to `generatePcbOnlyWithKiCadExecutable`. It returns native
  `.kicad_pcb` only when the hosted PCB validator accepted the board.
- `packages/storage-adapter/local-storage-service.mjs` stores internal export
  copies under `export/PR/${exportFileName}`. Change that to
  `export/${service}/${exportFileName}`.
- `apps/api/src/server.mjs` returns `fileName: 'project.pdsprj'` from
  `POST /api/circuits/:serial/download`. Use the actual artifact file name.
- `src/generation/SupportedComponentsPage.tsx` is hardcoded with Proteus-era
  groups and copy. Add service tabs or a service filter and load the KiCad
  groups from `kicadSupportedComponents.json`.
- `src/generation/AnimatedDarkGeneratePage.tsx` locks KiCad in the target menu
  and visible copy says Proteus-ready. Unlock KiCad and pass the selected EDA to
  `generateWithTempLegacy`.
- `src/generation/NonAnimatedDarkWorkspace.tsx` has `.pdsprj` and Proteus status
  copy. Make it service/file-extension aware.
- `src/generation/HistoryPage.tsx` has a Proteus-only insight label and an empty
  KiCad logo path. The service filter already includes KiCad.
- Docs (`docs/RUNBOOK.md`, `docs/BACKEND.md`, `docs/ARCHITECTURE.md`,
  `docs/IMPLEMENTATION_AUDIT.md`) describe only PR-A/Proteus export examples.

## Generator boundary

The KiCad executable takes canonical ProGenEDA main JSON, not a raw natural
language prompt. The website therefore needs either:

1. a prompt-to-main-json route before invoking the KiCad adapter, or
2. an API payload that already includes `mainJson` for KiCad requests.

After `mainJson` exists, the executable fixes/validates it, generates KiCad
projects, creates user/internal artifacts, and writes validation manifests.

# Website KiCad Implementation Checklist

1. Copy `website_files/packages/component-registry/registries/KC-A.json` into
   `newwebsite/packages/component-registry/registries/KC-A.json`.
2. Copy `website_files/apps/api/src/services/kicad-executable-service.mjs` into
   `newwebsite/apps/api/src/services/kicad-executable-service.mjs`.
3. Add the `api.env.kicad.example` variables to `newwebsite/api.env`.
4. Update `apps/api/src/config.mjs` with `kicadExecutablePath` and `kicadWorkDir`.
5. In `apps/api/src/services/temp-generator-service.mjs`, route `service === 'KC'`
   to `generateWithKiCadExecutable({ mainJson, prompt, config })`.
6. Extend `/api/generate` to accept or obtain `mainJson` when `targetService` is
   `KC`. Keep natural prompt generation blocked until prompt-to-main-json is
   wired.
7. In `packages/storage-adapter/local-storage-service.mjs`, change internal
   bundle export path from `export/PR/...` to `export/${service}/...`.
8. In `apps/api/src/server.mjs`, return the stored artifact file name for
   `POST /api/circuits/:serial/download`.
9. Update `src/temp/legacyGeneratorClient.ts` to accept a selected service and
   stop hardcoding `targetService: 'PR'`.
10. Unlock KiCad in `src/generation/AnimatedDarkGeneratePage.tsx` and pass the
    selected service through the client.
11. Make download modal/shared serial/workspace copy service-aware; KiCad
    downloads are `PROGEN_KICAD_PROJECT.zip`.
12. Replace or extend `SupportedComponentsPage.tsx` with service tabs and import
    `kicadSupportedComponents.json` for the KiCad component menu.
13. Update docs/runbook examples with `KC-A` serial examples and `.zip` KiCad
    project exports.
14. Smoke test:

    ```bash
    ./progen-kicad-portable/progen-kicad run examples/ee215_diode_iv.json \
      --output-root /tmp/progen-kicad-smoke \
      --routing-mode combination
    ```

15. Website smoke test:

    - POST `/api/generate` with `targetService: "KC"` and canonical `mainJson`.
    - Confirm DB service is `KC`.
    - Confirm serial starts with `KC-A-`.
    - Confirm export artifact is `PROGEN_KICAD_PROJECT.zip`.
    - Confirm internal bundle contains `export/KC/PROGEN_KICAD_PROJECT.zip`.

# Newwebsite EasyEDA Pro Integration Audit

Audited baseline: `newwebsite` commit `a236ecdb509fbdba7322d4f62360e9f4435b9225`.

## Integrated Surfaces

- API configuration for executable, work, and example-library paths.
- Native executable adapter with NDJSON stage streaming and audit ZIP retention.
- `EA` generation dispatch for prompt-planned and direct canonical JSON input.
- Batch generation, artifact naming, serial registry, persistence, and download.
- Deterministic JSON validator/editor with guided and admin advanced modes.
- Registry-backed prompt planner and fixture examples.
- Example library containing all 300 descriptive circuits.
- Frontend target selectors, generation workspace, progress labels, and history.
- Supported Components page with all 59 logical names and explicit limits.
- EasyEDA Pro icon, landing/help/SEO wording, environment example, and docs.
- Production corpus runner and API integration documentation.

## Important Behavior

The website stores the `.eprj` as the public artifact and the executable's
internal ZIP inside private circuit metadata. Progress comes from completed
backend stages. A missing or failed native validation report causes generation
to fail; the website never publishes a premature or unvalidated artifact.

Prompt generation can use the configured OpenAI structured planner. With AI
disabled, direct JSON and deterministic examples remain available. The runtime
component and limit source of truth is `EA-A.json`, generated from the backend
catalogue rather than hand-maintained in React.

## Deliberate Non-Changes

- Proteus, KiCad, and LTspice adapters remain independent.
- Existing serial codes are unchanged; EasyEDA receives the separate `EA-A`
  namespace.
- EasyEDA project generation never imports from the KiCad backend.
- The installed EasyEDA desktop application is not a server dependency.
- The full proprietary desktop bundle and full standard library are not shipped.

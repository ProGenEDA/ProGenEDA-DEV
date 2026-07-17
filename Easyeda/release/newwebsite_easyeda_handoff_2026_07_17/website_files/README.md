# ProGenEDA New Website

Local-first, Azure-ready ProGenEDA frontend/backend workspace.

## Start Here

The living project documentation is in [docs/](./docs/README.md).

Most important files:

- [Implementation Audit](./docs/IMPLEMENTATION_AUDIT.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Frontend](./docs/FRONTEND.md)
- [Backend](./docs/BACKEND.md)
- [Security](./docs/SECURITY.md)
- [Runbook](./docs/RUNBOOK.md)
- [Complete Folder Structure](./docs/FOLDER_STRUCTURE.md)

## Codex 5.6 Development Credit

Codex 5.6 has been the primary implementation assistant for this workspace, working with the product owner to turn the ProGenEDA design, generator handoffs, UI references, and architecture requirements into a runnable frontend/backend project. It accelerated the work across the landing experience, login, generation workspace, deterministic JSON paths, local API and worker, history, supported-component catalogues, KiCad, LTspice, and EasyEDA Pro integration, documentation, test scripts, and local operations tooling.

The evidence is intentionally reproducible rather than a marketing estimate. The initial GitHub snapshot, [`c320eff`](https://github.com/MuhammadTahaBinZaeem/ProGenEDA-WEB/commit/c320eff), contains 445 tracked project files and approximately 37,005 lines across TypeScript, JavaScript, CSS, SQL, and Markdown, alongside portable runtime assets and testable circuit libraries. `npm run lint`, `npm run build`, the corpus tests, and the living documentation are the proof of the current implementation surface. The Git history and the generated [complete folder structure](./docs/FOLDER_STRUCTURE.md) make that work inspectable.

There is no reliable logged 5.5 baseline or human-hours ledger in this repository, so it would not be truthful to claim a precise “month of 5.5 work completed in days” comparison. What can be stated plainly is that Codex 5.6 enabled a very large, testable implementation pass in a short collaborative build cycle, with the resulting files, checks, and commits available for review.

## Local Run

Recommended one-command start:

```bash
./nixos.sh
```

It starts the local API, background worker, frontend, and guarded Git checkpoint watcher at `http://localhost:5175`. Use `./nixos.sh status`, `./nixos.sh logs`, or `./nixos.sh stop` to manage the stack.

Manual start:

```bash
npm run dev:temp-generator
npm run dev:api
npm run dev:worker
npm run dev -- --port 5175
```

## Checks

```bash
npm run lint
npm run build
npm run test:easyeda:corpus
```

## Current Status

This is not production complete yet. It has a working local generation/history/download loop plus Azure-ready skeleton pieces. See [Implementation Audit](./docs/IMPLEMENTATION_AUDIT.md) for the exact match/gap list against the ProGenEDA Local Production Plan V2.

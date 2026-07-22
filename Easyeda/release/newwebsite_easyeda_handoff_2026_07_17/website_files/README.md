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

The initial GitHub snapshot, [`c320eff`](https://github.com/MuhammadTahaBinZaeem/ProGenEDA-WEB/commit/c320eff), contains 445 tracked project files and approximately 37,005 lines across TypeScript, JavaScript, CSS, SQL, and Markdown, alongside portable runtime assets and testable circuit libraries. `npm run lint`, `npm run build`, the corpus tests, and the living documentation are the proof of the current implementation surface. The Git history and the generated [complete folder structure](./docs/FOLDER_STRUCTURE.md) make that work inspectable and reproducible.

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

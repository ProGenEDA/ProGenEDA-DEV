# Frontend

Last updated: 2026-07-14

## Stack

- React 19
- Vite 6
- TypeScript
- Three.js
- iconsax-react and lucide-react
- Static assets in `public/`

## Routes

Implemented app routes:

```text
/                  public scroll-story landing page
/login             login page
/generate          generation workspace
/history           history workspace
/supported-components  supported Proteus, KiCad, LTspice, and EasyEDA Pro registries
/terms-of-service  SEO legal page
/privacy-policy    SEO privacy page
/get-help          SEO help page
/prompt-guide      SEO prompt-writing and deterministic validation guide
```

`public/staticwebapp.config.json` uses SPA fallback for authenticated app routes and explicit static rewrites for public legal/help/prompt-guide routes. The build prerenders public HTML for `/`, `/get-help`, `/prompt-guide`, `/terms-of-service`, and `/privacy-policy` so search crawlers receive route-specific metadata and primary content without depending on JavaScript.

## Public Landing Page

Files:

```text
src/landing/LandingPage.tsx
src/landing/landingContent.ts
src/landing/landing.css
public/landing/
```

The home route is a white editorial scroll story for technical and investor review. It covers the user problem, market signals, complete intent-to-artifact pipeline, live product evidence, competitive positioning, internal validation evidence, business expansion paths, and roadmap. Claims, source links, pipeline stages, market figures, comparison rows, and roadmap copy are kept in `landingContent.ts` so the narrative can be revised without rebuilding the page structure.

The landing product shots are fresh captures of the running Generate and History workspaces. The social card is a live 1200 x 630 hero capture at `public/landing/progeneda-og.png`. The seven editorial story scenes are optimized WebP assets.

Responsive checks use native NixOS Chromium with desktop and 390 px mobile viewports. The phone comparison becomes labeled stacked records so no comparison column is hidden behind horizontal scrolling.

## Login Page

Current login is temporary:

- Email/password temp login.
- Google button is visual/placeholder.
- Terms acceptance stored locally.
- Login stores a temp session in local or session storage.
- Login navigates to `/generate`.

Production target:

- Firebase Authentication.
- Backend receives Firebase ID token.
- Backend verifies token using Firebase Admin SDK.
- Local temp session headers must be removed.

## Generation Page

Main file:

```text
src/generation/AnimatedDarkGeneratePage.tsx
```

Implemented modes:

- Animated dark mode.
- Non-animated dark mode.

Deferred:

- Animated light mode.
- Non-animated light mode.

Mode selection:

- User menu under the username.
- Stored in `localStorage` through `generationModeStorage.ts`.

Animated dark:

- Uses vendored Three.js tesseract animation.
- Keyboard W/Y/I was removed from app behavior by detaching the imported keydown handler.
- Prompt submit triggers forward animation.
- Failure triggers red branch.
- Successful download triggers reverse to blue.
- Uses the Three.js director's real 34-second forward duration as the expected wait.
- Shows deterministic executable-stage labels while the backend is working.
- After the expected duration, the top-right status changes to a clear hold message; the download dialog only appears after both the animation and backend result are complete.
- At twice the expected duration, the run fails with a clear simpler-circuit timeout message.

Non-animated dark:

- Uses `NonAnimatedDarkWorkspace.tsx`.
- Has static routing board and workspace state screens.
- Success wait is 25 seconds.
- Failure waits at least 10 seconds before returning to failed red prompt state.
- Uses a 25-second expected window and 50-second hard timeout.

Mobile behavior:

- Three.js animation is not mounted on mobile viewport.
- Mobile uses simplified prompt/status behavior.

## Shared Sidebar

File:

```text
src/generation/GenerationSidebar.tsx
```

Used by:

- Generate page.
- History page.
- Supported Components page.

Important:

```text
Do not fork or duplicate the sidebar for each dashboard page.
```

The sidebar owns:

- ProGenEDA brand.
- Navigation items.
- Sliding active nav indicator.
- Usage/tokens placeholder.
- Supported components card.
- User menu with mode/theme choices.

## History Page

File:

```text
src/generation/HistoryPage.tsx
```

Behavior:

- Calls `GET /api/history`.
- Displays metadata-only generation cards.
- Allows downloading successful exports.
- Allows copying serials.
- Shows error details for failed generations.
- Successful KiCad, LTspice, and EasyEDA Pro cards expose `Edit JSON`; Proteus cards remain disabled until the upgraded Proteus runtime is installed.
- The KiCad/LTspice/EasyEDA JSON Lab is a flat black modal with guided safe fields for all users and raw canonical JSON for demo/admin only.
- Filters by status/service.
- Client-side search over loaded results.

## Supported Components Page

File:

```text
src/generation/SupportedComponentsPage.tsx
```

The UI exposes four explicit component surfaces:

```text
Proteus      56 exact registry names (runtime audit pending)
KiCad .sch  103 supported schematic words
KiCad .pcb   34 audited footprint records / 15 physical mappings
LTspice .asc 7 donor-native stock-symbol families
```

The KiCad PCB surface is deliberately separate from schematic support. Its note communicates that source, pad-net, clearance, connectivity, overlap, and board-outline validation must pass before a board is downloadable.

Proteus registry target (the legacy exporter must still be audited before this is represented as an enforced runtime rule):

```text
Every listed integrated circuit is capped at 15 instances per circuit.
Other supported Proteus component types do not receive that per-part limit.
```

Current UI limitations:

- Pagination controls are visual/basic; cursor pagination is not wired deeply.
- Date picker is visual only.
- Search is not backend indexed.

## API Client

File:

```text
src/backend/apiClient.ts
```

Current behavior:

- Uses `VITE_PROGEN_API_URL`, defaulting to `http://127.0.0.1:3000`.
- Reads temp session from browser storage.
- Sends temp identity headers.

Production target:

- Read Firebase ID token.
- Send `Authorization: Bearer <id_token>`.
- Remove client-controlled identity headers.

## Temporary Legacy Generator Client

File:

```text
src/temp/legacyGeneratorClient.ts
```

Current behavior:

- Calls backend `POST /api/generate`.
- Returns backend-provided download URL/serial.
- Old direct blob handling remains as fallback.

Replacement rule:

```text
Replace this client boundary when the Azure generator service is ready.
Do not wire generator-specific logic through the UI components.
```

## SEO Frontend Work

Implemented:

- Legal/help content pages.
- `robots.txt`.
- `sitemap.xml`.
- `manifest.webmanifest`.
- Page metadata through `PageMeta`.

Future:

- Update sitemap when dashboard public/share pages are added.
- Add public serial landing pages when share-by-serial UI exists.

## UI Testing Notes

Commands:

```bash
npm run lint
npm run build
```

Playwright uses the native NixOS Chromium executable for local screenshots and layout audits. Fresh product captures live under `.local-runtime/screenshots/product/`; the landing scroll-story captures live under `.local-runtime/screenshots/landing-final/`.

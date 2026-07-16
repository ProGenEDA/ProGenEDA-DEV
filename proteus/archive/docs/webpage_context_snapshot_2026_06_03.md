# Webpage Context Snapshot - 2026-06-03

This snapshot captures the separate Progen web-app/deployment work. It is
intentionally stored apart from the main generator context so the next generator
session can resume from the Progen context snapshot without absorbing web-page
implementation details.

## Scope

Build and deploy a private web app wrapper for the current Progen generator.
The web app is separate from the main generator repo and lives locally at:

```text
D:\Coding\web app
```

The deployed private GitHub repo is:

```text
https://github.com/MuhammadTahaBinZaeem/progenlive
```

The repo is private and was pushed for Render deployment.

## Deployment Target

The project moved away from Hugging Face Spaces to Render Free.

Render setup expected by the user:

```text
Runtime: Docker
Instance type: Free
Repo: MuhammadTahaBinZaeem/progenlive
Required environment variables:
  GROQ_API_KEY
  MONGO_URI
```

No raw API keys, MongoDB connection strings, or Hugging Face tokens should be
stored in source files or committed snapshots.

## Web App Behavior

Main files:

```text
app.py
index.html
requirements.txt
Dockerfile
proteusgen
proteusgen.exe
progen_runtime/
deploy.py
tests/test_app_security.py
```

Implemented behavior:

- Login is required before circuit generation.
- Unauthenticated state reports that the user is not signed in.
- Logout clears browser-held credentials and returns the UI to signed-out state.
- App name changed to `Progen`.
- Supported components shown in the UI: resistor, capacitor, inductor.
- Removed visible workflow/internal private prompt text.
- Removed the terminal/session-output panel.
- Removed the previous glow/green-line styling.
- Generation accepts natural-language circuit descriptions after login.
- The app asks the configured 70b model to produce strict CircuitIR JSON.
- The app validates/repairs CircuitIR locally before running the generator.
- The response is a direct `.pdsprj` download.

## Model And Prompting

The web app uses the Groq OpenAI-compatible chat API with:

```text
model: llama-3.3-70b-versatile
```

User-facing errors mention `70b`, not provider internals.

The prompt pipeline includes a locked example book so the model sees many
description-to-JSON pairs before the user's request. The example bank includes
R-only, C-only, RC, and RCL families, including the 15 requested circuit
patterns plus 6-component and 21-component acceptance examples where available.

The model is not trusted blindly:

- Natural labels are normalized to the generator's safe two-character labels.
- Component graph outputs can be repaired into the locked group schema.
- Invalid model outputs retry with validation feedback.
- Invented component values are stripped unless the user prompt contains
  explicit units/values.

## Runtime Generator

The web deployment uses the copied runtime wrapper:

```text
proteusgen
progen_runtime/src/proteusgen/
```

The Docker image also copies:

```text
proteusgen.exe
```

The web app calls:

```text
generate-mixed-passives
generate-mixed-rcl
```

depending on the validated CircuitIR family.

## Render/GitHub Deployment State

Pushed private repo:

```text
MuhammadTahaBinZaeem/progenlive
```

Latest pushed commit from this session:

```text
8b8b0300fbd571b47ff0171d955ae1256de0fc6a
Prepare Progen for Render deployment
```

Important correction:

- The first push accidentally omitted runtime `.pdsprj` fixtures because a
  broad `.gitignore` rule ignored all `.pdsprj` files.
- This was fixed with:

```text
!progen_runtime/fixtures/pdsprj/*.pdsprj
```

- The corrected push includes 24 required runtime fixture projects.

## Security Work

`deploy.py` now targets private GitHub/Render staging only.

It no longer contains Hugging Face upload/token logic.

Deployment preflight behavior:

- Creates/clears isolated `deploy_staging`.
- Copies deploy files non-destructively.
- Scans staged files for raw credential prefixes.
- Requires `app.py` to read:

```text
os.getenv("MONGO_URI")
os.getenv("GROQ_API_KEY")
```

- Optionally force-pushes the isolated staging tree to:

```text
https://github.com/MuhammadTahaBinZaeem/progenlive.git
```

Secrets were not committed. Any keys pasted during the chat should still be
rotated because they appeared in chat/IDE context.

## Validation At Snapshot

Validated in `D:\Coding\web app`:

```text
python -m pytest tests -q
15 passed, 1 warning

python -m compileall app.py deploy.py tests progen_runtime\src
passed

python -m bandit -r app.py deploy.py proteusgen progen_runtime\src -q
clean

python deploy.py
staging security scan passed
```

Docker was not installed locally, so a local container build could not be run.
The Python app server from the web-app test remained running at:

```text
http://127.0.0.1:7860
```

## Local Test Modes

Placeholder mode:

```powershell
python -m pip install -r requirements.txt
$env:PROGEN_LOCAL_TEST_MODE = "1"
$env:PROGEN_LOCAL_AI_STUB = "1"
$env:PROGEN_TEST_USERNAME = "demo"
$env:PROGEN_TEST_PASSWORD = "demo"
python -m uvicorn app:app --host 127.0.0.1 --port 7860
```

Production local mode:

```powershell
python -m pip install -r requirements.txt
$env:MONGO_URI = "<set locally>"
$env:GROQ_API_KEY = "<set locally>"
python -m uvicorn app:app --host 127.0.0.1 --port 7860
```

## Resume Notes

For generator work, resume from:

```text
docs/progen_context_snapshot_2026_06_02.md
```

For web deployment work, resume from this file and the private GitHub repo
`MuhammadTahaBinZaeem/progenlive`.

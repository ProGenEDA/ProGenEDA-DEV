# Proteus repository consolidation validation — 2026-07-16

> **GPT-5.6 implementation.** GPT-5.6 repaired component placement,
> consolidated the shared terminal route and nonzero grid-attached wire
> contract, preserved research evidence, added the value/properties workflow
> and portable executable, automated validation, and established this
> repeatable repository validation record.

## Scope

This record validates the active `proteus/` layout after moving the current
runtime, tests, evidence, dated runners, experiments, and historical material
out of the repository root. It records relocation behavior; it does not claim
new terminal-family acceptance.

## Validation results

| Gate | Result |
| --- | --- |
| `compileall` over active source, tests, tools, and experiment runners | Passed |
| focused application tests | 6 passed |
| runner-backed relocation tests | 55 passed |
| catalogue tests | 46 passed, 8 expected failures |
| component-placer tests | 215 passed, 5 expected failures |
| full active test suite | 418 passed, 13 expected failures, 78 subtests passed |
| PyInstaller build | Passed on final merged `main`; `release/ProgenProteus.exe` rebuilt 2026-07-17 (`BE444F1827440A01BCEEDB7A05794C794926CC4FCC3D76605B40743BEF7BE947`) |
| executable JSON smoke test | Passed after the final rebuild; the R/C project report contains four terminal units and four nonzero terminal-to-pin WIRE records |
| Proteus 8 cold open / cold reopen | Passed after the final rebuild on a disposable executable-smoke copy; two 20-second cold opens, correct schematic title, no matching Bad Object Record, Fatal Error, LXLCORE, or library-dialog text, unchanged SHA-256 |

## Historical expected-failure policy

The 13 expected failures are intentionally retained diagnostic evidence rather
than silently skipped or “fixed” by weakening the current implementation:

- Four tests request `4017`, which is catalogue evidence but is not available
  from the locked runtime mega donor.
- Four 4027 scale/staging cases require the earlier rejected zero-length
  donor-contact WIRE route; active policy requires a nonzero grid-attached
  terminal-to-pin wire.
- Two 2N3904/2N4401 assertions expose remaining zero-length attachment
  behavior and therefore remain unpromoted research.
- One mixed 74HC08 layout case, one all-49 mix that contains explicitly
  blocked `FUSE`/`SWITCH`, and one strict 4511 donor-byte-parity case remain
  historical integration research, not active acceptance claims.

These are explicit `pytest.xfail` cases with individual reasons. They stay
visible in the test result while keeping current placement, package discovery,
and accepted two-pin routes protected from speculative changes.

## Repeatable local loader gate

Run from the repository root after generating a candidate:

```powershell
powershell -ExecutionPolicy Bypass -File proteus/active/tools/invoke_local_proteus_gate.ps1 `
  -Project out/candidate.pdsprj
```

The gate refuses to close an existing user-owned PDS/ISIS session. It copies
the candidate, launches only the copy with a hidden Proteus window, waits at
least 12 seconds, enumerates its actual window and child-window text for
loader errors, stops only the process it launched, cold-reopens the same copy,
and verifies that its SHA-256 remains unchanged. A Bad Object Record that
opens correctly still requires the separate disposable Ctrl+S comparison rule
from `AGENTS.md`; normally opening projects are never Ctrl+S'd by this gate.

## Inventory integrity

The final merged-main inventory check maps **37,286** files exactly once and
lists **1,339** retained local-only items explicitly. The active manifest
contains **1,009** active files; its current aggregate SHA-256 is intentionally
read from the generated manifest rather than copied here, so this narrative
record never makes the self-updating inventory stale.

The generator then self-checks each non-self-referential hash, inventory CSV,
ignored-local CSV, and active aggregate. The current result is `status: ok`.
See [`../inventory/active_manifest.json`](../inventory/active_manifest.json)
and [`../inventory/repository_map.csv`](../inventory/repository_map.csv).

The six historical `Project Backups`/`.workspace` files found during this
final gate are intentionally preserved only in the local ignored inventory,
not recommitted. This follows the explicit policy for reproducible Proteus
application state while retaining their original paths and hashes. The map
tool now avoids redundant path resolution for already-absolute walk paths,
which keeps the exhaustive Windows hash check practical without weakening its
SHA-256 coverage.

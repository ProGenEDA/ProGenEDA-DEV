# Observed Proteus Project Structure

These notes summarize behavior observed from user-created Proteus 8.13 project tests and one Proteus 8.16 sample.

## Container

Observed `.pdsprj` files behave as ZIP-style containers and extract into internal project files.

Observed Proteus 8.13 internal files:

```text
PROJECT.XML
ROOT.DSN
ROOT.CDB
SCRIPTS/PWRRAILS.DAT
```

## PROJECT.XML

Proteus 8.13 projects showed metadata like:

```xml
<TIMESTAMP RELEASE="813" FILEVER="830" ... />
```

A Proteus 8.16 sample showed `RELEASE="816"`.

Current understanding: PROJECT.XML stores version and timestamp metadata.

## ROOT.DSN

ROOT.DSN is the observed home of visible schematic data.

Observed strings include:

```text
ISIS SCHEMATIC FILE
ISIS CIRCUIT FILE
OBJECT DATA
TERMINAL
WIRE
COMPONENT
COMPONENT ID
COMPONENT VALUE
TERMINAL LABEL
WIRE LABEL
$TERINPUT
$TEROUTPUT
$TERPOWER
$TERGROUND
RESISTOR
```

Confirmed from tests:

- terminal-only projects changed ROOT.DSN while ROOT.CDB stayed unchanged
- terminal labels are represented in ROOT.DSN
- visible wires/stubs appear as WIRE records/objects in ROOT.DSN
- series/parallel/ladder topology changes are represented by ROOT.DSN changes

## ROOT.CDB

ROOT.CDB is the observed home of component metadata for resistor tests.

Confirmed from tests:

- resistor values are controlled by ROOT.CDB
- resistor reference names are controlled by ROOT.CDB
- CDB-only value/ref edits are reflected by Proteus after opening
- DSN-only value/ref edits can be normalized back from ROOT.CDB
- ROOT.CDB must exist for the tested projects to open safely

## SCRIPTS/PWRRAILS.DAT

This file stayed unchanged across early visible POWER/GROUND terminal and resistor-network tests.

For the first generator version, copy this file unchanged from a known-good template.

## Known save noise

- PROJECT.XML timestamp-like fields change between saves.
- ROOT.DSN has small save/session-like byte changes near the early metadata region in otherwise equivalent resaves.

## Remaining questions before resistor generator v0

- How to reliably reuse known-good resistor visual templates.
- How resistor, terminal, and wire-stub coordinates are represented.
- Whether terminal-on-pin can avoid short wire stubs.
- What minimum CDB seed is safest.
- Which ZIP repack options Proteus accepts.

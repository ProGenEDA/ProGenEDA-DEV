# Test Result: Blank Sheet / Missing Circuit Root Cause

## User test result

The user tested the terminal-style power/ground attempts:

```text
TERM_T01_6R_POWER_BRIDGE_GROUND_SHORTWIRE
TERM_T02_R21_POWER_BRIDGE_GROUND_SHORTWIRE
TERM_T03_6R_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
TERM_T04_R21_POWER_BRIDGE_GROUND_POWERLAYOUT_BRIDGE
```

Result:

```text
The circuit was missing / schematic opened as a blank sheet.
```

## Root cause found

The OBJECT DATA section was malformed in these terminal-bridge attempts.

Working DSN object streams begin like this:

```text
OBJECT DATA 00 <first object bytes...>
```

The broken terminal-bridge attempts began like this:

```text
OBJECT DATA <first object bytes...>
```

Specifically, the generated donor-bridge object stream was missing the required leading `00` object-data prefix byte before the donor bridge cluster.

## Why this happened

The V9 normal resistor object chunk begins with a generic `00` header byte.

When using a donor bridge, the script did:

```text
object_chunk = donor_bridge_cluster + normal_resistor_chunk[1:]
```

This dropped the normal chunk's leading `00`, but did not prepend a replacement `00` before the donor bridge.

Proteus then parsed the OBJECT DATA stream incorrectly, causing the visible circuit to disappear.

## Fix

For any donor-bridge object stream, prepend the required leading `00` byte:

```text
object_chunk = 00 + donor_bridge_cluster + normal_resistor_chunk[1:]
```

For two donor bridge clusters:

```text
object_chunk = 00 + power_bridge_cluster + ground_bridge_cluster + normal_resistor_chunk[1:]
```

## Corrected generation

A corrected fixed attempt has been generated at:

```text
experiments/power_bridge_ground_terminal_fixed_2026-05-29/
```

The corrected ZIP is:

```text
POWER_BRIDGE_GROUND_TERMINAL_FIXED_ATTEMPTS_2026_05_29.zip
sha256: 425147074434f122c917fefaf2783688b9beee2468dec2f80ef547337a8a43cb
```

## Rule going forward

When the generated object data begins with normal V9 records, the object chunk already starts with `00`.

When the generated object data begins with a donor-derived bridge cluster, the generator must explicitly prepend `00` before the donor cluster.

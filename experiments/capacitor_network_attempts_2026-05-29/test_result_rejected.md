# Test Result: First Capacitor Network Attempt Rejected

## User feedback

The first generated capacitor network pack was rejected by the user:

```text
CAPACITOR_NETWORK_ATTEMPTS_2026_05_29.zip
```

Affected attempts:

```text
CAP_NET_T01_6C_SAME_TOPOLOGY_AS_6R
CAP_NET_T02_21C_SAME_TOPOLOGY_AS_R21
```

## Reason

The generation pass was not careful enough. It repeated the capacitor donor group in a shallow way and used an unvalidated coordinate shift.

Main problems:

```text
1. sequential donor group repetition was used
2. resistor-style partitioned object order was not tested
3. capacitor centers were shifted by an assumed midpoint offset
4. no donor exact-rebuild guard was included before mutation
```

## Corrective action

A deeper V2 attempt was generated separately:

```text
experiments/capacitor_network_v2_attempts_2026-05-30/
```

V2 uses:

```text
partitioned object order
exact CAP_T02 template split/reassembly check
CDB builder exact-match check against CAP_T01 for n=1
resistor topology x/y anchors directly
fixed 1uF values for first validation
```

## Decision

Do not lock this first attempt.

# First 15 Resistor Tests Analysis

Source batch: user returned first subset of the 60-test resistor pack, plus additional project corpus files.

## Strong findings

### DSN controls visible component existence

Confirmed again:

- DSN with four resistors and CDB with one resistor opened with four visible resistors.
- After resave, Proteus rebuilt CDB metadata for the four visible resistors.
- CDB with extra resistor entries but DSN with one visible resistor opened with only one visible resistor.
- After resave, Proteus pruned CDB back to the visible DSN component set.

Conclusion: for visible schematic object count, ROOT.DSN wins.

### CDB controls resistor metadata

Confirmed again:

- Resistor refs and values live authoritatively in ROOT.CDB.
- ROOT.CDB can be rebuilt from DSN when entries are missing, but for deterministic generation we should still generate matching CDB entries.

### Arbitrary resistor values accepted

Observed accepted values in returned test data:

- `1`
- `10`
- `100`
- `330`
- `1k`
- `2k`
- `3k`
- `4k`
- `10k`
- `4.7k`
- `1M`
- `2,2M` observed; should retest `2.2M` with dot later

### Longer resistor refs accepted

Observed accepted refs:

- `R10`
- `RX1`
- `R100`
- `R_TEST`

The validator should allow alphanumeric and underscore refs beginning with a letter, but generation should still avoid duplicate refs.

### Coordinate scale discovered for resistor movement

Single-resistor movement tests showed ROOT.CDB unchanged and ROOT.DSN changed only in coordinate/visual data.

Observed coordinate deltas:

- one small grid movement approximately `254000` coordinate units
- one large grid movement approximately `2540000` coordinate units

X movement changed repeated X-coordinate fields.
Y movement changed repeated Y-coordinate fields.

This is enough for fixed-grid horizontal resistor layout in generator v0.

### Rotation/mirror is not needed for v0

Rotation/mirror tests changed ROOT.DSN visual data only. For resistor-generator v0, use fixed horizontal orientation and avoid rotation support.

### Terminal-only data remains DSN-only

Input terminal test confirmed terminal objects do not require ROOT.CDB. More precise terminal template mapping is still needed, but this is not blocking resistor networks if a full branch template is used.

## Redundancy conclusion

The original 60-test plan is now too broad. Many tests repeat already confirmed authority rules.

The remaining work before resistor-generator v0 should focus only on:

1. reusable branch template structure
2. terminal-on-pin versus short stub requirement
3. exact full-branch cloning behavior
4. coordinate placement for multiple branches
5. repacking stability
6. one final generated topology transformation test

## Recommended reduced next batch

Run a compressed set of 8 tests instead of continuing all 60.

See the latest chat guidance for the exact reduced list.

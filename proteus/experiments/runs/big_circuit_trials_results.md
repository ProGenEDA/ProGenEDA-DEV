# Big Circuit Trials Results

Source: user-tested `BIG_CIRCUIT_TRIALS_V813_DSN_PATCHED` pack.

## Version-control result

The ROOT.DSN version patch worked for the digital clock repack control.

BIG11 result:

- Opened normally in Proteus 8.13.
- No later-version ROOT.DSN warning reported after patching ROOT.DSN offsets 167/169 to 813/830.
- Matched original digital clock 100%.
- All sheets worked as intended.
- Save As succeeded.
- Part refs/names remained the same.

Conclusion: for Proteus 8.13 targeting, patch both PROJECT.XML and ROOT.DSN header version fields.

## Empty CDB result

Empty/minimal ROOT.CDB works well for many single-sheet or effectively single-sheet circuits, but it changes metadata.

Observed effects:

- Projects generally open and save.
- Proteus rebuilds ROOT.CDB on save.
- Part refs are regenerated/reordered.
- Node/input/output names stay stable.
- Simulation can match the control if the original control simulates.

## Multi-sheet finding

The digital clock project had multiple sheets in the original control. Empty CDB trials caused only the first sheet to remain visible, renamed generically as Root Sheet 1.

Observed:

- BIG01/BIG02 showed only first sheet/TIME_CORE-like content.
- Other clock sheets were missing.
- Refs were regenerated.
- Component list was not meaningfully damaged, but visible sheets were lost.

Conclusion: ROOT.CDB stores or strongly controls sheet/page list metadata. For multi-sheet projects, preserving or generating appropriate CDB sheet metadata is required.

## Foreign CDB finding

BIG09 used digital-clock DSN with foreign HomeTheater CDB. It opened and saved, but showed two sheets matching the foreign CDB sheet structure rather than all original clock sheets.

Observed:

- Two sheets appeared.
- Sheet names were generic/lost.
- Circuit content was still from the digital clock DSN.
- Refs were regenerated/changed.
- Simulation matched what was visible.

Conclusion: CDB sheet structure can gate which DSN sheets are exposed. Foreign CDB can sometimes open but is unsafe for reliable generation.

BIG10 used HomeTheater DSN with digital-clock CDB and failed to open. Conclusion: foreign CDB is not generally safe.

## Component-family findings from big trials

Empty CDB successfully opened and regenerated metadata for several non-resistor component families:

- 74HC/74LS digital ICs in the clock/time-core sheet
- ATMEGA328P + LCD/LM016L project
- LM741/op-amp/source analog project
- inductor/source/boost converter project
- JK/NAND DLD project

This suggests that for many components, DSN contains enough visual/device identity for Proteus to rebuild CDB metadata.

## Per-trial notes

### BIG01 digital clock + empty CDB

Opened and saved. Only first sheet remained visible. Time-core looked correct. Refs changed. 7-seg sheets were not visible.

### BIG02 digital clock + empty CDB + empty project shell

Opened, saved, simulated. Same behavior as BIG01: only first sheet remained; refs changed.

### BIG03 ATMEGA/LCD/home-theater + empty CDB

Opened and saved. Simulated with same error as control. Empty second sheet disappeared. Refs changed, but node/input/output names stayed.

### BIG04 metal detector + empty CDB

Both control and test failed with the same VGDVC.DLL access violation, so this does not count against the empty-CDB method.

### BIG05 ENA analog/opamp/source + empty CDB

Opened and saved. Refs reordered. Visual circuit accurate. Control simulated but test did not; likely due to regenerated metadata/model issue needing later source-specific test.

### BIG06 boost converter/inductor/source + empty CDB

Opened, saved, and simulated with exactly same result as control. Refs changed.

### BIG07 level1 DLD 7seg/logicprobe + empty CDB

Neither control nor test opened reliably. Control crashed 8.16. Not useful for method conclusion.

### BIG08 JK/DLD + empty CDB

Opened and saved. Refs changed. Same clock model error as control; replacing clock fixed both. Not a generator issue.

### BIG09 digital-clock DSN + HomeTheater CDB

Opened and saved. Two sheets appeared, suggesting CDB controls visible sheet list/count. Visible circuits were from clock DSN. Refs changed.

### BIG10 HomeTheater DSN + digital-clock CDB

Control opened but test failed. Foreign CDB is unsafe.

### BIG11 unchanged clock repack + V813 ROOT.DSN patch

Opened normally in Proteus 8.13, matched original completely, all sheets worked, Save As succeeded, refs stayed same.

## Updated generation strategy

For single-sheet circuits:

- DSN-heavy generation with minimal/empty CDB may be viable.
- Proteus can rebuild component metadata on first open/save.
- Refs may be regenerated unless CDB is generated/preserved.

For multi-sheet circuits:

- Preserve or generate CDB sheet metadata.
- Empty CDB collapses sheet visibility.
- Foreign CDB can expose wrong number of sheets and is unsafe.

For polished output:

- Generate/maintain CDB refs and values to avoid generic reordering.
- Use empty CDB only as a rapid trial mode, not final mode.

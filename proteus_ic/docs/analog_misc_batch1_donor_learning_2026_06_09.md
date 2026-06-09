# Analog/Misc Batch 1 Donor Learning - 2026-06-09

This note covers donor-derived analog/misc components supplied after the main
74-series donor batches. It does not promote these into the production route
yet and does not attempt mixed-family synthesis.

## Donor Folder

Imported donors:

```text
proteus_ic/donors/analog_misc_batch1
```

Families:

```text
NE555
NPN
PNP
LM741
ELEC-CAP
```

## Marker Notes

Observed Proteus markers:

```text
NE555    -> NE555
NPN      -> NPN
PNP      -> PNP
LM741    -> LM741
ELEC-CAP -> CAP-ELEC
```

The electrolytic capacitor donor uses `CAP-ELEC` in `ROOT.DSN`/`ROOT.CDB`, and
its donor terminal labels are blank.

## Terminal Policy

All visible pins/endpoints in the supplied donors use donor-native bidirectional
terminal records:

```text
$TERBIDIR only
no $TERINPUT
no $TEROUTPUT
```

Single-donor visible terminal counts:

```text
NE555     8
NPN       3
PNP       3
LM741     7
ELEC-CAP  2
```

RLC donor files include donor-native passive/source-terminal material. The
temporary generator preserves those whole chunks instead of rebuilding them.

## Generated Solo Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_analog_misc_batch1_solo_temp.py
```

Output:

```text
experiments/analog_misc_batch1_solo_temp_2026_06_09
experiments/ANALOG_MISC_BATCH1_SOLO_TEMP_2026_06_09.zip
```

Generated controls:

- `T00_*_SINGLE_EXACT_REPACK`
- `T01_*_SINGLE_E001_TRANSPLANT`
- `T02_*_SINGLE_LABEL_MUTATION`
- `T03_*_2X_UNIQUE_LABELS`
- `T04_*_4X_UNIQUE_LABELS` where a 4x donor exists
- `T05_ELEC_CAP_8X_UNIQUE_LABELS`
- `T06_*_RLC_DONOR_TRANSPLANT`

Automated result:

```text
0 static validation issues
python -m pytest tests -q => 104 passed, 78 subtests passed
```

Manual Proteus result:

```text
User reported every circuit in experiments/analog_misc_batch1_solo_temp_2026_06_09 works.
```

Treat this as acceptance for the solo donor-derived controls in this folder:
exact repack, E001 transplant, label mutation, scale controls, and whole RLC
donor transplants. This does not yet promote mixed-family analog synthesis.

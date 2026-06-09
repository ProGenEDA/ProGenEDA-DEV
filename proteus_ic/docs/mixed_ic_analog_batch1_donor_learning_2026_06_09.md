# Mixed IC/Analog Batch 1 Donor Learning - 2026-06-09

This note covers the first real mixed-donor corpus supplied after synthetic
mixed sequential IC generation failed. These donors are important because they
contain multiple IC families, R/C/L, and analog parts together in Proteus-made
projects.

## Donor Folder

Imported donors:

```text
proteus_ic/donors/mixed_ic_analog_batch1
```

Files:

```text
MIX_RCL_ANALOG_ONLY.pdsprj
MIX_SEQ_192_193_RCL_ANALOG.pdsprj
MIX_SEQ_4017_4020_4024.pdsprj
MIX_SEQ_192_193_4017_4020_4024_RCL_ANALOG.pdsprj
MIX_SEQ_COUNTERS_ALL_RCL_ANALOG.pdsprj
MIX_MISC_157_283_165_595_85_RCL_ANALOG.pdsprj
```

## Observed Pattern

All visible endpoints in these donors use bidirectional terminal records:

```text
$TERBIDIR only
no $TERINPUT
no $TEROUTPUT
```

Every donor also has matching bidirectional-terminal and `WIRE` counts. This is
strong evidence that large mixed sequential/analog projects should preserve
complete donor chunks and same-name bidirectional terminal topology.

## Conservative Generated Pack

Script:

```text
python tools/proteus_generation/2026-06-09/generate_mixed_ic_analog_batch1_temp.py
```

Output:

```text
experiments/mixed_ic_analog_batch1_temp_2026_06_09
experiments/MIXED_IC_ANALOG_BATCH1_TEMP_2026_06_09.zip
```

Generated controls per donor:

- exact deterministic repack
- whole object/CDB/device-section transplant into E001
- topology-preserving bidirectional-terminal label mutation

Automated result:

```text
0 static validation issues
python -m pytest tests -q => 107 passed, 78 subtests passed
archive_sha256: e3e744cd6c9941ac7d2ae184b247d8d679c7b55245ae082e9fcd5fb24e6a32c6
```

## Boundary

This batch does not yet prove arbitrary mixed synthesis by unit slicing,
same-length identity mutation, or subset removal. Those methods already failed
for sequential counters. The next safe step after this pack passes Proteus
testing is to test donor-subset removal or explicit user-provided mixed donor
templates, not to return to synthetic per-unit splicing.

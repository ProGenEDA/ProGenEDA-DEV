# ROOT.DSN Version Patch Finding

User reported Proteus/ISIS warning after opening the previous V813 metadata-patched trial pack:

```text
File 'ROOT.DSN' has a later version than this copy of ISIS.
```

This means PROJECT.XML version metadata alone is not enough.

## Observed DSN version fields

Comparing ROOT.DSN headers from known projects showed two little-endian uint16 values at fixed offsets:

```text
ROOT.DSN offset 167: release/version
ROOT.DSN offset 169: file format version
```

Observed examples:

```text
Proteus 8.04: offset 167 = 804, offset 169 = 805
Proteus 8.09: offset 167 = 809, offset 169 = 821
Proteus 8.13: offset 167 = 813, offset 169 = 830
Proteus 8.16: offset 167 = 816, offset 169 = 847
Proteus 9.00: offset 167 = 900, offset 169 = 907
```

## New pack generated

Generated file:

```text
BIG_CIRCUIT_TRIALS_V813_DSN_PATCHED.zip
```

Patch applied to every `.pdsprj` in the pack:

1. PROJECT.XML patched to `RELEASE="813" FILEVER="830"`.
2. ROOT.DSN patched:
   - offset 167 = uint16 little-endian 813
   - offset 169 = uint16 little-endian 830

## Interpretation

If BIG11 opens without the ROOT.DSN later-version warning, then the warning is controlled by the two ROOT.DSN header fields.

If BIG11 still warns, another internal version marker exists and must be located.

## Importance

This is the first concrete version-control mechanism for generated projects. A generator targeting Proteus 8.13 should set both PROJECT.XML metadata and ROOT.DSN header version fields.

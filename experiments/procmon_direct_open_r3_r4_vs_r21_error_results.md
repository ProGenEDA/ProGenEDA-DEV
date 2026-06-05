# ProcMon Direct Open: Valid R3/R4 vs Broken R21 Error Results

User captured fresh direct-open ProcMon logs for:

```text
r3normalopenfromprojectfilesdirectly.CSV
r4normalopenfromprojectfilesdirectly.CSV
r21errorisisopenfromprojectfilesdirectly.CSV
r21errorvg..openfromprojectfilesdirectly.CSV
```

## Main conclusion

The two broken R21 logs load a strict subset of the modules loaded by normal R3/R4 openings.

The broken files reach the schematic stack:

```text
ISIS.DLL
SYNTAX.DLL
PRIMS.dll
VSMDEBUG.dll
LOADERS.DLL
```

Then they stop before later successful-open modules such as:

```text
ARES.DLL
ELECTRA.DLL
IMPORTER.dll
DXP.dll
VSMEDIT.dll
VSMSTUDIO.DLL
OpenCascade/CITF stack: CITFSTEP.dll, TK*.dll, FreeImage.dll, FreeType.dll
```

This strongly suggests the malformed R21 files fail during early schematic decode / object-model / rendering setup, not during SPICE simulation or a separate legacy converter path.

## Module counts

```text
R3_normal_direct:      69,965 events, 80 Proteus BIN modules
R4_normal_direct:      80,386 events, 85 Proteus BIN modules
R21_ISIS_direct:       48,324 events, 42 Proteus BIN modules
R21_VGDVC_direct:      48,319 events, 42 Proteus BIN modules
```

## Focused module presence

```text
module        R3 normal   R4 normal   R21 ISIS   R21 VGDVC
ISIS.DLL      yes         yes         yes        yes
VGDVC.DLL     yes         yes         yes        yes
SYNTAX.DLL    yes         yes         yes        yes
PRIMS.dll     yes         yes         yes        yes
LOADERS.DLL   yes         yes         yes        yes
NETLIST.dll   yes         yes         yes        yes
IMPORTER.dll  yes         yes         no         no
ARES.DLL      yes         yes         no         no
ELECTRA.DLL   yes         yes         no         no
DXP.dll       yes/no*     yes         no         no
DSNCVT40.DLL  no          no          no         no
IDSCVT40.DLL  no          no          no         no
OBJITF.DLL    no          no          no         no
SPICEINP.DLL  no          no          no         no
SPICESIM.DLL  no          no          no         no
```

`DXP.dll` appeared in the R4 direct normal log and earlier normal opens; not important enough to treat as the cause.

## What this weakens

The filename-based suspicion around these modules is weakened for normal `.pdsprj` open:

```text
DSNCVT40.DLL
IDSCVT40.DLL
OBJITF.DLL
SPICEINP.DLL
SPICESIM.DLL
```

They were not observed as active modules in the normal or broken direct-open logs.

## What this strengthens

The active open/decode path is likely inside:

```text
ISIS.DLL
SYNTAX.DLL
PRIMS.dll
LOADERS.DLL
VGDVC.DLL downstream
```

## Interpretation of R21 ISIS vs R21 VGDVC

Both broken R21 logs have almost the same active Proteus-specific module set and stop before the successful-open post-load modules.

The difference between `ISIS.DLL` and `VGDVC.DLL` error types likely reflects how far the malformed object graph gets:

```text
ISIS.DLL error  -> parser/deserializer/object-structure failure
VGDVC.DLL error -> malformed object accepted far enough to reach visual drawing/rendering
```

It does not point to a separate converter DLL.

## Generator implication

The failure remains a `ROOT.DSN` structure problem, probably around:

```text
object records
section boundary bytes
second ISIS CIRCUIT FILE pointer
CCT000 / __DEFAULT__ pointer fields
sheet object registry / object count / component binding
```

## Next best data

The highest-value next capture is not more normal opens. It is:

```text
1. open a generated file that gives yellow 'circuit corrupt but repaired'
2. save it
3. return the original generated project and the Proteus-resaved project
4. diff generated ROOT.DSN vs resaved ROOT.DSN
```

That will show exactly what Proteus repaired.

# Local `D:/arch/outtt` Reference, 2026-05-30

## User Instruction

The user provided this local folder as an additional first-look reference:

```text
D:/arch/outtt
```

They said it contains source/code details for important DLLs and should be checked first when needed.

## Observed Top-Level Contents

High-level inspection showed:

```text
BIN/
DATA/
DRIVERS/
GhidraTempProj/
HELP/
LICENCE/
Tools/
Translations/
error_log.txt
unins000.exe.cpp
```

Notable decompiled outputs include:

```text
BIN/ISIS.DLL.cpp
BIN/VGDVC.DLL.cpp
BIN/DSIM.DLL.cpp
BIN/SPICEINP.DLL.cpp
BIN/PRIMS.dll.cpp
BIN/LOADERS.DLL.cpp
BIN/DSNCVT40.DLL.cpp
BIN/IDSCVT40.DLL.cpp
BIN/PROSPICE.DLL.cpp
```

## Policy For Use

Use this folder as a first-look local diagnostic reference for:

- crash/error names
- symbol strings
- file-format markers
- parser/loader clues
- narrowing experiments

Do not use it to:

- modify Proteus executables
- bypass licensing
- copy proprietary implementation code into the generator
- replace empirical validation from user-created `.pdsprj` projects

Any rule inferred from this folder must still be corroborated by generated project behavior before being promoted into locked generator logic.

# E001 Empty Project Base

User provided a new known-good empty Proteus 8.13 project to use as the base sheet from now on.

Source upload:

```text
E001_empty_project.zip
```

Extracted project:

```text
E001_empty_project/New Project.pdsprj
```

Internal files:

```text
PROJECT.XML
ROOT.DSN
ROOT.CDB
SCRIPTS/PWRRAILS.DAT
```

Observed metadata:

```xml
<TIMESTAMP RELEASE="813" FILEVER="830" ... />
```

ROOT.DSN version header:

```text
offset 167 = 813
offset 169 = 830
```

ROOT.CDB:

```text
size = 118 bytes
strings = ROOT, Master Sheet
```

Conclusion:

Use this E001 project as the default base shell for future generated single-sheet trials instead of any later-version or uncertain DLDLab13 shell.

Important correction:

The previous P2 empty-sheet NAND trial pack used a bad base sheet, and therefore all trials failed before testing the generation idea. Those failures should not be treated as evidence against the object-composition idea.

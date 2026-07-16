# Main Learning

This folder stores long-form human-readable learning documents for the Proteus generator project.

## Current learning PDFs generated locally

The following files were generated in the ChatGPT sandbox and should be copied into this folder manually if binary storage is required:

```text
resistor_E0_R1_R2_R3_R4_pattern_comparison.pdf
resistor_E0_R1_R2_R3_R4_full_byte_diff_no_green.pdf
resistor_E0_R1_R2_R3_R4_diff_no_green_artifacts.zip
resistor_E001_R1_R4_full_comparison.pdf
resistor_E001_R1_R4_diff_only_with_generated_attempt.pdf
resistor_diff_only_with_generated_attempt_artifacts.zip
```

## Why the PDFs are not stored directly here yet

The GitHub connector available in this chat is reliable for UTF-8 text files. Direct binary upload is not exposed through the simple contents API wrapper in this environment. Base64 text storage is possible, but large PDFs create very large text commits and are awkward to maintain.

For now, the PDF files are delivered as sandbox artifacts in the chat and this folder records the intended GitHub location and restore policy.

## Restore policy if base64 chunks are added later

If a file is stored as `.base64` or split into `part_001.b64`, `part_002.b64`, etc., restore it with:

```bash
cat part_*.b64 > file.pdf.base64
base64 -d file.pdf.base64 > file.pdf
```

PowerShell equivalent:

```powershell
$txt = (Get-Content part_*.b64 -Raw)
[IO.File]::WriteAllBytes("file.pdf", [Convert]::FromBase64String($txt))
```

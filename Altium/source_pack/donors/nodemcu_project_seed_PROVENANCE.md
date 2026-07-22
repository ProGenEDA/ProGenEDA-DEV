# Altium Project Descriptor Donor

`nodemcu_project_seed.PrjPcb` is a compact exact-section extraction from the
MIT-licensed NodeMCU Altium project descriptor. It retains the donor's
`Design`, `Preferences`, first schematic `Document`, and `Configuration`
sections. The unrelated PCB document and output-job sections were omitted.

- Repository: `https://github.com/nodemcu/nodemcu-devkit`
- Source file: `NODEMCU_ESP12.PrjPCB`
- Source commit: `587a0881f7ee9c02b628323909afa40c92162c1a`
- Original file SHA-256: `933e4c4cca539041148132a8d02ee6901b4c0c7e0d2093c6082161705737e957`
- License: MIT; preserved in `NODEMCU_MIT_LICENSE.txt`

Generation changes only `DocumentPath` in the extracted template. The
template hash is pinned by the project-descriptor module.

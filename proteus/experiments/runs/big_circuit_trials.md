# Big Circuit Trial Pack

Purpose: move from small component tests to aggressive whole-circuit trials.

## Core hypothesis

For complex Proteus projects, `ROOT.DSN` may preserve visible schematic existence/topology for many component types, while `ROOT.CDB` can sometimes be rebuilt or normalized by Proteus after opening/saving.

This is a deliberate documented leap of faith based on previous resistor tests:

- `ROOT.DSN` controls visible object existence.
- `ROOT.CDB` controls resistor metadata when present.
- missing CDB entries can sometimes be rebuilt from DSN.

## Trial pack generated

Generated pack: `BIG_CIRCUIT_TRIALS_PACK.zip`

Included trials:

1. `BIG01_digital_clock_empty_cdb` — digital clock DSN + empty CDB.
2. `BIG02_digital_clock_empty_cdb_empty_project_xml` — digital clock DSN + empty CDB + empty project metadata shell.
3. `BIG03_home_theater_atmega_lcd_empty_cdb` — ATMEGA/LCD controller DSN + empty CDB.
4. `BIG04_metal_detector_pic_lcd_empty_cdb` — PIC/LCD/74HC4066/CD4093 project DSN + empty CDB.
5. `BIG05_ena_analog_opamp_sources_empty_cdb` — analog LM741/source circuit DSN + empty CDB.
6. `BIG06_boost_converter_inductor_source_empty_cdb` — inductor/source/boost circuit DSN + empty CDB.
7. `BIG07_level1_7seg_logicprobe_empty_cdb` — DLD level-1 7-seg/logical project DSN + empty CDB.
8. `BIG08_jk_flipflop_dld_empty_cdb` — JK/DLD lab circuit DSN + empty CDB.
9. `BIG09_hybrid_clock_dsn_home_theater_cdb` — digital clock DSN + foreign HomeTheater CDB.
10. `BIG10_hybrid_home_theater_dsn_clock_cdb` — HomeTheater DSN + foreign digital clock CDB.
11. `BIG11_repack_control_digital_clock_no_change` — unchanged digital clock extract/repack baseline.

## Expected interpretation

If BIG11 fails, repacking method is suspect.

If BIG11 passes and BIG01/BIG03/BIG04 pass, the project can take a major shortcut: for new IC-heavy circuits, focus on DSN templates first and treat CDB as rebuildable/normalizable in early generator versions.

If empty-CDB versions fail but foreign-CDB versions pass, then a non-empty CDB seed may be required.

If both empty and foreign-CDB versions fail for IC-heavy projects, component-specific CDB generation remains necessary.

## User feedback needed

For each trial:

- opens yes/no
- visually matches intended source yes/no
- major parts visible yes/no
- Save As succeeds yes/no
- return resaved `.pdsprj` if possible

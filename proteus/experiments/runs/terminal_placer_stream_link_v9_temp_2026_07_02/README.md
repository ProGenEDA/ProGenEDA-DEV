# Terminal Placer Stream-Link V9

This pack targets the rejected V7 N07-N09 failure without selecting a new
circuit donor. The shared terminal placer:

1. consumes the component placer + beautifier output;
2. preserves that component order and every unsupported packet;
3. schema-encodes `$TERBIDIR` and canonical 50-byte WIRE records;
4. builds ROOT.DSN;
5. rebases both active link copies from the final associated WIRE address.

The decoded Proteus 8.13 formula is:

```
(object_chunk_absolute_start + full_wire_marker_offset - 24) & 0xffff
```

Test V9_01 through V9_06 first, then V9_07, V9_08, and V9_09. For each file
check: no Bad Object Record, terminals and short wires render, wires touch the
correct pins, Ctrl+S/reopen preserves them, and simulation/netlist opens.

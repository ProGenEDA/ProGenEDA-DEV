#!/usr/bin/env python3
# V6 exact method summary: terminal label patch fix.
# Full executable code is included inside the local artifact zip as generation_code_used.py.
# Key fix: do not search for newly inserted label bytes when patching terminal label coordinates.
# Patch known fixed label/coordinate offsets instead.

from __future__ import annotations
import struct

def i32(x:int):
    return struct.pack('<i', x)

def patch_terminal_fixed(template: bytearray, label: str, sx: int, sy: int, lx: int, ly: int, kind: str, serial: int = 0, suffix_mode: str = 'keep') -> bytes:
    r = bytearray(template)
    lab = label.encode('ascii')
    if len(lab) != 2:
        raise ValueError(label)

    # Terminal symbol coordinates.
    r[1:5] = i32(sx)
    r[5:9] = i32(sy)

    # V5 bug:
    #   patch_label_2 inserted the label, then r.find(new_label) was used to locate the label for coordinate patching.
    #   For labels like B6, the same two bytes can occur inside binary coordinate fields.
    #   That caused label-coordinate writes to land at the wrong byte offset.
    #
    # V6 fix:
    #   Use fixed offsets from the donor terminal schema.
    if kind == 'in':
        len_off = 30
        label_off = 31
        coord_off = 33
        assert r[len_off] == 2
    elif kind == 'out':
        len_off = 31
        label_off = 32
        coord_off = 34
        assert r[len_off] == 2
    else:
        raise ValueError(kind)

    r[label_off:label_off+2] = lab
    r[coord_off:coord_off+4] = i32(lx)
    r[coord_off+4:coord_off+8] = i32(ly)

    if suffix_mode == 'unique':
        base = 0x0159 if kind == 'in' else 0x018b
        seq = (base + serial * 0x01be) & 0xffff
        r[-4:-2] = struct.pack('<H', seq)
        r[-2] = 0x01
        r[-1] = 0x00

    return bytes(r)

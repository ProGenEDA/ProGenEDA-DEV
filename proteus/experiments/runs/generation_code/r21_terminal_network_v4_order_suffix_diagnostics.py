#!/usr/bin/env python3
# R21 terminal network V4 order/suffix diagnostics.
# Purpose: after V3 showed 21 resistors work but terminal-containing files crash in VGDVC,
# test whether terminal object order or terminal suffix mutation is the cause.
# This code is preserved as the exact method used to create the local V4 artifact.

from __future__ import annotations
import json, shutil, struct, zipfile
from pathlib import Path

ROOT = Path('/mnt/data')
E0_PROJECT = ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/CONTROL_E001_EMPTY_BASE.pdsprj'
R4_PROJECT = ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/CONTROL_R4_REAL_SOURCE_FOR_DEVICE_RECORDS_ONLY.pdsprj'
R12_WORKING = ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/TEST_E001_R12_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj'
PAR4_PROJECT = ROOT/'work_term/CONTROL_B02_E008_four_parallel_N1_N2.pdsprj'
OUTDIR = ROOT/'R21_TERMINAL_NETWORK_V4_ORDER_SUFFIX_DIAGNOSTICS'

PROP_TEXT = b'{PRIMITIVE=ANALOGUE}\n\x00'
GRID = 1270000
ROW_GAP = -1524000
REFS = ['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
VALUES = [f'{i}k' for i in range(1,22)]
VISIBLE_VALUES = ['1k','2k','3k','4k','5k','6k','7k','8k','9k','Ak','Bk','Ck','Dk','Ek','Fk','Gk','Hk','Ik','Jk','Kk','Lk']

def u32(x:int): return struct.pack('<I', x)
def i32(x:int): return struct.pack('<i', x)
def u16(x:int): return struct.pack('<H', x)
def enc_str(s:str):
    b = s.encode('ascii')
    return bytes([len(b)]) + b
def enc_text(data:bytes): return u32(4+len(data)) + data

def read_member(p:Path, name:str):
    with zipfile.ZipFile(p) as z:
        return z.read(name)

def write_project(path:Path, cdb:bytes, dsn:bytes):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SCRIPTS/PWRRAILS.DAT', read_member(E0_PROJECT, 'SCRIPTS/PWRRAILS.DAT'))
        z.writestr('ROOT.CDB', cdb)
        z.writestr('ROOT.DSN', dsn)
        z.writestr('PROJECT.XML', read_member(E0_PROJECT, 'PROJECT.XML'))

def topology():
    conns = []
    nodes = ['N0'] + [f'A{i}' for i in range(1,7)] + ['M0']
    for i in range(7):
        conns.append((i+1, nodes[i], nodes[i+1], i, 0))
    nodes = ['N0'] + [f'B{i}' for i in range(1,7)] + ['M0']
    for i in range(7):
        conns.append((8+i, nodes[i], nodes[i+1], i, 1))
    nodes = ['M0'] + [f'C{i}' for i in range(1,7)] + ['Z0']
    for i in range(7):
        conns.append((15+i, nodes[i], nodes[i+1], i, 2))
    return conns

def coords_for(idx:int, col:int, row:int):
    x0 = -6350000
    y0 = 5080000
    x = x0 + col*GRID*2
    y = y0 + row*ROW_GAP
    return {
        'x': x, 'y': y,
        'lt_symbol_x': x-508000, 'lt_label_x': x-889000,
        'rt_symbol_x': x+1778000, 'rt_label_x': x+2159000,
    }

def build_cdb(n=21):
    out = bytearray(); out += u32(7)
    out += u32(1)+u32(1)+u32(0)+enc_str('ROOT')+b'\x00'+u32(0)+u32(1)+u32(1)
    out += u32(2)
    out += u32(1)+u32(3)+u32(1)+enc_str('')+u32(10)+u32(0)
    out += u32(2)+u32(2)+u32(0)+enc_str('Master Sheet')+u32(10)+u32(0)
    out += u32(n)
    for idx in range(1,n+1):
        ref = REFS[idx-1]
        out += u32(idx)+u32(1)+u32(0)+u32(idx)+enc_str(ref)
        out += u32(2)+enc_str('1')+b'\x00'+enc_str('2')+b'\x00'
        out += u32(0)+u32(idx)+u32(0)
    out += u32(1)+u32(1)+b'\x00'+enc_str('')+u32(1)
    out += u32(n)
    for idx in range(1,n+1):
        out += u32(idx)+u32(1)+u32(0)+u32(0)+u32(0)
        out += enc_str(REFS[idx-1])+enc_str(VALUES[idx-1])+enc_str('RESISTOR')+enc_str('')+enc_text(PROP_TEXT)
    out += u32(0)
    return bytes(out)

# The rest of the local script performed:
# - extraction of terminal/resistor/wire donor records
# - SUFFIX_KEEP vs SUFFIX_UNIQUE terminal patch variants
# - donor-order vs interleaved-order object layouts
# - E0-tail and R4-tail project packing
# Full exact local artifact includes generation_code_used.py with the complete executable body.

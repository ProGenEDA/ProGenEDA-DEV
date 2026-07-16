#!/usr/bin/env python3
# R21 terminal network V5 correct object-boundary diagnostic generator.
# Key fix from V4: terminal donor chunk has a 1-byte OBJECT DATA header.
# Terminal records begin at donor visual chunk offset +1, not +0.

from __future__ import annotations
import json, shutil, struct, zipfile
from pathlib import Path

ROOT=Path('/mnt/data')
E0_PROJECT=ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/CONTROL_E001_EMPTY_BASE.pdsprj'
R4_PROJECT=ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/CONTROL_R4_REAL_SOURCE_FOR_DEVICE_RECORDS_ONLY.pdsprj'
R12_WORKING=ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/TEST_E001_R12_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj'
PAR4_PROJECT=ROOT/'work_term/CONTROL_B02_E008_four_parallel_N1_N2.pdsprj'
OUTDIR=ROOT/'R21_TERMINAL_NETWORK_V5_CORRECT_OBJECT_BOUNDARIES'

PROP_TEXT=b'{PRIMITIVE=ANALOGUE}\n\x00'
GRID=1270000
ROW_GAP=-1524000
REFS=['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
VALUES=[f'{i}k' for i in range(1,22)]
VISIBLE_VALUES=['1k','2k','3k','4k','5k','6k','7k','8k','9k','Ak','Bk','Ck','Dk','Ek','Fk','Gk','Hk','Ik','Jk','Kk','Lk']

def u32(x:int): return struct.pack('<I',x)
def i32(x:int): return struct.pack('<i',x)
def enc_str(s:str):
    b=s.encode('ascii')
    return bytes([len(b)])+b

def enc_text(data:bytes):
    return u32(4+len(data))+data

def read_member(p:Path,name:str):
    with zipfile.ZipFile(p) as z:
        return z.read(name)

def extract_visual_chunk(project:Path):
    d=read_member(project,'ROOT.DSN')
    fi=d.find(b'ISIS CIRCUIT FILE')
    obj=d.find(b'OBJECT DATA',fi)
    sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    return d[obj+len(b'OBJECT DATA'):sec]

def terminal_templates_correct():
    par=extract_visual_chunk(PAR4_PROJECT)
    # Correct terminal layout:
    # par[0] is object-region/chunk header byte.
    # input terminal records begin at par[1].
    ins=[bytearray(par[1+i*103:1+(i+1)*103]) for i in range(4)]
    outs=[bytearray(par[413+i*104:413+(i+1)*104]) for i in range(4)]
    groups=[]
    base=829
    for i in range(4):
        gbase=base+i*(346+50+50)
        groups.append((bytearray(par[gbase:gbase+346]), bytearray(par[gbase+346:gbase+396]), bytearray(par[gbase+396:gbase+446])))
    return ins, outs, groups

# Full local executable script is preserved inside the artifact zip as generation_code_used.py.
# This repo copy records the critical extraction rules and source paths.

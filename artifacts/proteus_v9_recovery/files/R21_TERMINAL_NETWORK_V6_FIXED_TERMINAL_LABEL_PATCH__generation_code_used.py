from __future__ import annotations
import json, shutil, struct, zipfile
from pathlib import Path
ROOT=Path('/mnt/data')
V5=ROOT/'v5'
OUTDIR=ROOT/'R21_TERMINAL_NETWORK_V6_FIXED_TERMINAL_LABEL_PATCH'
BASE_RES_DSN=V5/'TEST_R21_V5_RESISTORS_ONLY_CORRECT_BOUNDARY_E0_TAIL.ROOT.DSN.bin'
BASE_RES_CDB=V5/'TEST_R21_V5_RESISTORS_ONLY_CORRECT_BOUNDARY_E0_TAIL.ROOT.CDB.bin'
CONTROL=V5/'CONTROL_E001_EMPTY_BASE.pdsprj'
ALL_TERMS_DSN=V5/'TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_E0_TAIL.ROOT.DSN.bin'
ALL_WIRES_DSN=V5/'TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_WIRES_E0_TAIL.ROOT.DSN.bin'
REFS=['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
VALUES=[f'{i}k' for i in range(1,22)]
VISIBLE_VALUES=['1k','2k','3k','4k','5k','6k','7k','8k','9k','Ak','Bk','Ck','Dk','Ek','Fk','Gk','Hk','Ik','Jk','Kk','Lk']
GRID=1270000
ROW_GAP=-1524000

def u32(x:int): return struct.pack('<I',x)
def i32(x:int): return struct.pack('<i',x)
def u16(x:int): return struct.pack('<H',x)

def read_member(p:Path,name:str):
    with zipfile.ZipFile(p) as z: return z.read(name)

def write_project(path:Path,cdb:bytes,dsn:bytes):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SCRIPTS/PWRRAILS.DAT',read_member(CONTROL,'SCRIPTS/PWRRAILS.DAT'))
        z.writestr('ROOT.CDB',cdb)
        z.writestr('ROOT.DSN',dsn)
        z.writestr('PROJECT.XML',read_member(CONTROL,'PROJECT.XML'))

def object_chunk(d:bytes):
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    return d[obj+len(b'OBJECT DATA'):sec]

def topology():
    conns=[]
    nodes=['N0']+[f'A{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((i+1,nodes[i],nodes[i+1],i,0))
    nodes=['N0']+[f'B{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((8+i,nodes[i],nodes[i+1],i,1))
    nodes=['M0']+[f'C{i}' for i in range(1,7)]+['Z0']
    for i in range(7): conns.append((15+i,nodes[i],nodes[i+1],i,2))
    return conns

def coords_for(col,row):
    x0=-6350000; y0=5080000
    x=x0+col*GRID*2; y=y0+row*ROW_GAP
    return dict(x=x,y=y,lt_symbol_x=x-508000,lt_label_x=x-889000,rt_symbol_x=x+1778000,rt_label_x=x+2159000)

# Extract known-safe resistor records from working resistor-only DSN.
def resistor_records():
    ck=object_chunk(BASE_RES_DSN.read_bytes())
    assert ck[:2]==b'\x00\x00'
    recs=[]
    p=2
    for i in range(21):
        recs.append(bytearray(ck[p:p+346])); p+=346
    assert all(r.find(b'COMPONENT ID')>0 for r in recs)
    return recs

# Extract terminal templates from V5 all-terms chunk, but treat them only as records.
# The V5 problem was not template boundary by this point; it was patching label coordinates by searching for the new label bytes.
def terminal_templates():
    ck=object_chunk(ALL_TERMS_DSN.read_bytes())
    assert ck[0]==0
    in_t=[bytearray(ck[1+i*103:1+(i+1)*103]) for i in range(4)]
    out_start=1+21*103
    out_t=[bytearray(ck[out_start+i*104:out_start+(i+1)*104]) for i in range(4)]
    return in_t,out_t

def wire_templates():
    ck=object_chunk(ALL_WIRES_DSN.read_bytes())
    start=1+21*103+21*104+21*346
    ws=[]
    for i in range(42):
        ws.append(bytearray(ck[start+i*50:start+(i+1)*50]))
    return ws

def patch_terminal_fixed(template:bytearray, label:str, sx:int, sy:int, lx:int, ly:int, kind:str, serial:int=0, suffix_mode='keep'):
    r=bytearray(template)
    lab=label.encode('ascii')
    if len(lab)!=2: raise ValueError(label)
    # The old bug: finding the new label anywhere corrupted records when bytes like B6 occurred inside coordinate fields.
    # Correct: patch fixed label field offsets observed in donor terminal records.
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    if kind=='in':
        len_off=30; label_off=31; coord_off=33
        assert r[len_off]==2
    else:
        len_off=31; label_off=32; coord_off=34
        assert r[len_off]==2
    r[label_off:label_off+2]=lab
    r[coord_off:coord_off+4]=i32(lx); r[coord_off+4:coord_off+8]=i32(ly)
    if suffix_mode=='unique':
        base=0x0159 if kind=='in' else 0x018b
        seq=(base+serial*0x01be)&0xffff
        r[-4:-2]=u16(seq); r[-2]=0x01; r[-1]=0x00
    return bytes(r)

def patch_wire_fixed(template:bytearray,x1:int,y1:int,x2:int,y2:int,final=False):
    r=bytearray(template)
    r[34:38]=i32(x1); r[38:42]=i32(y1); r[42:46]=i32(x2); r[46:50]=i32(y2)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def build_block(kind:str, suffix='keep'):
    ins,outs=terminal_templates(); ws=wire_templates(); rs=resistor_records(); conns=topology()
    block=bytearray(); serial=0
    if kind=='resistors_only':
        for i,r in enumerate(rs,1):
            rr=bytearray(r); rr[-1]=0xff if i==21 else 0x00; block+=rr
        header_len=2
    elif kind in ('two_terms_b6_then_resistors','two_terms_n0a1_then_resistors'):
        if kind=='two_terms_b6_then_resistors': idx,left,right,col,row=14,'B6','M0',6,1
        else: idx,left,right,col,row=1,'N0','A1',0,0
        c=coords_for(col,row)
        block += patch_terminal_fixed(ins[(idx-1)%4],left,c['lt_symbol_x'],c['y'],c['lt_label_x'],c['y'],'in',serial,suffix); serial+=1
        block += patch_terminal_fixed(outs[(idx-1)%4],right,c['rt_symbol_x'],c['y'],c['rt_label_x'],c['y'],'out',serial,suffix); serial+=1
        for i,r in enumerate(rs,1):
            rr=bytearray(r); rr[-1]=0xff if i==21 else 0x00; block+=rr
        header_len=1
    elif kind in ('all_terms_then_resistors','all_terms_resistors_wires'):
        term_records=[]; wire_records=[]
        for idx,left,right,col,row in conns:
            c=coords_for(col,row); k=(idx-1)%4
            term_records.append(patch_terminal_fixed(ins[k],left,c['lt_symbol_x'],c['y'],c['lt_label_x'],c['y'],'in',serial,suffix)); serial+=1
        for idx,left,right,col,row in conns:
            c=coords_for(col,row); k=(idx-1)%4
            term_records.append(patch_terminal_fixed(outs[k],right,c['rt_symbol_x'],c['y'],c['rt_label_x'],c['y'],'out',serial,suffix)); serial+=1
        res_records=[]
        for i,r in enumerate(rs,1):
            rr=bytearray(r); rr[-1]=0xff if (i==21 and kind=='all_terms_then_resistors') else 0x00; res_records.append(bytes(rr))
        if kind=='all_terms_resistors_wires':
            for idx,left,right,col,row in conns:
                c=coords_for(col,row); wi=(idx-1)*2
                wire_records.append(patch_wire_fixed(ws[wi],c['x']-254000,c['y'],c['x'],c['y']))
                wire_records.append(patch_wire_fixed(ws[wi+1],c['x']+1524000,c['y'],c['x']+1270000,c['y'],final=(idx==21)))
        block += b''.join(term_records)+b''.join(res_records)+b''.join(wire_records)
        header_len=1
    else: raise ValueError(kind)
    return bytes(block),header_len

def rebuild_dsn(block:bytes, header_len:int):
    base=bytearray(BASE_RES_DSN.read_bytes())
    fi=base.find(b'ISIS CIRCUIT FILE'); obj=base.find(b'OBJECT DATA',fi); sec=base.find(b'ISIS CIRCUIT FILE',fi+1)
    prefix=bytearray(base[:obj+len(b'OBJECT DATA')+header_len])
    tail=bytearray(base[sec:])
    first_isis=fi
    new_sec=len(prefix)+len(block)
    rel_obj=tail.find(b'OBJECT DATA')
    second_obj=new_sec+rel_obj
    ptr=second_obj+13
    # pointer before first ISIS is at first_isis - 4 in this construction.
    prefix[first_isis-4:first_isis]=u32(ptr)
    # patch CCT000 and __DEFAULT__ pointers in tail
    cct=tail.find(b'CCT000')
    if cct!=-1: tail[cct+len(b'CCT000')+2:cct+len(b'CCT000')+6]=u32(first_isis)
    default=tail.find(b'__DEFAULT__\x00\x00')
    if default!=-1: tail[default+len(b'__DEFAULT__\x00\x00'):default+len(b'__DEFAULT__\x00\x00')+4]=u32(new_sec)
    out=prefix+bytearray(block)+tail
    return bytes(out), {'first_isis':first_isis,'second_isis':new_sec,'second_obj':second_obj,'ptr':ptr,'header_len':header_len,'counts':{'TERINPUT':out.count(b'$TERINPUT'),'TEROUTPUT':out.count(b'$TEROUTPUT'),'COMPONENT_ID':out.count(b'COMPONENT ID'),'WIRE':out.count(b'WIRE')}}

def main():
    if OUTDIR.exists(): shutil.rmtree(OUTDIR)
    OUTDIR.mkdir()
    cdb=BASE_RES_CDB.read_bytes()
    shutil.copy2(CONTROL, OUTDIR/'CONTROL_E001_EMPTY_BASE.pdsprj')
    configs=[
        ('TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL','resistors_only','keep'),
        ('TEST_R21_V6_TWO_TERMS_N0_A1_FIXED_LABELPATCH_E0_TAIL','two_terms_n0a1_then_resistors','keep'),
        ('TEST_R21_V6_TWO_TERMS_B6_M0_FIXED_LABELPATCH_E0_TAIL','two_terms_b6_then_resistors','keep'),
        ('TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_NO_WIRES_E0_TAIL','all_terms_then_resistors','keep'),
        ('TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_NO_WIRES_E0_TAIL','all_terms_then_resistors','unique'),
        ('TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_WITH_WIRES_E0_TAIL','all_terms_resistors_wires','keep'),
        ('TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_WITH_WIRES_E0_TAIL','all_terms_resistors_wires','unique'),
    ]
    manifest=[]
    for name,kind,suffix in configs:
        block,hlen=build_block(kind,suffix)
        dsn,info=rebuild_dsn(block,hlen)
        write_project(OUTDIR/(name+'.pdsprj'),cdb,dsn)
        (OUTDIR/(name+'.ROOT.CDB.bin')).write_bytes(cdb)
        (OUTDIR/(name+'.ROOT.DSN.bin')).write_bytes(dsn)
        manifest.append({'file':name+'.pdsprj','kind':kind,'suffix':suffix,'info':info})
    (OUTDIR/'manifest.json').write_text(json.dumps({'tests':manifest},indent=2))
    (OUTDIR/'generation_code_used.py').write_text(Path(__file__).read_text())
    (OUTDIR/'README_TEST_FIRST.txt').write_text('''R21 V6 terminal-label-patch diagnostic pack\n\nConcrete V5 bug found:\nThe terminal label patcher searched for the NEW label bytes anywhere in the record after replacing the label.\nFor labels such as B6, those two bytes also appeared inside binary coordinate fields, so the code patched coordinates at the wrong offset and corrupted terminal records.\n\nV6 fix:\nPatch terminal label and label-coordinate fields at fixed offsets:\n- input terminal: len @ +30, label @ +31, label coords @ +33/+37\n- output terminal: len @ +31, label @ +32, label coords @ +34/+38\n\nTest order:\n1 CONTROL_E001_EMPTY_BASE.pdsprj\n2 TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.pdsprj\n3 TEST_R21_V6_TWO_TERMS_N0_A1_FIXED_LABELPATCH_E0_TAIL.pdsprj\n4 TEST_R21_V6_TWO_TERMS_B6_M0_FIXED_LABELPATCH_E0_TAIL.pdsprj\n5 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_NO_WIRES_E0_TAIL.pdsprj\n6 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_NO_WIRES_E0_TAIL.pdsprj\n7 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_WITH_WIRES_E0_TAIL.pdsprj\n8 TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_WITH_WIRES_E0_TAIL.pdsprj\n\nInterpretation:\n- If B6 test works: the coordinate-collision bug is fixed.\n- If all-terms no-wires works: terminal scaling is okay.\n- If no-wires works but wires fails: wire record/endpoint semantics are the remaining problem.\n''')
    zip_path=ROOT/'R21_TERMINAL_NETWORK_V6_FIXED_TERMINAL_LABEL_PATCH.zip'
    if zip_path.exists(): zip_path.unlink()
    shutil.make_archive(str(zip_path).removesuffix('.zip'),'zip',OUTDIR)
    print(zip_path)
main()

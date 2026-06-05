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
def u16(x:int): return struct.pack('<H',x)
def enc_str(s:str):
    b=s.encode('ascii'); return bytes([len(b)])+b
def enc_text(data:bytes): return u32(4+len(data))+data

def read_member(p:Path,name:str):
    with zipfile.ZipFile(p) as z: return z.read(name)
def write_project(path:Path,cdb:bytes,dsn:bytes):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SCRIPTS/PWRRAILS.DAT',read_member(E0_PROJECT,'SCRIPTS/PWRRAILS.DAT'))
        z.writestr('ROOT.CDB',cdb)
        z.writestr('ROOT.DSN',dsn)
        z.writestr('PROJECT.XML',read_member(E0_PROJECT,'PROJECT.XML'))

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
    return {
      'x':x,'y':y,
      'lt_symbol_x':x-508000,'lt_label_x':x-889000,
      'rt_symbol_x':x+1778000,'rt_label_x':x+2159000,
    }

def build_cdb(n=21):
    out=bytearray(); out+=u32(7)
    out+=u32(1)+u32(1)+u32(0)+enc_str('ROOT')+b'\x00'+u32(0)+u32(1)+u32(1)
    out+=u32(2)
    out+=u32(1)+u32(3)+u32(1)+enc_str('')+u32(10)+u32(0)
    out+=u32(2)+u32(2)+u32(0)+enc_str('Master Sheet')+u32(10)+u32(0)
    out+=u32(n)
    for idx in range(1,n+1):
        ref=REFS[idx-1]
        out+=u32(idx)+u32(1)+u32(0)+u32(idx)+enc_str(ref)
        out+=u32(2)+enc_str('1')+b'\x00'+enc_str('2')+b'\x00'
        out+=u32(0)+u32(idx)+u32(0)
    out+=u32(1)+u32(1)+b'\x00'+enc_str('')+u32(1)
    out+=u32(n)
    for idx in range(1,n+1):
        out+=u32(idx)+u32(1)+u32(0)+u32(0)+u32(0)
        out+=enc_str(REFS[idx-1])+enc_str(VALUES[idx-1])+enc_str('RESISTOR')+enc_str('')+enc_text(PROP_TEXT)
    out+=u32(0)
    return bytes(out)

def extract_visual_chunk(project:Path):
    d=read_member(project,'ROOT.DSN')
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    return d[obj+len(b'OBJECT DATA'):sec]

def terminal_templates_correct():
    # Actual par4 object chunk has a 1-byte OBJECT DATA header at offset 0.
    # Terminal records begin at offset 1, NOT 0. This was the V2/V3/V4 bug.
    par=extract_visual_chunk(PAR4_PROJECT)
    ins=[bytearray(par[1+i*103:1+(i+1)*103]) for i in range(4)]
    outs=[bytearray(par[413+i*104:413+(i+1)*104]) for i in range(4)]
    # After terminals: 1 + 4*103 + 4*104 = 829. Then groups: resistor 346, wire 50, wire 50.
    groups=[]
    base=829
    for i in range(4):
        gbase=base+i*(346+50+50)
        groups.append((bytearray(par[gbase:gbase+346]), bytearray(par[gbase+346:gbase+396]), bytearray(par[gbase+396:gbase+446])))
    return ins,outs,groups

def resistor_template():
    d=read_member(R12_WORKING,'ROOT.DSN')
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    # R12 generated from resistor-only valid shell has two bytes after OBJECT DATA then resistor record starts.
    start=obj+len(b'OBJECT DATA')+2
    rec=bytearray(d[start:start+346])
    assert len(rec)==346 and rec[0]==0xff and rec.find(b'COMPONENT ID')>0
    return rec

def patch_label_2(r:bytearray, old:bytes, new:str):
    nb=new.encode('ascii'); assert len(nb)==2
    p=r.find(old)
    if p<0: raise RuntimeError((old,new,r[:80]))
    r[p:p+2]=nb

def patch_terminal(template:bytearray, old:bytes, new:str, sx:int, sy:int, lx:int, ly:int, suffix_mode='keep', serial=0, kind='in'):
    r=bytearray(template)
    patch_label_2(r,old,new)
    # terminal symbol coords at +1/+5? record starts with 0x10 then x,y.
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    p=r.find(new.encode('ascii'))
    r[p+2:p+6]=i32(lx); r[p+6:p+10]=i32(ly)
    if suffix_mode=='unique':
        base=0x0159 if kind=='in' else 0x018b
        r[-3:-1]=u16((base+serial*0x01be)&0xffff)
        r[-1]=0x01
    # suffix_mode keep preserves donor suffix, including final 01.
    return bytes(r)

def patch_wire(template:bytearray,x1:int,y1:int,x2:int,y2:int,final=False):
    r=bytearray(template)
    # wire record starts with 0x00? coords currently known at +34..+49 if extracted correctly.
    r[34:38]=i32(x1); r[38:42]=i32(y1); r[42:46]=i32(x2); r[46:50]=i32(y2)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def patch_resistor(template:bytearray,idx:int,ref:str,val:str,x:int,y:int,final=False):
    r=bytearray(template)
    r[0]=0xff; r[1]=2; r[2:4]=ref.encode('ascii')
    r[69]=2; r[70:72]=val.encode('ascii')
    fields=[(4,8),(72,76),(146,150),(231,235),(312,316)]
    pairs=[(x,y+121920),(x,y-121920),(x,y-375920),(x,y-375920),(x,y)]
    for (xo,yo),(xx,yy) in zip(fields,pairs):
        r[xo:xo+4]=i32(xx); r[yo:yo+4]=i32(yy)
    r[324:328]=u32(idx)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def build_block(kind:str, suffix_mode='keep'):
    ins,outs,groups=terminal_templates_correct(); res_t=resistor_template()
    block=bytearray(); man=[]; serial=0
    conns=topology()
    if kind=='resistors_only':
        for idx,left,right,col,row in conns:
            c=coords_for(col,row); final=(idx==21)
            block+=patch_resistor(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'],final)
            man.append({'idx':idx,'ref':REFS[idx-1],'left':left,'right':right,**c})
    elif kind in ('two_terms_then_resistors','two_terms_donorbytes_then_resistors'):
        idx,left,right,col,row=conns[0]
        c=coords_for(col,row)
        if kind=='two_terms_donorbytes_then_resistors':
            # exact donor terminal bytes, no label or coordinate mutation
            block += bytes(ins[0]) + bytes(outs[0])
        else:
            block+=patch_terminal(ins[0],b'N1',left,c['lt_symbol_x'],c['y'],c['lt_label_x'],c['y'],suffix_mode,serial,'in'); serial+=1
            block+=patch_terminal(outs[0],b'N2',right,c['rt_symbol_x'],c['y'],c['rt_label_x'],c['y'],suffix_mode,serial,'out'); serial+=1
        for idx,left,right,col,row in conns:
            c=coords_for(col,row); final=(idx==21)
            block+=patch_resistor(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'],final)
    elif kind in ('all_terms_then_resistors','all_terms_resistors_wires'):
        term_records=[]; res_records=[]; wire_records=[]
        for idx,left,right,col,row in conns:
            c=coords_for(col,row)
            ii=(idx-1)%4
            term_records.append(patch_terminal(ins[ii],b'N1',left,c['lt_symbol_x'],c['y'],c['lt_label_x'],c['y'],suffix_mode,serial,'in')); serial+=1
        for idx,left,right,col,row in conns:
            c=coords_for(col,row)
            ii=(idx-1)%4
            term_records.append(patch_terminal(outs[ii],b'N2',right,c['rt_symbol_x'],c['y'],c['rt_label_x'],c['y'],suffix_mode,serial,'out')); serial+=1
        for idx,left,right,col,row in conns:
            c=coords_for(col,row); final=(idx==21 and kind=='all_terms_then_resistors')
            res_records.append(patch_resistor(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'],final))
            if kind=='all_terms_resistors_wires':
                _,wl,wr=groups[(idx-1)%4]
                wire_records.append(patch_wire(wl,c['x']-254000,c['y'],c['x'],c['y']))
                wire_records.append(patch_wire(wr,c['x']+1524000,c['y'],c['x']+1270000,c['y'],final=(idx==21)))
        block += b''.join(term_records) + b''.join(res_records) + b''.join(wire_records)
    else:
        raise ValueError(kind)
    return bytes(block),man

def build_dsn(object_block:bytes, tail_mode='E0_TAIL', header_len=2):
    e0=read_member(E0_PROJECT,'ROOT.DSN'); r4=read_member(R4_PROJECT,'ROOT.DSN')
    e0_first=e0.find(b'ISIS CIRCUIT FILE'); e0_second=e0.find(b'ISIS CIRCUIT FILE',e0_first+1)
    r4_first=r4.find(b'ISIS CIRCUIT FILE'); r4_obj=r4.find(b'OBJECT DATA',r4_first)
    insert_marker=b'{PACKAGE=NULL}\n\x00'; insert_pos=e0.rfind(insert_marker,0,e0_first)+len(insert_marker)
    dev=bytearray(r4[insert_pos:r4_first])
    first_header=r4[r4_first:r4_obj+len(b'OBJECT DATA')+header_len]
    if tail_mode=='E0_TAIL': tail=bytearray(e0[e0_second:])
    else:
        r4_second=r4.find(b'ISIS CIRCUIT FILE',r4_first+1); tail=bytearray(r4[r4_second:])
    first_isis_new=insert_pos+len(dev)
    second_isis_new=first_isis_new+len(first_header)+len(object_block)
    rel_obj=tail.find(b'OBJECT DATA'); second_obj=second_isis_new+rel_obj
    ptr=second_obj+13
    dev[-4:]=u32(ptr)
    cct=tail.find(b'CCT000')
    if cct!=-1: tail[cct+len(b'CCT000')+2:cct+len(b'CCT000')+6]=u32(first_isis_new)
    default=tail.find(b'__DEFAULT__\x00\x00')
    if default!=-1: tail[default+len(b'__DEFAULT__\x00\x00'):default+len(b'__DEFAULT__\x00\x00')+4]=u32(second_isis_new)
    out=bytearray(e0[:insert_pos])+dev+first_header+bytearray(object_block)+tail
    # sanity
    assert out.find(b'ISIS CIRCUIT FILE')==first_isis_new
    assert out.find(b'ISIS CIRCUIT FILE',first_isis_new+1)==second_isis_new
    return bytes(out), {'first_isis':first_isis_new,'second_isis':second_isis_new,'second_obj':second_obj,'ptr':ptr,'header_len':header_len,'byte_before_second':out[second_isis_new-1]}

def main():
    if OUTDIR.exists(): shutil.rmtree(OUTDIR)
    OUTDIR.mkdir()
    shutil.copy2(E0_PROJECT, OUTDIR/'CONTROL_E001_EMPTY_BASE.pdsprj')
    cdb=build_cdb(21)
    tests=[]
    configs=[
        ('TEST_R21_V5_RESISTORS_ONLY_CORRECT_BOUNDARY_E0_TAIL','resistors_only','keep','E0_TAIL',2),
        ('TEST_R21_V5_TWO_TERMS_DONORBYTES_THEN_RESISTORS_E0_TAIL','two_terms_donorbytes_then_resistors','keep','E0_TAIL',1),
        ('TEST_R21_V5_TWO_TERMS_PATCHED_THEN_RESISTORS_E0_TAIL','two_terms_then_resistors','keep','E0_TAIL',1),
        ('TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_E0_TAIL','all_terms_then_resistors','keep','E0_TAIL',1),
        ('TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_WIRES_E0_TAIL','all_terms_resistors_wires','keep','E0_TAIL',1),
        ('TEST_R21_V5_TWO_TERMS_DONORBYTES_THEN_RESISTORS_R4_TAIL','two_terms_donorbytes_then_resistors','keep','R4_TAIL',1),
        ('TEST_R21_V5_TWO_TERMS_PATCHED_THEN_RESISTORS_R4_TAIL','two_terms_then_resistors','keep','R4_TAIL',1),
        ('TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_R4_TAIL','all_terms_then_resistors','keep','R4_TAIL',1),
        ('TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_WIRES_R4_TAIL','all_terms_resistors_wires','keep','R4_TAIL',1),
        ('TEST_R21_V5_TWO_TERMS_PATCHED_THEN_RESISTORS_SUFFIX_UNIQUE_E0_TAIL','two_terms_then_resistors','unique','E0_TAIL',1),
    ]
    for name,kind,suffix,tail,hlen in configs:
        block,man=build_block(kind,suffix)
        dsn,info=build_dsn(block,tail,hlen)
        path=OUTDIR/(name+'.pdsprj')
        write_project(path,cdb,dsn)
        (OUTDIR/(name+'.ROOT.CDB.bin')).write_bytes(cdb)
        (OUTDIR/(name+'.ROOT.DSN.bin')).write_bytes(dsn)
        tests.append({'file':path.name,'kind':kind,'suffix':suffix,'tail':tail,'header_len':hlen,'dsn_info':info,'counts':{'terinput':dsn.count(b'$TERINPUT'),'teroutput':dsn.count(b'$TEROUTPUT'),'component_id':dsn.count(b'COMPONENT ID'),'wire':dsn.count(b'WIRE')}})
    topo=[{'idx':i,'ref':REFS[i-1],'value':VALUES[i-1],'visible':VISIBLE_VALUES[i-1]} for i in range(1,22)]
    (OUTDIR/'manifest.json').write_text(json.dumps({'tests':tests},indent=2))
    (OUTDIR/'topology_map.json').write_text(json.dumps(topo,indent=2))
    (OUTDIR/'generation_code_used.py').write_text(Path(__file__).read_text())
    (OUTDIR/'README_TEST_FIRST.txt').write_text('''R21 V5 terminal-network diagnostic pack\n\nMain fix: correct terminal object boundaries.\nThe par4 donor object chunk has a 1-byte OBJECT DATA header at offset 0.\nTerminal records begin at offset 1. Older packs incorrectly included the header byte inside the first terminal record and then also used a 2-byte resistor-style OBJECT DATA header.\n\nTest order:\n1 CONTROL_E001_EMPTY_BASE.pdsprj\n2 TEST_R21_V5_RESISTORS_ONLY_CORRECT_BOUNDARY_E0_TAIL.pdsprj\n3 TEST_R21_V5_TWO_TERMS_DONORBYTES_THEN_RESISTORS_E0_TAIL.pdsprj\n4 TEST_R21_V5_TWO_TERMS_PATCHED_THEN_RESISTORS_E0_TAIL.pdsprj\n5 TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_E0_TAIL.pdsprj\n6 TEST_R21_V5_ALL_TERMS_THEN_RESISTORS_WIRES_E0_TAIL.pdsprj\n\nIf E0-tail terminal tests fail, try matching R4-tail files.\nIf donorbytes works but patched fails: patching label/coords is still wrong.\nIf patched two terminals works but all terms fails: terminal scaling/token uniqueness is the problem.\nIf no-wire works but wire fails: wire record/endpoint semantics are the problem.\n''')
    zip_path=ROOT/'R21_TERMINAL_NETWORK_V5_CORRECT_OBJECT_BOUNDARIES.zip'
    if zip_path.exists(): zip_path.unlink()
    shutil.make_archive(str(zip_path).removesuffix('.zip'),'zip',OUTDIR)
    print(zip_path)
main()

from __future__ import annotations
import zipfile,struct,json,shutil
from pathlib import Path
ROOT=Path('/mnt/data')
E0=ROOT/'e001_empty_project.pdsprj'
B02=ROOT/'work_term/CONTROL_B02_E008_four_parallel_N1_N2.pdsprj'
OUT=ROOT/'R21_E001_B02_ORDER_TERMINATOR_FIXED_GENERATION'
ZIP=ROOT/'R21_E001_B02_ORDER_TERMINATOR_FIXED_GENERATION.zip'
PROP_TEXT=b'{PRIMITIVE=ANALOGUE}\n\x00'
REFS=['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
VALUES=[f'{i}k' for i in range(1,22)]
VIS_VALUES=['1k','2k','3k','4k','5k','6k','7k','8k','9k','Ak','Bk','Ck','Dk','Ek','Fk','Gk','Hk','Ik','Jk','Kk','Lk']
DX=2540000
DY=-1524000

def u32(x:int): return struct.pack('<I',x)
def i32(x:int): return struct.pack('<i',x)
def u16(x:int): return struct.pack('<H',x)
def enc_str(s:str):
    b=s.encode('ascii'); return bytes([len(b)])+b
def enc_text(data:bytes): return u32(4+len(data))+data
def member(p:Path,name:str):
    with zipfile.ZipFile(p) as z: return z.read(name)
def write_project(path:Path,cdb:bytes,dsn:bytes):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SCRIPTS/PWRRAILS.DAT',member(E0,'SCRIPTS/PWRRAILS.DAT'))
        z.writestr('ROOT.CDB',cdb)
        z.writestr('ROOT.DSN',dsn)
        z.writestr('PROJECT.XML',member(E0,'PROJECT.XML'))

def build_cdb(n:int):
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

def extract_b02_templates():
    d=member(B02,'ROOT.DSN')
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    c=d[obj+len(b'OBJECT DATA'):sec]
    header=c[:1]
    inputs=[bytearray(c[1+i*103:1+(i+1)*103]) for i in range(4)]
    outputs=[bytearray(c[413+i*104:413+(i+1)*104]) for i in range(4)]
    sep=c[829:830]
    groups=[]
    base=830
    for i in range(4):
        gbase=base+i*446
        res=bytearray(c[gbase:gbase+346])
        w1=bytearray(c[gbase+346:gbase+396])
        w2=bytearray(c[gbase+396:gbase+446])
        groups.append((res,w1,w2))
    assert header==b'\x00' and sep==b'\x00'
    assert all(b'$TERINPUT' in t for t in inputs)
    assert all(b'$TEROUTPUT' in t for t in outputs)
    assert all(b'COMPONENT ID' in g[0] and b'WIRE' in g[1] and b'WIRE' in g[2] for g in groups)
    return header,inputs,outputs,sep,groups
HEADER,IN_TS,OUT_TS,SEP,GROUPS=extract_b02_templates()

def patch_input(t:bytearray,label:str,sx:int,sy:int,lx:int,ly:int,serial:int):
    r=bytearray(t); lab=label.encode('ascii'); assert len(lab)==2
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    r[30]=2; r[31:33]=lab; r[33:37]=i32(lx); r[37:41]=i32(ly)
    seq=(0x0159+serial*0x01be)&0xffff
    r[-4:-2]=u16(seq); r[-2]=0x01; r[-1]=0x00
    return bytes(r)

def patch_output(t:bytearray,label:str,sx:int,sy:int,lx:int,ly:int,serial:int):
    r=bytearray(t); lab=label.encode('ascii'); assert len(lab)==2
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    r[31]=2; r[32:34]=lab; r[34:38]=i32(lx); r[38:42]=i32(ly)
    seq=(0x018b+serial*0x01be)&0xffff
    r[-4:-2]=u16(seq); r[-2]=0x01; r[-1]=0x00
    return bytes(r)

def patch_res(t:bytearray,idx:int,ref:str,val:str,x:int,y:int):
    r=bytearray(t); assert len(ref)==2 and len(val)==2
    r[1]=2; r[2:4]=ref.encode('ascii')
    r[4:8]=i32(x+254000); r[8:12]=i32(y+121920)
    r[69]=2; r[70:72]=val.encode('ascii')
    r[72:76]=i32(x+254000); r[76:80]=i32(y-121920)
    r[149:153]=i32(x+254000); r[153:157]=i32(y-375920)
    r[235:239]=i32(x+254000); r[239:243]=i32(y-375920)
    r[312:316]=i32(x); r[316:320]=i32(y)
    r[324:328]=u32(idx)
    return bytes(r)

def patch_wire(t:bytearray,x1:int,y1:int,x2:int,y2:int):
    r=bytearray(t)
    r[33:37]=i32(x1); r[37:41]=i32(y1); r[41:45]=i32(x2); r[45:49]=i32(y2)
    return bytes(r)

def topology(n:int):
    if n==1: return [(1,'N0','A1',0,0)]
    if n==2: return [(1,'N0','A1',0,0),(2,'A1','Z0',1,0)]
    conns=[]
    nodes=['N0']+[f'A{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((i+1,nodes[i],nodes[i+1],i,0))
    nodes=['N0']+[f'B{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((8+i,nodes[i],nodes[i+1],i,1))
    nodes=['M0']+[f'C{i}' for i in range(1,7)]+['Z0']
    for i in range(7): conns.append((15+i,nodes[i],nodes[i+1],i,2))
    return conns[:n]

def coords(col,row):
    x0=-6350000; y0=5080000
    x=x0+col*DX; y=y0+row*DY
    return x,y

def build_object_chunk(n:int):
    conns=topology(n)
    inputs=[]; outputs=[]; groups=[]; maps=[]
    for idx,left,right,col,row in conns:
        x,y=coords(col,row)
        # Match B02 geometry relative to resistor body.
        in_sym_x=x-508000; out_sym_x=x+1778000
        in_label_x=x-889000; out_label_x=x+2159000
        # wire endpoint/tip relation from B02
        in_tip_x=x-254000; out_tip_x=x+1524000
        left_pin_x=x; right_pin_x=x+1270000
        inputs.append(patch_input(IN_TS[(idx-1)%4],left,in_sym_x,y,in_label_x,y,idx*2-2))
        outputs.append(patch_output(OUT_TS[(idx-1)%4],right,out_sym_x,y,out_label_x,y,idx*2-1))
        res,w1,w2=GROUPS[(idx-1)%4]
        groups.append(patch_res(res,idx,REFS[idx-1],VIS_VALUES[idx-1],x,y))
        groups.append(patch_wire(w1,in_tip_x,y,left_pin_x,y))
        groups.append(patch_wire(w2,out_tip_x,y,right_pin_x,y))
        maps.append({'idx':idx,'ref':REFS[idx-1],'value':VALUES[idx-1],'visible':VIS_VALUES[idx-1],'left':left,'right':right,'x':x,'y':y})
    chunk=bytearray(HEADER+b''.join(inputs)+b''.join(outputs)+SEP+b''.join(groups))
    # Critical: valid B02 donor object stream ends with final object byte 0xFF.
    # Previous B02 pack ended with 0x00, causing VGDVC/crash on terminal+wire files.
    if chunk:
        chunk[-1]=0xFF
    return bytes(chunk),maps

def build_dsn(object_chunk:bytes):
    e0=member(E0,'ROOT.DSN'); b02=member(B02,'ROOT.DSN')
    e0_first=e0.find(b'ISIS CIRCUIT FILE'); e0_second=e0.find(b'ISIS CIRCUIT FILE',e0_first+1)
    b02_first=b02.find(b'ISIS CIRCUIT FILE'); b02_obj=b02.find(b'OBJECT DATA',b02_first)
    marker=b'{PACKAGE=NULL}\n\x00'
    insert=e0.rfind(marker,0,e0_first)+len(marker)
    dev=bytearray(b02[insert:b02_first])
    first_header=b02[b02_first:b02_obj+len(b'OBJECT DATA')]
    tail=bytearray(e0[e0_second:])
    first_isis=insert+len(dev)
    second_isis=first_isis+len(first_header)+len(object_chunk)
    second_obj=second_isis+tail.find(b'OBJECT DATA')
    ptr=second_obj+13
    if len(dev)>=4: dev[-4:]=u32(ptr)
    cct=tail.find(b'CCT000')
    if cct!=-1: tail[cct+len(b'CCT000')+2:cct+len(b'CCT000')+6]=u32(first_isis)
    default=tail.find(b'__DEFAULT__\x00\x00')
    if default!=-1: tail[default+len(b'__DEFAULT__\x00\x00'):default+len(b'__DEFAULT__\x00\x00')+4]=u32(second_isis)
    return bytes(bytearray(e0[:insert])+dev+first_header+bytearray(object_chunk)+tail)

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copy(E0,OUT/'CONTROL_E001_EMPTY_BASE.pdsprj')
    manifest={}
    for n,name in [(1,'TEST_B02_ORDER_R1_TERMINAL_RESISTOR_TERMINAL'),(2,'TEST_B02_ORDER_R2_SERIES_TERMINALS'),(21,'FINAL_B02_ORDER_R21_7PAR7_PLUS_7SERIES_TERMINALS')]:
        obj,maps=build_object_chunk(n)
        cdb=build_cdb(n)
        dsn=build_dsn(obj)
        p=OUT/f'{name}.pdsprj'
        write_project(p,cdb,dsn)
        (OUT/f'{name}.ROOT.CDB.bin').write_bytes(cdb)
        (OUT/f'{name}.ROOT.DSN.bin').write_bytes(dsn)
        manifest[name]={'n':n,'object_chunk_len':len(obj),'dsn_len':len(dsn),'cdb_len':len(cdb),'map':maps}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'README_TEST_FIRST.txt').write_text('''B02-order fixed generation pack.\n\nE001 is the project base. B02 is used as schema/reference for terminal-resistor-wire ordering and 2-character terminal label records.\n\nTest order:\n1 CONTROL_E001_EMPTY_BASE.pdsprj\n2 TEST_B02_ORDER_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj\n3 TEST_B02_ORDER_R2_SERIES_TERMINALS.pdsprj\n4 FINAL_B02_ORDER_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj\n''')
    shutil.copy(__file__,OUT/'generation_code_used.py')
    if ZIP.exists(): ZIP.unlink()
    with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.iterdir()): z.write(f,f.name)
    print(ZIP,ZIP.stat().st_size)
if __name__=='__main__': main()

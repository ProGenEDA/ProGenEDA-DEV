from __future__ import annotations
import zipfile, struct, json, shutil
from pathlib import Path

ROOT=Path('/mnt/data')
E0=ROOT/'e001_empty_project.pdsprj'
E019=ROOT/'e019_resistor_in_out_10k.pdsprj'
OUT=ROOT/'R21_E001_E019_GROUP_ORDER_GENERATION'
ZIP=ROOT/'R21_E001_E019_GROUP_ORDER_GENERATION.zip'
PROP_TEXT=b'{PRIMITIVE=ANALOGUE}\n\x00'
REFS=['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
VALUES=[f'{i}k' for i in range(1,22)]
VIS_VALUES=[f'{i:02d}k' for i in range(1,22)]
# Coordinates in Proteus integer units. Built around e019 relative geometry.
DX=3200000
DY=-1900000

def u32(x:int): return struct.pack('<I',x)
def i32(x:int): return struct.pack('<i',x)
def enc_str(s:str):
    b=s.encode('ascii')
    assert len(b)<256
    return bytes([len(b)])+b
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

def extract_e019_templates():
    d=member(E019,'ROOT.DSN')
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    chunk=d[obj+len(b'OBJECT DATA'):sec]
    assert len(chunk)==657
    header=chunk[:1]
    in_t=bytearray(chunk[1:104])
    out_t=bytearray(chunk[104:208])
    res_t=bytearray(chunk[208:554])
    w1_t=bytearray(chunk[554:604])
    w2_t=bytearray(chunk[604:654])
    trail=chunk[654:657]
    assert b'$TERINPUT' in in_t and b'$TEROUTPUT' in out_t and b'COMPONENT ID' in res_t and b'WIRE' in w1_t and b'WIRE' in w2_t
    return header,in_t,out_t,res_t,w1_t,w2_t,trail

HEADER,IN_T,OUT_T,RES_T,W1_T,W2_T,TRAIL=extract_e019_templates()

def terminal_patch(r:bytearray,label:str,sx:int,sy:int,lx:int,ly:int,kind:str,serial:int):
    r=bytearray(r); lab=label.encode('ascii'); assert len(lab)==2
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    if kind=='in':
        r[30]=2; r[31:33]=lab; r[33:37]=i32(lx); r[37:41]=i32(ly)
    else:
        r[31]=2; r[32:34]=lab; r[34:38]=i32(lx); r[38:42]=i32(ly)
    # keep the same local donor record shape, but make the final text/identity-ish suffix vary safely
    # from the observed e019/terminal donor pattern. Leave last byte 0x00 as in e019 single terminal records.
    # Some terminal packs opened only when these bytes were not destroyed.
    if len(r)>=4:
        seq=(0x0159 + serial*0x01be) & 0xffff
        r[-4:-2]=struct.pack('<H',seq)
        # r[-2] remains donor value, r[-1] remains donor value
    return bytes(r)

def resistor_patch(r:bytearray,idx:int,ref:str,val3:str,body_x:int,body_y:int):
    r=bytearray(r)
    assert len(ref)==2 and len(val3)==3
    # ref field: e019 resistor has len at +3, bytes +4..+5, ref x/y +6/+10
    r[3]=2; r[4:6]=ref.encode('ascii')
    # value field: e019 resistor has marker FF, len +71, bytes +72..+74, value x/y +75/+79
    r[71]=3; r[72:75]=val3.encode('ascii')
    # visible coords following the e019 layout
    r[6:10]=i32(body_x+254000); r[10:14]=i32(body_y+121920)      # component ID label
    r[75:79]=i32(body_x+254000); r[79:83]=i32(body_y-121920)    # component value label
    r[152:156]=i32(body_x+254000); r[156:160]=i32(body_y-375920) # hidden subckt text
    r[238:242]=i32(body_x+254000); r[242:246]=i32(body_y-375920) # hidden properties text
    r[315:319]=i32(body_x); r[319:323]=i32(body_y)               # body
    # e019 3-char record uses CDB/element key at +327
    r[327:331]=u32(idx)
    return bytes(r)

def wire_patch(r:bytearray,x1:int,y1:int,x2:int,y2:int):
    r=bytearray(r)
    # e019 wire coords found at +36/+40 and +44/+48
    r[36:40]=i32(x1); r[40:44]=i32(y1); r[44:48]=i32(x2); r[48:52]=i32(y2) if len(r)>=52 else r[48:50]
    # w1/w2 are 50-byte slices; the second endpoint y in the donor is partly implicit/continued by fixed bytes.
    # For horizontal wires at same y, patch available x/y fields and preserve donor tail.
    return bytes(r)

def topology(n:int):
    if n==1:
        return [(1,'IN','OU',0,0)]
    if n==2:
        return [(1,'IN','N1',0,0),(2,'N1','OU',1,0)]
    conns=[]
    nodes=['N0']+[f'A{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((i+1,nodes[i],nodes[i+1],i,0))
    nodes=['N0']+[f'B{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((8+i,nodes[i],nodes[i+1],i,1))
    nodes=['M0']+[f'C{i}' for i in range(1,7)]+['Z0']
    for i in range(7): conns.append((15+i,nodes[i],nodes[i+1],i,2))
    return conns[:n]

def make_group(idx,label_left,label_right,col,row):
    # Match e019 visual relation exactly, just translated per component.
    body_x=-5080000 + col*DX
    body_y=762000 + row*DY
    left_pin=body_x
    right_pin=body_x+1270000
    in_symbol_x=body_x-1524000
    in_label_x=body_x-1905000
    out_symbol_x=body_x+2286000
    out_label_x=body_x+2667000
    in_tip_x=in_symbol_x+254000
    out_tip_x=out_symbol_x-254000
    recs=[]
    recs.append(terminal_patch(IN_T,label_left,in_symbol_x,body_y,in_label_x,body_y,'in',idx*2-2))
    recs.append(terminal_patch(OUT_T,label_right,out_symbol_x,body_y,out_label_x,body_y,'out',idx*2-1))
    recs.append(resistor_patch(RES_T,idx,REFS[idx-1],VIS_VALUES[idx-1],body_x,body_y))
    recs.append(wire_patch(W1_T,in_tip_x,body_y,left_pin,body_y))
    recs.append(wire_patch(W2_T,out_tip_x,body_y,right_pin,body_y))
    return b''.join(recs), {'idx':idx,'ref':REFS[idx-1],'value':VALUES[idx-1],'visible':VIS_VALUES[idx-1],'left':label_left,'right':label_right,'body_x':body_x,'body_y':body_y}

def build_object_chunk(n:int):
    out=bytearray(HEADER)
    maps=[]
    for idx,left,right,col,row in topology(n):
        g,m=make_group(idx,left,right,col,row)
        out+=g; maps.append(m)
    out+=TRAIL
    return bytes(out),maps

def build_dsn(object_chunk:bytes):
    e0=member(E0,'ROOT.DSN'); e19=member(E019,'ROOT.DSN')
    e0_first=e0.find(b'ISIS CIRCUIT FILE'); e0_second=e0.find(b'ISIS CIRCUIT FILE',e0_first+1)
    e19_first=e19.find(b'ISIS CIRCUIT FILE'); e19_obj=e19.find(b'OBJECT DATA',e19_first)
    marker=b'{PACKAGE=NULL}\n\x00'
    insert=e0.rfind(marker,0,e0_first)+len(marker)
    # donor device-definition block before first ISIS from e019
    dev=bytearray(e19[insert:e19_first])
    first_header=e19[e19_first:e19_obj+len(b'OBJECT DATA')]
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
    shutil.copy(E0, OUT/'CONTROL_E001_EMPTY_BASE.pdsprj')
    manifest={}
    for n,name in [(1,'TEST_E019_ORDER_R1_TERMINAL_RESISTOR_TERMINAL'),(2,'TEST_E019_ORDER_R2_SERIES_TERMINALS'),(21,'FINAL_E019_ORDER_R21_7PAR7_PLUS_7SERIES_TERMINALS')]:
        obj,mapdata=build_object_chunk(n)
        cdb=build_cdb(n)
        dsn=build_dsn(obj)
        p=OUT/f'{name}.pdsprj'
        write_project(p,cdb,dsn)
        (OUT/f'{name}.ROOT.CDB.bin').write_bytes(cdb)
        (OUT/f'{name}.ROOT.DSN.bin').write_bytes(dsn)
        manifest[name]={'n':n,'dsn_len':len(dsn),'cdb_len':len(cdb),'object_chunk_len':len(obj),'map':mapdata}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'README_TEST_FIRST.txt').write_text('''E019 group-order generation pack.\n\nThese are E001-based projects. E019 is used only as the one-resistor terminal--resistor--terminal record schema donor.\n\nTest order:\n1. CONTROL_E001_EMPTY_BASE.pdsprj\n2. TEST_E019_ORDER_R1_TERMINAL_RESISTOR_TERMINAL.pdsprj\n3. TEST_E019_ORDER_R2_SERIES_TERMINALS.pdsprj\n4. FINAL_E019_ORDER_R21_7PAR7_PLUS_7SERIES_TERMINALS.pdsprj\n\nThe final topology is two 7-resistor series branches in parallel, followed by seven more resistors in series.\n''')
    shutil.copy(__file__, OUT/'generation_code_used.py')
    if ZIP.exists(): ZIP.unlink()
    with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.iterdir()): z.write(f, f.name)
    print(ZIP, ZIP.stat().st_size)

if __name__=='__main__': main()

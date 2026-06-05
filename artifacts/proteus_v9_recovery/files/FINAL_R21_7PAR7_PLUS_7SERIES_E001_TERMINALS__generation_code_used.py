from __future__ import annotations
import json, shutil, struct, zipfile
from pathlib import Path

ROOT=Path('/mnt/data')
OUTDIR=ROOT/'FINAL_R21_7PAR7_PLUS_7SERIES_E001_TERMINALS'
E0_PROJECT=ROOT/'work_v6/CONTROL_E001_EMPTY_BASE.pdsprj'
BASE_RES_CDB=ROOT/'work_v6/TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.ROOT.CDB.bin'
BASE_RES_DSN=ROOT/'work_v6/TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.ROOT.DSN.bin'
TERMS_DSN=ROOT/'work_v6/TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_KEEP_NO_WIRES_E0_TAIL.ROOT.DSN.bin'

GRID=1270000
# More readable visual spacing than previous packs.
ROW_GAP=-1778000
REFS=['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
LOGICAL=[f'R{i}' for i in range(1,22)]
CDB_VALUES=[f'{i}k' for i in range(1,22)]
VISIBLE_SAFE=['1k','2k','3k','4k','5k','6k','7k','8k','9k','Ak','Bk','Ck','Dk','Ek','Fk','Gk','Hk','Ik','Jk','Kk','Lk']
VISIBLE_TRUE=CDB_VALUES[:]

def u32(x:int): return struct.pack('<I',x)
def i32(x:int): return struct.pack('<i',x)
def u16(x:int): return struct.pack('<H',x)

def read_member(p:Path,name:str):
    with zipfile.ZipFile(p) as z: return z.read(name)

def object_chunk(d:bytes):
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    if fi<0 or obj<0 or sec<0: raise RuntimeError('DSN markers missing')
    return d[obj+len(b'OBJECT DATA'):sec]

def write_project(path:Path,cdb:bytes,dsn:bytes):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SCRIPTS/PWRRAILS.DAT',read_member(E0_PROJECT,'SCRIPTS/PWRRAILS.DAT'))
        z.writestr('ROOT.CDB',cdb)
        z.writestr('ROOT.DSN',dsn)
        z.writestr('PROJECT.XML',read_member(E0_PROJECT,'PROJECT.XML'))

def topology():
    conns=[]
    # Branch A: first seven resistors, from N0 to M0.
    nodes=['N0']+[f'A{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((i+1,nodes[i],nodes[i+1],i,0))
    # Branch B: next seven resistors, parallel with branch A.
    nodes=['N0']+[f'B{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((8+i,nodes[i],nodes[i+1],i,1))
    # Tail: final seven resistors in series after the parallel block.
    nodes=['M0']+[f'C{i}' for i in range(1,7)]+['Z0']
    for i in range(7): conns.append((15+i,nodes[i],nodes[i+1],i,2))
    return conns

def coords_for(col:int,row:int):
    # Three horizontal rows. A and B share N0/M0 labels, tail starts from M0.
    x0=-6100000
    y0=6100000
    x=x0+col*GRID*2
    y=y0+row*ROW_GAP
    left_pin=x
    right_pin=x+1270000
    # Terminal symbol coordinate in donor layout is 254000 units away from its contact tip.
    in_symbol_x=left_pin-254000
    out_symbol_x=right_pin+254000
    return dict(
        x=x,y=y,left_pin=left_pin,right_pin=right_pin,
        in_symbol_x=in_symbol_x, out_symbol_x=out_symbol_x,
        in_label_x=in_symbol_x-381000, out_label_x=out_symbol_x+381000,
    )

def terminal_templates():
    ck=object_chunk(TERMS_DSN.read_bytes())
    assert ck[0]==0
    ins=[bytearray(ck[1+i*103:1+(i+1)*103]) for i in range(4)]
    out_start=1+21*103
    outs=[bytearray(ck[out_start+i*104:out_start+(i+1)*104]) for i in range(4)]
    return ins,outs

def resistor_template_records():
    ck=object_chunk(BASE_RES_DSN.read_bytes())
    assert ck[:2]==b'\x00\x00'
    recs=[]; p=2
    for i in range(21):
        recs.append(bytearray(ck[p:p+346])); p+=346
    return recs

def patch_terminal_fixed(template:bytearray,label:str,sx:int,sy:int,lx:int,ly:int,kind:str):
    r=bytearray(template); lab=label.encode('ascii')
    if len(lab)!=2: raise ValueError(label)
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    if kind=='in':
        len_off=30; label_off=31; coord_off=33
        assert r[len_off]==2
    else:
        len_off=31; label_off=32; coord_off=34
        assert r[len_off]==2
    r[label_off:label_off+2]=lab
    r[coord_off:coord_off+4]=i32(lx); r[coord_off+4:coord_off+8]=i32(ly)
    # Keep donor suffix bytes exactly. This is the terminal variant already observed to open.
    return bytes(r)

def patch_resistor_safe(template:bytearray,idx:int,ref:str,value2:str,x:int,y:int,final:bool=False):
    r=bytearray(template)
    assert len(ref)==2 and len(value2)==2
    r[0]=0xff; r[1]=2; r[2:4]=ref.encode('ascii')
    r[69]=2; r[70:72]=value2.encode('ascii')
    coord_fields=[(4,8),(72,76),(146,150),(231,235),(312,316)]
    pairs=[(x, y+121920),(x, y-121920),(x, y-375920),(x, y-375920),(x, y)]
    for (xo,yo),(xx,yy) in zip(coord_fields,pairs):
        r[xo:xo+4]=i32(xx); r[yo:yo+4]=i32(yy)
    r[324:328]=u32(idx)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def patch_resistor_variable(template:bytearray,idx:int,ref:str,value:str,x:int,y:int,final:bool=False):
    # Optional true-visible-value version. Variable-length value field expands records for 10k..21k.
    r=bytearray(template)
    assert len(ref)==2
    r[0]=0xff; r[1]=2; r[2:4]=ref.encode('ascii')
    old_len=r[69]
    new=value.encode('ascii')
    r[69]=len(new)
    r[70:70+old_len]=new
    if len(new)>old_len:
        r[70+old_len:70+old_len]=b'\x00'*(len(new)-old_len)
    elif len(new)<old_len:
        del r[70+len(new):70+old_len]
    delta=len(new)-old_len
    def off(o): return o+delta if o>70 else o
    coord_fields=[(4,8),(72,76),(146,150),(231,235),(312,316)]
    pairs=[(x, y+121920),(x, y-121920),(x, y-375920),(x, y-375920),(x, y)]
    for (xo,yo),(xx,yy) in zip(coord_fields,pairs):
        xo2,yo2=off(xo),off(yo)
        r[xo2:xo2+4]=i32(xx); r[yo2:yo2+4]=i32(yy)
    bindo=off(324)
    r[bindo:bindo+4]=u32(idx)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def build_block(true_visible=False):
    ins,outs=terminal_templates(); res_templates=resistor_template_records()
    conns=topology()
    term_inputs=[]; term_outputs=[]; resistors=[]; map_rows=[]
    for idx,left,right,col,row in conns:
        c=coords_for(col,row); k=(idx-1)%4
        term_inputs.append(patch_terminal_fixed(ins[k],left,c['in_symbol_x'],c['y'],c['in_label_x'],c['y'],'in'))
        term_outputs.append(patch_terminal_fixed(outs[k],right,c['out_symbol_x'],c['y'],c['out_label_x'],c['y'],'out'))
        ref=REFS[idx-1]
        if true_visible:
            rr=patch_resistor_variable(res_templates[idx-1],idx,ref,VISIBLE_TRUE[idx-1],c['x'],c['y'],final=(idx==21))
        else:
            rr=patch_resistor_safe(res_templates[idx-1],idx,ref,VISIBLE_SAFE[idx-1],c['x'],c['y'],final=(idx==21))
        resistors.append(rr)
        map_rows.append({'logical':LOGICAL[idx-1],'ref':ref,'value':CDB_VALUES[idx-1],'left_node':left,'right_node':right,'row':row,'col':col,'x':c['x'],'y':c['y']})
    block=b''.join(term_inputs)+b''.join(term_outputs)+b''.join(resistors)
    return block,map_rows

def rebuild_dsn(block:bytes):
    base=bytearray(BASE_RES_DSN.read_bytes())
    fi=base.find(b'ISIS CIRCUIT FILE'); obj=base.find(b'OBJECT DATA',fi); sec=base.find(b'ISIS CIRCUIT FILE',fi+1)
    # Terminal-first object blocks use one object-region header byte after OBJECT DATA.
    prefix=bytearray(base[:obj+len(b'OBJECT DATA')+1])
    tail=bytearray(base[sec:])
    first_isis=fi
    new_sec=len(prefix)+len(block)
    rel_obj=tail.find(b'OBJECT DATA')
    second_obj=new_sec+rel_obj
    ptr=second_obj+13
    prefix[first_isis-4:first_isis]=u32(ptr)
    cct=tail.find(b'CCT000')
    if cct!=-1: tail[cct+len(b'CCT000')+2:cct+len(b'CCT000')+6]=u32(first_isis)
    default=tail.find(b'__DEFAULT__\x00\x00')
    if default!=-1: tail[default+len(b'__DEFAULT__\x00\x00'):default+len(b'__DEFAULT__\x00\x00')+4]=u32(new_sec)
    out=prefix+bytearray(block)+tail
    return bytes(out), {'first_isis':first_isis,'second_isis':new_sec,'second_obj':second_obj,'ptr':ptr,'counts':{'TERINPUT':out.count(b'$TERINPUT'),'TEROUTPUT':out.count(b'$TEROUTPUT'),'COMPONENT_ID':out.count(b'COMPONENT ID')}}

def main():
    if OUTDIR.exists(): shutil.rmtree(OUTDIR)
    OUTDIR.mkdir()
    cdb=BASE_RES_CDB.read_bytes()
    shutil.copy2(E0_PROJECT,OUTDIR/'CONTROL_E001_EMPTY_BASE.pdsprj')
    results=[]
    for true_visible,name in [
        (False,'FINAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_CDB_TRUE_SAFE_VISIBLE.pdsprj'),
        (True,'OPTIONAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_TRUE_VISIBLE_VALUES.pdsprj')
    ]:
        block,topomap=build_block(true_visible=true_visible)
        dsn,info=rebuild_dsn(block)
        write_project(OUTDIR/name,cdb,dsn)
        (OUTDIR/(name+'.ROOT.CDB.bin')).write_bytes(cdb)
        (OUTDIR/(name+'.ROOT.DSN.bin')).write_bytes(dsn)
        results.append({'file':name,'true_visible':true_visible,'info':info})
    (OUTDIR/'topology_map.json').write_text(json.dumps(topomap,indent=2))
    (OUTDIR/'manifest.json').write_text(json.dumps({'base':'E001 only','tests':results,'notes':'Main file stores real 1k..21k values in ROOT.CDB. Safe visible labels use 1k..9k then Ak..Lk. Optional file tests true visible 10k..21k labels.'},indent=2))
    (OUTDIR/'README_TEST_FIRST.txt').write_text('''FINAL R21 resistor-terminal circuit, E001 base only\n\nTopology:\n  Branch A: R1..R7 in series from N0 to M0\n  Branch B: R8..RE in series from N0 to M0, parallel with Branch A\n  Tail:     RF..RL in series from M0 to Z0\n\nThis implements: 7 in series || 7 in series, then 7 more in series.\n\nTest first:\n  FINAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_CDB_TRUE_SAFE_VISIBLE.pdsprj\n\nThis is built from E001 PROJECT.XML + E001 PWRRAILS + generated ROOT.CDB + generated/rebuilt ROOT.DSN.\nIt is not using a full R4 project as base.\n\nActual CDB values:\n  R1=1k, R2=2k, ..., R9=9k, RA=10k, RB=11k, ..., RL=21k.\n\nVisible-safe labels:\n  1k..9k then Ak..Lk. This is intentional to preserve the fixed-width visible resistor record.\n\nOptional:\n  OPTIONAL_E001_R21_7PAR7_PLUS_7SERIES_TERMINALS_TRUE_VISIBLE_VALUES.pdsprj\n  This tries true visible labels 10k..21k by variable-length value fields. Test only after the safe file.\n\nNo explicit wire records are included. Terminals are placed at resistor pin-contact positions and repeated terminal labels define shared nodes.\n''')
    shutil.copy2(Path(__file__),OUTDIR/'generation_code_used.py')
    zip_path=ROOT/'FINAL_R21_7PAR7_PLUS_7SERIES_E001_TERMINALS.zip'
    if zip_path.exists(): zip_path.unlink()
    shutil.make_archive(str(zip_path).removesuffix('.zip'),'zip',OUTDIR)
    print(zip_path)

if __name__=='__main__': main()

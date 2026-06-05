#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, struct, zipfile
from pathlib import Path
ROOT=Path('/mnt/data')
E0_PROJECT=ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/CONTROL_E001_EMPTY_BASE.pdsprj'
R4_PROJECT=ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/CONTROL_R4_REAL_SOURCE_FOR_DEVICE_RECORDS_ONLY.pdsprj'
R12_WORKING=ROOT/'work_e001/E001_CDB_WRITTEN_R7_R12_GENERATION_SHOT/TEST_E001_R12_CDB_WRITTEN_DSN_REBUILT_E0_TAIL.pdsprj'
PAR4_PROJECT=ROOT/'work_term/CONTROL_B02_E008_four_parallel_N1_N2.pdsprj'
OUTDIR=ROOT/'R21_TERMINAL_NETWORK_V4_ORDER_SUFFIX_DIAGNOSTICS'
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

def coords_for(idx:int,col:int,row:int):
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

def terminal_templates_all():
    par=extract_visual_chunk(PAR4_PROJECT)
    ins=[bytearray(par[s:s+103]) for s in [0,103,206,309]]
    outs=[bytearray(par[s:s+104]) for s in [412,516,620,724]]
    wires_left=[bytearray(par[1175:1225]), bytearray(par[1621:1671]), bytearray(par[2067:2117]), bytearray(par[2513:2563])]
    wires_right=[bytearray(par[1225:1275]), bytearray(par[1671:1721]), bytearray(par[2117:2167]), bytearray(par[2563:2613])]
    return ins,outs,wires_left,wires_right

def resistor_template():
    d=read_member(R12_WORKING,'ROOT.DSN')
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    start=obj+len(b'OBJECT DATA')+2
    rec=bytearray(d[start:start+346])
    assert len(rec)==346 and rec[0]==0xff and rec.find(b'COMPONENT ID')>0 and rec.find(b'RESISTOR')>0
    return rec

def patch_label_2(r:bytearray, old:bytes, new:str):
    nb=new.encode('ascii')
    assert len(nb)==2
    p=r.find(old)
    if p<0: raise RuntimeError((old,new))
    r[p:p+2]=nb

def patch_terminal(template:bytearray, old:bytes, new:str, sx:int, sy:int, lx:int, ly:int, serial:int, kind:str, suffix_mode='keep', coord_mode='patch'):
    r=bytearray(template); patch_label_2(r,old,new)
    if coord_mode=='patch':
        # symbol/pin point coordinate near object start
        r[2:6]=i32(sx); r[6:10]=i32(sy)
        # label text coordinate after label bytes
        p=r.find(new.encode('ascii'))
        r[p+2:p+6]=i32(lx); r[p+6:p+10]=i32(ly)
    if suffix_mode=='zero':
        r[-1]=0
    elif suffix_mode=='unique':
        # V3 approach: keep final byte 01 but generate unique-ish 16-bit token.
        base = 0x0159 if kind=='in' else 0x018b
        val = (base + serial*0x01be) & 0xffff
        r[-3:-1]=u16(val)
        r[-1]=0x01
    elif suffix_mode=='keep':
        pass
    else:
        raise ValueError(suffix_mode)
    return bytes(r)

def patch_wire(template:bytearray,x1:int,y1:int,x2:int,y2:int,final=False):
    r=bytearray(template)
    r[34:38]=i32(x1); r[38:42]=i32(y1); r[42:46]=i32(x2); r[46:50]=i32(y2)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def patch_resistor_2char(template:bytearray,idx:int,ref:str,val:str,x:int,y:int,final=False):
    r=bytearray(template)
    assert len(ref)==2 and len(val)==2
    r[0]=0xff; r[1]=2; r[2:4]=ref.encode('ascii')
    r[69]=2; r[70:72]=val.encode('ascii')
    coord_fields=[(4,8),(72,76),(146,150),(231,235),(312,316)]
    pairs=[(x, y+121920),(x, y-121920),(x, y-375920),(x, y-375920),(x, y)]
    for (xo,yo),(xx,yy) in zip(coord_fields,pairs):
        r[xo:xo+4]=i32(xx); r[yo:yo+4]=i32(yy)
    r[324:328]=u32(idx)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def item_records(suffix_mode='keep', coord_mode='patch'):
    in_ts,out_ts,wl_ts,wr_ts=terminal_templates_all(); res_t=resistor_template()
    conns=topology(); items=[]; terminal_serial=0
    for idx,left,right,col,row in conns:
        c=coords_for(idx,col,row)
        in_template=in_ts[(idx-1)%4]; out_template=out_ts[(idx-1)%4]
        wl_template=wl_ts[(idx-1)%4]; wr_template=wr_ts[(idx-1)%4]
        left_term=patch_terminal(in_template,b'N1',left,c['lt_symbol_x'],c['y'],c['lt_label_x'],c['y'],terminal_serial,'in',suffix_mode,coord_mode); terminal_serial+=1
        right_term=patch_terminal(out_template,b'N2',right,c['rt_symbol_x'],c['y'],c['rt_label_x'],c['y'],terminal_serial,'out',suffix_mode,coord_mode); terminal_serial+=1
        res=patch_resistor_2char(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'])
        wl=patch_wire(wl_template,c['x']-254000,c['y'],c['x'],c['y'])
        wr=patch_wire(wr_template,c['x']+1524000,c['y'],c['x']+1270000,c['y'])
        items.append({'idx':idx,'left':left,'right':right,'term_in':left_term,'term_out':right_term,'res':res,'wire_l':wl,'wire_r':wr,'coords':c})
    return items

def build_object_block(kind:str,suffix_mode='keep',coord_mode='patch'):
    res_t=resistor_template(); block=bytearray(); man=[]
    items=item_records(suffix_mode,coord_mode)
    def add_resistors(final=True):
        nonlocal block
        for it in items:
            idx=it['idx']; c=it['coords']
            block+=patch_resistor_2char(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'],final=(final and idx==21))
    if kind=='resistors_only':
        add_resistors(True)
    elif kind=='two_terms_ordered_then_resistors':
        block+=items[0]['term_in']+items[0]['term_out']
        add_resistors(True)
    elif kind=='two_terms_donorcoords_then_resistors':
        items2=item_records(suffix_mode,'donor')
        block+=items2[0]['term_in']+items2[0]['term_out']
        add_resistors(True)
    elif kind=='all_inputs_outputs_then_resistors':
        for it in items: block+=it['term_in']
        for it in items: block+=it['term_out']
        add_resistors(True)
    elif kind=='all_inputs_outputs_then_resistors_wires':
        for it in items: block+=it['term_in']
        for it in items: block+=it['term_out']
        for it in items:
            idx=it['idx']; c=it['coords']
            block+=patch_resistor_2char(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'])
            block+=it['wire_l']+patch_wire(bytearray(it['wire_r']),c['x']+1524000,c['y'],c['x']+1270000,c['y'],final=(idx==21))
    elif kind=='donor_order_repeat_groups':
        # Same order as 4-parallel donor for each group: all inputs, all outputs, then R/wire/wire repeated.
        for it in items: block+=it['term_in']
        for it in items: block+=it['term_out']
        for it in items:
            idx=it['idx']; c=it['coords']
            block+=patch_resistor_2char(res_t,idx,REFS[idx-1],VISIBLE_VALUES[idx-1],c['x'],c['y'])
            block+=it['wire_l']+patch_wire(bytearray(it['wire_r']),c['x']+1524000,c['y'],c['x']+1270000,c['y'],final=(idx==21))
    else:
        raise ValueError(kind)
    for it in items:
        man.append({k:it[k] for k in ['idx','left','right']})
    return bytes(block),man

def build_dsn(object_block:bytes,tail_mode='E0_TAIL'):
    e0=read_member(E0_PROJECT,'ROOT.DSN'); r4=read_member(R4_PROJECT,'ROOT.DSN')
    e0_first=e0.find(b'ISIS CIRCUIT FILE'); e0_second=e0.find(b'ISIS CIRCUIT FILE',e0_first+1)
    r4_first=r4.find(b'ISIS CIRCUIT FILE'); r4_obj=r4.find(b'OBJECT DATA',r4_first)
    insert_marker=b'{PACKAGE=NULL}\n\x00'; insert_pos=e0.rfind(insert_marker,0,e0_first)+len(insert_marker)
    dev=bytearray(r4[insert_pos:r4_first])
    first_header=r4[r4_first:r4_obj+len(b'OBJECT DATA')+2]
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
    meta={'tail':tail_mode,'first_isis':first_isis_new,'object_block_len':len(object_block),'second_isis':second_isis_new,'second_object':second_obj,'ptr_before_first':ptr,
          'count_TERINPUT':out.count(b'$TERINPUT'),'count_TEROUTPUT':out.count(b'$TEROUTPUT'),'count_WIRE':out.count(b'WIRE'),'count_resistor_text':out.count(b'COMPONENT ID')}
    return bytes(out),meta

def main():
    if OUTDIR.exists(): shutil.rmtree(OUTDIR)
    OUTDIR.mkdir(parents=True)
    shutil.copy2(E0_PROJECT,OUTDIR/'CONTROL_E001_EMPTY_BASE.pdsprj')
    cdb=build_cdb(21)
    manifest={'title':'R21 terminal network V4 order/suffix diagnostics','reason':'V3 proved first two tests only (control and resistors-only) open; even two generated terminals caused VGDVC. V4 tests whether terminal object order or suffix token mutation caused the terminal crash.','files':[]}
    tests=[]
    for suffix in ['keep','unique']:
        for kind in ['two_terms_ordered_then_resistors','two_terms_donorcoords_then_resistors','all_inputs_outputs_then_resistors','all_inputs_outputs_then_resistors_wires']:
            tests.append((kind,suffix))
    tests.insert(0,('resistors_only','keep'))
    for kind,suffix in tests:
        obj,man=build_object_block(kind,suffix_mode=suffix,coord_mode='patch')
        for tail in ['E0_TAIL','R4_TAIL']:
            dsn,meta=build_dsn(obj,tail)
            name=f'TEST_R21_V4_{kind.upper()}_SUFFIX_{suffix.upper()}_{tail}.pdsprj'
            write_project(OUTDIR/name,cdb,dsn)
            (OUTDIR/(name+'.ROOT.CDB.bin')).write_bytes(cdb)
            (OUTDIR/(name+'.ROOT.DSN.bin')).write_bytes(dsn)
            manifest['files'].append({'name':name,'kind':kind,'suffix_mode':suffix,'tail':tail,'root_cdb_len':len(cdb),'root_dsn_len':len(dsn),**meta})
    (OUTDIR/'topology_map.json').write_text(json.dumps({'resistors':man},indent=2),encoding='utf-8')
    (OUTDIR/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (OUTDIR/'README_TEST_FIRST.txt').write_text('''# R21 terminal network V4 order/suffix diagnostics

V3 result:
- CONTROL opens.
- RESISTORS_ONLY opens.
- every terminal-containing file still gives VGDVC.DLL [000190DA].

V4 hypothesis:
The terminal crash may be caused by object ordering or terminal suffix mutation.
Real donor ordering is:
  all input terminals
  all output terminals
  then resistor + wire + wire groups
V3 order was terminal/resistor interleaved.

V4 variants:
- SUFFIX_KEEP: terminal suffix bytes are not modified except label/coordinates.
- SUFFIX_UNIQUE: V3-style generated terminal suffix token is used.
- TWO_TERMS_ORDERED_THEN_RESISTORS: only two terminals, before all resistors.
- TWO_TERMS_DONORCOORDS_THEN_RESISTORS: two terminals with donor coordinates, before all resistors.
- ALL_INPUTS_OUTPUTS_THEN_RESISTORS: 42 terminals first, then all 21 resistors, no wires.
- ALL_INPUTS_OUTPUTS_THEN_RESISTORS_WIRES: 42 terminals first, then resistor/wire/wire groups.

Test order:
1. CONTROL_E001_EMPTY_BASE.pdsprj
2. TEST_R21_V4_RESISTORS_ONLY_SUFFIX_KEEP_E0_TAIL.pdsprj
3. TEST_R21_V4_TWO_TERMS_ORDERED_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
4. TEST_R21_V4_TWO_TERMS_DONORCOORDS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
5. TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_SUFFIX_KEEP_E0_TAIL.pdsprj
6. TEST_R21_V4_ALL_INPUTS_OUTPUTS_THEN_RESISTORS_WIRES_SUFFIX_KEEP_E0_TAIL.pdsprj

Only if KEEP variants fail, test UNIQUE variants.
If an E0-tail fails, try its matching R4-tail fallback.

Report the first terminal-containing file that opens.
''',encoding='utf-8')
    shutil.copy2(Path(__file__),OUTDIR/'generation_code_used.py')
    zpath=ROOT/'R21_TERMINAL_NETWORK_V4_ORDER_SUFFIX_DIAGNOSTICS.zip'
    if zpath.exists(): zpath.unlink()
    with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in OUTDIR.rglob('*'): z.write(p,p.relative_to(OUTDIR.parent))
    print(zpath)
if __name__=='__main__': main()

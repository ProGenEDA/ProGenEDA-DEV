from __future__ import annotations
import json, shutil, struct, zipfile
from pathlib import Path

ROOT=Path('/mnt/data')
V6=ROOT/'v6'
OUTDIR=ROOT/'R21_TERMINAL_RESISTOR_FINAL_CHECKS_V7_E001'
CONTROL=V6/'CONTROL_E001_EMPTY_BASE.pdsprj'
BASE_RES_DSN=V6/'TEST_R21_V6_RESISTORS_ONLY_BASELINE_E0_TAIL.ROOT.DSN.bin'
# Use V6 all-terms unique as terminal donor because it opened structurally in user's report.
TERM_DSN=V6/'TEST_R21_V6_ALL_TERMS_FIXED_LABELPATCH_UNIQUE_NO_WIRES_E0_TAIL.ROOT.DSN.bin'

PROP_TEXT=b'{PRIMITIVE=ANALOGUE}\n\x00'
GRID=1270000
ROW_GAP=-1524000
REFS=['R1','R2','R3','R4','R5','R6','R7','R8','R9','RA','RB','RC','RD','RE','RF','RG','RH','RI','RJ','RK','RL']
VALUES=[f'{i}k' for i in range(1,22)]
VISIBLE_SAFE=['1k','2k','3k','4k','5k','6k','7k','8k','9k','Ak','Bk','Ck','Dk','Ek','Fk','Gk','Hk','Ik','Jk','Kk','Lk']

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
        z.writestr('SCRIPTS/PWRRAILS.DAT', read_member(CONTROL,'SCRIPTS/PWRRAILS.DAT'))
        z.writestr('ROOT.CDB', cdb)
        z.writestr('ROOT.DSN', dsn)
        z.writestr('PROJECT.XML', read_member(CONTROL,'PROJECT.XML'))

def build_cdb(n:int):
    out=bytearray(); out+=u32(7)
    # MODULE ROOT
    out+=u32(1)+u32(1)+u32(0)+enc_str('ROOT')+b'\x00'+u32(0)+u32(1)+u32(1)
    # SHEETS
    out+=u32(2)
    out+=u32(1)+u32(3)+u32(1)+enc_str('')+u32(10)+u32(0)
    out+=u32(2)+u32(2)+u32(0)+enc_str('Master Sheet')+u32(10)+u32(0)
    # ELEMENTS
    out+=u32(n)
    for idx in range(1,n+1):
        ref=REFS[idx-1]
        out+=u32(idx)+u32(1)+u32(0)+u32(idx)+enc_str(ref)
        out+=u32(2)+enc_str('1')+b'\x00'+enc_str('2')+b'\x00'
        out+=u32(0)+u32(idx)+u32(0)
    # BOARD
    out+=u32(1)+u32(1)+b'\x00'+enc_str('')+u32(1)
    # PARTS
    out+=u32(n)
    for idx in range(1,n+1):
        out+=u32(idx)+u32(1)+u32(0)+u32(0)+u32(0)
        out+=enc_str(REFS[idx-1])+enc_str(VALUES[idx-1])+enc_str('RESISTOR')+enc_str('')+enc_text(PROP_TEXT)
    # SNIPPETS
    out+=u32(0)
    return bytes(out)

def object_chunk(d:bytes):
    fi=d.find(b'ISIS CIRCUIT FILE'); obj=d.find(b'OBJECT DATA',fi); sec=d.find(b'ISIS CIRCUIT FILE',fi+1)
    return d[obj+len(b'OBJECT DATA'):sec]

def base_resistor_template_records():
    ck=object_chunk(BASE_RES_DSN.read_bytes())
    assert ck[:2]==b'\x00\x00'
    recs=[]; p=2
    for i in range(21):
        r=bytearray(ck[p:p+346]); p+=346
        assert r.find(b'COMPONENT ID')>0
        recs.append(r)
    return recs

def terminal_templates():
    ck=object_chunk(TERM_DSN.read_bytes())
    assert ck[0]==0
    in_t=[bytearray(ck[1+i*103:1+(i+1)*103]) for i in range(4)]
    out_start=1+21*103
    out_t=[bytearray(ck[out_start+i*104:out_start+(i+1)*104]) for i in range(4)]
    assert all(t.find(b'$TERINPUT')>0 for t in in_t)
    assert all(t.find(b'$TEROUTPUT')>0 for t in out_t)
    return in_t,out_t

def topology(n=21):
    if n==1:
        return [(1,'N0','A1',0,0)]
    if n==2:
        return [(1,'N0','A1',0,0),(2,'A1','A2',1,0)]
    conns=[]
    nodes=['N0']+[f'A{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((i+1,nodes[i],nodes[i+1],i,0))
    nodes=['N0']+[f'B{i}' for i in range(1,7)]+['M0']
    for i in range(7): conns.append((8+i,nodes[i],nodes[i+1],i,1))
    nodes=['M0']+[f'C{i}' for i in range(1,7)]+['Z0']
    for i in range(7): conns.append((15+i,nodes[i],nodes[i+1],i,2))
    return conns

def coords_for(col:int,row:int):
    # Spread more than earlier attempts to make visual diagnosis easier.
    x0=-7620000; y0=5080000
    x=x0+col*GRID*2
    y=y0+row*ROW_GAP
    return x,y

def patch_resistor_record(template:bytearray, idx:int, ref:str, visible_val:str, x:int, y:int, final=False, true_visible_values=False):
    r=bytearray(template)
    # ref must remain two chars at this stage.
    rb=ref.encode('ascii'); assert len(rb)==2
    r[0]=0xff; r[1]=2; r[2:4]=rb
    vb=visible_val.encode('ascii')
    if true_visible_values and len(vb)==3:
        # Experimental variable-length value field. The parser should use the length byte.
        # This is not used in the main SAFE files.
        r[69]=3
        r = r[:70] + bytearray(vb) + r[72:]
    else:
        # Safe fixed-width stage.
        if len(vb)!=2:
            vb=VISIBLE_SAFE[idx-1].encode('ascii')
        r[69]=2; r[70:72]=vb[:2]
    # Patch coordinate fields. If record expanded, offsets after value field shift by +1.
    shift = (len(r)-346)
    fields=[(4,8),(72+shift,76+shift),(146+shift,150+shift),(231+shift,235+shift),(312+shift,316+shift)]
    pairs=[(x,y+121920),(x,y-121920),(x,y-375920),(x,y-375920),(x,y)]
    for (xo,yo),(xx,yy) in zip(fields,pairs):
        r[xo:xo+4]=i32(xx); r[yo:yo+4]=i32(yy)
    r[324+shift:328+shift]=u32(idx)
    r[-1]=0xff if final else 0x00
    return bytes(r)

def patch_terminal_fixed(template:bytearray,label:str,sx:int,sy:int,lx:int,ly:int,kind:str,serial:int):
    r=bytearray(template)
    lab=label.encode('ascii')
    if len(lab)!=2: raise ValueError(label)
    r[1:5]=i32(sx); r[5:9]=i32(sy)
    if kind=='in':
        len_off=30; label_off=31; coord_off=33; base=0x0159
        assert r[len_off]==2
    else:
        len_off=31; label_off=32; coord_off=34; base=0x018b
        assert r[len_off]==2
    r[label_off:label_off+2]=lab
    r[coord_off:coord_off+4]=i32(lx); r[coord_off+4:coord_off+8]=i32(ly)
    # Unique suffix; keep record terminator byte 00.
    seq=(base+serial*0x01be)&0xffff
    r[-4:-2]=u16(seq); r[-2]=0x01; r[-1]=0x00
    return bytes(r)

def terminal_positions(x:int,y:int,mode:str):
    # resistor pins inferred from previous successful resistor/wire donor:
    left_pin=x
    right_pin=x+1270000
    if mode=='old_spacing':
        in_sx=x-508000; out_sx=x+1778000
    elif mode=='contact_tip':
        # inferred terminal contact point is symbol_x +/-254000.
        in_sx=left_pin-254000
        out_sx=right_pin+254000
    elif mode=='symbol_on_pin':
        in_sx=left_pin
        out_sx=right_pin
    else:
        raise ValueError(mode)
    # Keep labels away from the resistor body.
    in_lx=in_sx-381000
    out_lx=out_sx+381000
    return {
        'in_sx':in_sx,'in_sy':y,'in_lx':in_lx,'in_ly':y,
        'out_sx':out_sx,'out_sy':y,'out_lx':out_lx,'out_ly':y,
    }

def build_object_block(n:int, term_mode:str|None, order:str='terms_first', true_visible_values=False):
    rs=base_resistor_template_records(); ins,outs=terminal_templates(); conns=topology(n)
    term_records=[]; res_records=[]; serial=0; manifest=[]
    for idx,left,right,col,row in conns:
        x,y=coords_for(col,row)
        if term_mode:
            p=terminal_positions(x,y,term_mode)
            k=(idx-1)%4
            lt=patch_terminal_fixed(ins[k],left,p['in_sx'],p['in_sy'],p['in_lx'],p['in_ly'],'in',serial); serial+=1
            rt=patch_terminal_fixed(outs[k],right,p['out_sx'],p['out_sy'],p['out_lx'],p['out_ly'],'out',serial); serial+=1
            if order=='interleaved':
                # record order per component: left terminal, resistor, right terminal
                pass
            else:
                term_records.extend([lt,rt])
        rr=patch_resistor_record(rs[(idx-1)%21],idx,REFS[idx-1],VALUES[idx-1] if true_visible_values else VISIBLE_SAFE[idx-1],x,y,False,true_visible_values=true_visible_values)
        if order=='interleaved' and term_mode:
            res_records.append((lt,rr,rt))
        else:
            res_records.append(rr)
        manifest.append({'idx':idx,'ref':REFS[idx-1],'value':VALUES[idx-1],'left':left,'right':right,'x':x,'y':y})
    if order=='interleaved' and term_mode:
        flat=bytearray()
        for idx,(lt,rr,rt) in enumerate(res_records,1):
            flat += lt
            flat += rr
            flat += rt
        block=flat
    else:
        block=bytearray(b''.join(term_records)+b''.join(res_records))
    # Final object terminator: set only the last object's final byte FF.
    if block:
        block[-1]=0xff
    header_len=1 if term_mode else 2
    return bytes(block), header_len, manifest

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
    # patch pointer before first ISIS in prefix; this construction keeps first_isis stable.
    prefix[first_isis-4:first_isis]=u32(ptr)
    cct=tail.find(b'CCT000')
    if cct!=-1: tail[cct+len(b'CCT000')+2:cct+len(b'CCT000')+6]=u32(first_isis)
    default=tail.find(b'__DEFAULT__\x00\x00')
    if default!=-1: tail[default+len(b'__DEFAULT__\x00\x00'):default+len(b'__DEFAULT__\x00\x00')+4]=u32(new_sec)
    out=prefix+bytearray(block)+tail
    info={'first_isis':first_isis,'second_isis':new_sec,'second_obj':second_obj,'ptr':ptr,'header_len':header_len,'counts':{'TERINPUT':out.count(b'$TERINPUT'),'TEROUTPUT':out.count(b'$TEROUTPUT'),'COMPONENT_ID':out.count(b'COMPONENT ID'),'RESISTOR':out.count(b'RESISTOR')}}
    return bytes(out), info

def make(name,n,term_mode=None,order='terms_first',true_visible_values=False):
    block,hlen,mapinfo=build_object_block(n,term_mode,order,true_visible_values=true_visible_values)
    dsn,info=rebuild_dsn(block,hlen)
    cdb=build_cdb(n)
    write_project(OUTDIR/(name+'.pdsprj'),cdb,dsn)
    (OUTDIR/(name+'.ROOT.CDB.bin')).write_bytes(cdb)
    (OUTDIR/(name+'.ROOT.DSN.bin')).write_bytes(dsn)
    return {'file':name+'.pdsprj','n':n,'term_mode':term_mode,'order':order,'true_visible_values':true_visible_values,'info':info,'topology':mapinfo}

def main():
    if OUTDIR.exists(): shutil.rmtree(OUTDIR)
    OUTDIR.mkdir()
    shutil.copy2(CONTROL,OUTDIR/'CONTROL_E001_EMPTY_BASE.pdsprj')
    tests=[]
    # baseline: no terminals, proves E001 resistor core still works.
    tests.append(make('TEST_V7_R1_RESISTOR_ONLY_E001_BASELINE',1,None))
    tests.append(make('TEST_V7_R21_RESISTORS_ONLY_E001_BASELINE',21,None))
    # coordinate calibration around one resistor.
    for mode in ['old_spacing','contact_tip','symbol_on_pin']:
        tests.append(make(f'TEST_V7_R1_TERMINALS_{mode.upper()}_NO_WIRES',1,mode,'terms_first'))
    # two-resistor series check.
    tests.append(make('TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_NO_WIRES',2,'contact_tip','terms_first'))
    tests.append(make('TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_INTERLEAVED_NO_WIRES',2,'contact_tip','interleaved'))
    # final requested topology with terminals but no explicit wire records yet.
    tests.append(make('TEST_V7_R21_FINAL_CONTACT_TIP_TERMS_FIRST_NO_WIRES_SAFE_VALUES',21,'contact_tip','terms_first'))
    tests.append(make('TEST_V7_R21_FINAL_CONTACT_TIP_INTERLEAVED_NO_WIRES_SAFE_VALUES',21,'contact_tip','interleaved'))
    # optional experimental true visible values for 10k+; CDB is true in all files, this one tests variable text length.
    tests.append(make('TEST_V7_R21_EXPERIMENTAL_TRUE_VISIBLE_VALUES_CONTACT_TIP_NO_WIRES',21,'contact_tip','terms_first',true_visible_values=True))
    manifest={'base':'CONTROL_E001_EMPTY_BASE from E001','notes':'All projects use E001 PROJECT.XML/PWRRAILS and generated ROOT.CDB/ROOT.DSN. No R4 project base is used. Terminal-contact files contain no explicit wire records. They test terminal pin contact and label-net semantics first.','tests':tests}
    (OUTDIR/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUTDIR/'generation_code_used.py').write_text(Path(__file__).read_text())
    (OUTDIR/'README_TEST_FIRST.txt').write_text('''R21 Terminal + Resistor Final Checks V7, E001 only

Purpose:
- Do NOT lock terminals fully yet; run final coordinate/contact checks first.
- Confirm terminal coordinates against one resistor and two series resistors.
- Then test the requested 21-resistor topology using generated CDB-backed resistors + generated terminals.

Important:
- All generated files use E001 PROJECT.XML and E001 PWRRAILS.
- ROOT.CDB is generated for the resistor count in that file.
- ROOT.DSN is rebuilt/generated from the E001-derived resistor baseline.
- No full R4 project is used as a base.
- These tests avoid explicit wire records. The next question is whether terminal endpoints placed on resistor pins + repeated terminal labels are enough.

Test order:
1 CONTROL_E001_EMPTY_BASE.pdsprj
2 TEST_V7_R1_RESISTOR_ONLY_E001_BASELINE.pdsprj
3 TEST_V7_R21_RESISTORS_ONLY_E001_BASELINE.pdsprj
4 TEST_V7_R1_TERMINALS_OLD_SPACING_NO_WIRES.pdsprj
5 TEST_V7_R1_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
6 TEST_V7_R1_TERMINALS_SYMBOL_ON_PIN_NO_WIRES.pdsprj
7 TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_NO_WIRES.pdsprj
8 TEST_V7_R2_SERIES_TERMINALS_CONTACT_TIP_INTERLEAVED_NO_WIRES.pdsprj
9 TEST_V7_R21_FINAL_CONTACT_TIP_TERMS_FIRST_NO_WIRES_SAFE_VALUES.pdsprj
10 TEST_V7_R21_FINAL_CONTACT_TIP_INTERLEAVED_NO_WIRES_SAFE_VALUES.pdsprj
11 Optional: TEST_V7_R21_EXPERIMENTAL_TRUE_VISIBLE_VALUES_CONTACT_TIP_NO_WIRES.pdsprj

What to report:
- Which R1 terminal coordinate variant looks correct? OLD_SPACING, CONTACT_TIP, or SYMBOL_ON_PIN?
- Do R2 series terminal files open?
- Do final R21 files open?
- Does simulation start without missing model errors?
- Are terminals visibly on resistor pins, too far, or overlapping?
- Does optional TRUE_VISIBLE_VALUES open or produce bad object record?

Values:
- ROOT.CDB stores actual values 1k..21k in all generated files.
- SAFE visible labels use 1k..9k then Ak..Lk for stability.
- EXPERIMENTAL_TRUE_VISIBLE_VALUES tests visible 10k..21k by variable-length value fields.
''')
    zip_path=ROOT/'R21_TERMINAL_RESISTOR_FINAL_CHECKS_V7_E001.zip'
    if zip_path.exists(): zip_path.unlink()
    shutil.make_archive(str(zip_path).removesuffix('.zip'),'zip',OUTDIR)
    print(zip_path)

if __name__=='__main__': main()

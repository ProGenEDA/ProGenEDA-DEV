from __future__ import annotations
import json, zipfile, hashlib, shutil, re, struct
from pathlib import Path

ROOT = Path('/mnt/data')
DONOR_ROOT = ROOT / 'cap_donor_analysis'
SOURCE_ZIP = ROOT / 'CAP_T04_POWER_CAPACITOR_GROUND.zip'
OUT_ROOT = ROOT / 'CAPACITOR_FIRST_ATTEMPTS_2026_05_29'
ZIP_OUT = ROOT / 'CAPACITOR_FIRST_ATTEMPTS_2026_05_29.zip'

MARKERS = [b'CAPACITOR', b'CAP10', b'CAP', b'C1', b'1uF', b'RESISTOR', b'COMPONENT ID', b'COMPONENT VALUE', b'SUBCKT NAME', b'PROPERTIES', b'WIRE', b'$TERINPUT', b'$TEROUTPUT', b'$TERPOWER', b'$TERGROUND']

DONOR_CASES = [
    ('CAP_GEN_T01_SINGLE_CAPACITOR_TEMPLATE', 'CAP_T01_SINGLE_CAPACITOR_1uF.pdsprj', 'single capacitor donor template'),
    ('CAP_GEN_T02_CAPACITOR_BETWEEN_TERMINALS_TEMPLATE', 'CAP_T02_CAPACITOR_BETWEEN_TWO_TERMINALS.pdsprj', 'capacitor between input/output terminals donor template'),
    ('CAP_GEN_T03_RESISTOR_CAPACITOR_SERIES_TEMPLATE', 'CAP_T03_RESISTOR_CAPACITOR_SERIES.pdsprj', 'resistor-capacitor series donor template'),
    ('CAP_GEN_T04_POWER_CAPACITOR_GROUND_TEMPLATE', 'CAP_T04_POWER_CAPACITOR_GROUND.pdsprj', 'power-capacitor-ground donor template'),
]

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())

def u32(x: int) -> bytes:
    return struct.pack('<I', x)

def read_member(project: Path | bytes, name: str) -> bytes:
    data = project if isinstance(project, bytes) else project.read_bytes()
    with zipfile.ZipFile(Path('/tmp/_dummy') if False else __import__('io').BytesIO(data)) as z:
        return z.read(name)

def zip_member_bytes(project_bytes: bytes, name: str) -> bytes:
    import io
    with zipfile.ZipFile(io.BytesIO(project_bytes)) as z:
        return z.read(name)

def project_member(project_path: Path, name: str) -> bytes:
    with zipfile.ZipFile(project_path) as z:
        return z.read(name)

def object_chunk_from_dsn(dsn: bytes) -> bytes:
    fi = dsn.find(b'ISIS CIRCUIT FILE')
    obj = dsn.find(b'OBJECT DATA', fi)
    sec = dsn.find(b'ISIS CIRCUIT FILE', fi + 1)
    if fi < 0 or obj < 0 or sec < 0:
        raise RuntimeError('Could not locate DSN object chunk boundaries')
    return dsn[obj + len(b'OBJECT DATA'):sec]

def marker_counts(b: bytes) -> dict[str, int]:
    return {m.decode('latin1'): b.count(m) for m in MARKERS if b.count(m)}

def marker_offsets_first(b: bytes) -> list[dict[str, int | str]]:
    out = []
    for m in [b'$TERINPUT', b'$TEROUTPUT', b'$TERPOWER', b'$TERGROUND', b'COMPONENT ID', b'CAPACITOR', b'WIRE', b'RESISTOR']:
        for mat in re.finditer(re.escape(m), b):
            out.append({'offset': mat.start(), 'marker': m.decode('latin1')})
    return sorted(out, key=lambda x: int(x['offset']))[:12]

def rebuild_dsn_from_e001(e0_project: Path, donor_project: Path, object_chunk: bytes) -> bytes:
    """Rebuild DSN using the same stable E001/header/tail strategy used by the previous V9 generators.

    The output is not a byte-for-byte clone of the donor DSN; it is an E001-based generated DSN with a donor object chunk.
    """
    e0 = project_member(e0_project, 'ROOT.DSN')
    donor = project_member(donor_project, 'ROOT.DSN')

    e0_first = e0.find(b'ISIS CIRCUIT FILE')
    e0_second = e0.find(b'ISIS CIRCUIT FILE', e0_first + 1)
    donor_first = donor.find(b'ISIS CIRCUIT FILE')
    donor_obj = donor.find(b'OBJECT DATA', donor_first)
    if min(e0_first, e0_second, donor_first, donor_obj) < 0:
        raise RuntimeError('Missing ISIS/OBJECT DATA section marker')

    marker = b'{PACKAGE=NULL}\n\x00'
    insert = e0.rfind(marker, 0, e0_first) + len(marker)
    if insert < len(marker):
        raise RuntimeError('Could not find E001 package insert marker')

    dev = bytearray(donor[insert:donor_first])
    first_header = donor[donor_first:donor_obj + len(b'OBJECT DATA')]
    tail = bytearray(e0[e0_second:])

    first_isis = insert + len(dev)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b'OBJECT DATA')
    ptr = second_obj + 13

    # Patch pointers using same strategy as previous V9 generator.
    if len(dev) >= 4:
        dev[-4:] = u32(ptr)
    cct = tail.find(b'CCT000')
    if cct != -1:
        tail[cct + len(b'CCT000') + 2:cct + len(b'CCT000') + 6] = u32(first_isis)
    default = tail.find(b'__DEFAULT__\x00\x00')
    if default != -1:
        tail[default + len(b'__DEFAULT__\x00\x00'):default + len(b'__DEFAULT__\x00\x00') + 4] = u32(second_isis)

    return bytes(bytearray(e0[:insert]) + dev + first_header + bytearray(object_chunk) + tail)

def write_project(out_path: Path, root_cdb: bytes, root_dsn: bytes, control_project: Path):
    with zipfile.ZipFile(control_project) as base:
        project_xml = base.read('PROJECT.XML')
        pwr = base.read('SCRIPTS/PWRRAILS.DAT')
    with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('SCRIPTS/PWRRAILS.DAT', pwr)
        z.writestr('ROOT.CDB', root_cdb)
        z.writestr('ROOT.DSN', root_dsn)
        z.writestr('PROJECT.XML', project_xml)

def validate_attempt(object_chunk: bytes, root_cdb: bytes, root_dsn: bytes, donor_obj_hash: str, source_desc: str) -> list[str]:
    issues = []
    if not object_chunk:
        issues.append('object chunk is empty')
    if object_chunk[0] != 0:
        issues.append(f'object chunk first byte {object_chunk[0]:02x} != 00')
    if object_chunk[-1] != 0xff:
        issues.append(f'object chunk final byte {object_chunk[-1]:02x} != ff')
    if sha256_bytes(object_chunk) != donor_obj_hash:
        issues.append('rebuilt object chunk hash changed from donor chunk')
    if b'CAPACITOR' not in root_cdb:
        issues.append('ROOT.CDB lacks CAPACITOR marker')
    if b'CAPACITOR' not in object_chunk:
        issues.append('object chunk lacks CAPACITOR marker')
    if b'ROOT.CDB' in root_dsn:
        issues.append('ROOT.DSN unexpectedly contains ROOT.CDB literal')
    return issues

def make_case(case_id: str, donor_name: str, description: str, control_project: Path) -> dict:
    donor_project = DONOR_ROOT / donor_name
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    donor_cdb = project_member(donor_project, 'ROOT.CDB')
    donor_dsn = project_member(donor_project, 'ROOT.DSN')
    donor_obj = object_chunk_from_dsn(donor_dsn)
    rebuilt_dsn = rebuild_dsn_from_e001(control_project, donor_project, donor_obj)
    rebuilt_obj = object_chunk_from_dsn(rebuilt_dsn)

    out_project = case_dir / f'{case_id}.pdsprj'
    write_project(out_project, donor_cdb, rebuilt_dsn, control_project)
    (case_dir / f'{case_id}.ROOT.CDB.bin').write_bytes(donor_cdb)
    (case_dir / f'{case_id}.ROOT.DSN.bin').write_bytes(rebuilt_dsn)
    (case_dir / 'source_object_chunk.bin').write_bytes(donor_obj)

    issues = validate_attempt(rebuilt_obj, donor_cdb, rebuilt_dsn, sha256_bytes(donor_obj), donor_name)

    manifest = {
        'case_id': case_id,
        'status': 'experimental_unvalidated_first_capacitor_template_attempt',
        'description': description,
        'method': 'Use empty E001 project shell. Copy donor capacitor ROOT.CDB template. Extract donor ROOT.DSN object chunk and rebuild ROOT.DSN through the same E001/donor-header/tail method used by previous V9 generators. No mutation of capacitor ref/value/coordinates yet.',
        'source_donor': donor_name,
        'source_donor_sha256': sha256_file(donor_project),
        'project_file': out_project.name,
        'object_chunk_len': len(donor_obj),
        'root_cdb_len': len(donor_cdb),
        'root_dsn_len': len(rebuilt_dsn),
        'marker_counts': {
            'object_chunk': marker_counts(rebuilt_obj),
            'root_cdb': marker_counts(donor_cdb),
            'root_dsn': marker_counts(rebuilt_dsn),
        },
        'marker_offsets_first': marker_offsets_first(rebuilt_obj),
        'static_validation_issues': issues,
        'hashes': {
            out_project.name: sha256_file(out_project),
            'ROOT.CDB': sha256_bytes(donor_cdb),
            'ROOT.DSN': sha256_bytes(rebuilt_dsn),
            'donor_object_chunk': sha256_bytes(donor_obj),
            'CONTROL_E001_EMPTY_BASE.pdsprj': sha256_file(control_project),
        },
        'limitations': [
            'This is a first donor-template generation attempt, not a generalized capacitor generator yet.',
            'Reference/value/coordinate patching is not locked yet.',
            'The purpose is to verify that the capacitor CDB and DSN object chunk can be rebuilt into an E001-based generated project without losing the circuit.',
        ],
    }
    (case_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    (case_dir / 'README_TEST_FIRST.txt').write_text(f'''Capacitor first attempt: {case_id}\n\nSource donor: {donor_name}\nDescription: {description}\n\nOpen this file in Proteus:\n{out_project.name}\n\nCheck:\n- Does it open without VGDVC/bad object error?\n- Does the capacitor appear?\n- Does C1 and 1uF appear correctly?\n- Are wires/terminals preserved for this donor style?\n- Does save-as/reopen preserve the capacitor?\n\nStatic validation issues: {issues}\n''')
    shutil.copy(Path(__file__), case_dir / 'generation_code_used.py')
    return manifest

def main():
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    control_project = DONOR_ROOT / 'CONTROL_E001_EMPTY_BASE.pdsprj'
    attempts = []
    for case_id, donor_name, desc in DONOR_CASES:
        attempts.append(make_case(case_id, donor_name, desc, control_project))

    summary = {
        'case': 'CAPACITOR_FIRST_ATTEMPTS_2026_05_29',
        'status': 'experimental_unvalidated_first_generation_attempt',
        'source_zip': {
            'filename': SOURCE_ZIP.name,
            'sha256': sha256_file(SOURCE_ZIP),
        },
        'method_summary': 'First capacitor attempts are donor-template transplants: exact capacitor ROOT.CDB plus exact donor ROOT.DSN object chunk rebuilt into an E001-based generated project. This tests capacitor template viability before generalized patching.',
        'attempts': attempts,
    }
    (OUT_ROOT / 'summary_manifest.json').write_text(json.dumps(summary, indent=2))
    (OUT_ROOT / 'README_TEST_FIRST.txt').write_text('''Capacitor first generation attempts.\n\nOpen in order:\n1. CAP_GEN_T01_SINGLE_CAPACITOR_TEMPLATE/CAP_GEN_T01_SINGLE_CAPACITOR_TEMPLATE.pdsprj\n2. CAP_GEN_T02_CAPACITOR_BETWEEN_TERMINALS_TEMPLATE/CAP_GEN_T02_CAPACITOR_BETWEEN_TERMINALS_TEMPLATE.pdsprj\n3. CAP_GEN_T03_RESISTOR_CAPACITOR_SERIES_TEMPLATE/CAP_GEN_T03_RESISTOR_CAPACITOR_SERIES_TEMPLATE.pdsprj\n4. CAP_GEN_T04_POWER_CAPACITOR_GROUND_TEMPLATE/CAP_GEN_T04_POWER_CAPACITOR_GROUND_TEMPLATE.pdsprj\n\nThese are conservative donor-template rebuilds, not generalized capacitor generation yet.\n''')

    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    with zipfile.ZipFile(ZIP_OUT, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT_ROOT.rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(OUT_ROOT))

    summary['zip'] = {
        'filename': ZIP_OUT.name,
        'size_bytes': ZIP_OUT.stat().st_size,
        'sha256': sha256_file(ZIP_OUT),
    }
    (OUT_ROOT / 'summary_manifest.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({'zip': str(ZIP_OUT), 'summary': summary}, indent=2))

if __name__ == '__main__':
    main()

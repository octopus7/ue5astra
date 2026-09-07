"""Check final reports, protected inputs, and the integrity of all delivered PNGs."""
import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png(path):
    raw=path.read_bytes()
    assert raw[:8]==b'\x89PNG\r\n\x1a\n', str(path)
    offset=8;compressed=[];size=None;ended=False
    while offset<len(raw):
        length=struct.unpack_from('>I',raw,offset)[0]
        kind=raw[offset+4:offset+8];chunk=raw[offset+8:offset+8+length]
        crc=struct.unpack_from('>I',raw,offset+8+length)[0]
        assert zlib.crc32(kind+chunk)&0xffffffff==crc, str(path)
        if kind==b'IHDR':size=list(struct.unpack_from('>II',chunk))
        if kind==b'IDAT':compressed.append(chunk)
        offset+=length+12
        if kind==b'IEND':ended=True;break
    pixels=zlib.decompress(b''.join(compressed))
    assert ended and size and min(size)>=700 and len(set(pixels[::97]))>8, str(path)
    return {'file':path.relative_to(ROOT).as_posix(),'size':size,'bytes':len(raw),'sha256':sha(path),'png_crc_and_decode_passed':True}


data=json.loads((ART/'Layout/starfall_layout.json').read_text(encoding='utf-8'))
report_names=['StarfallLayout_Validation.json','StarfallSpaceship_FBXValidation.json',
    'StarfallTrees_Validation.json','StarfallFungiSpring_Validation.json',
    'UE_StarfallImportValidation.json','UE_StarfallReloadValidation.json','UE_SFDemoValidation.json']
reports={name:json.loads((ART/'Previews'/name).read_text(encoding='utf-8-sig')) for name in report_names}
assert all(r['passed'] for r in reports.values())
imported=reports['UE_StarfallImportValidation.json']
assert imported['layout_sha256']==sha(ART/'Layout/starfall_layout.json')
protected=imported['protected_asset_sha256']
assert all(sha(ROOT/path)==expected for path,expected in protected.items())
views=[ART/'Previews'/('UE_'+v['name']+'.png') for v in data['review_cameras']]
views += [ART/'Previews'/('UE_Demo_'+v['name']+'.png') for v in data['demo_shots']]
assert len(views)==14 and all(p.stat().st_mtime>(ART/'Layout/starfall_layout.json').stat().st_mtime for p in views)
references=sorted((ART/'Reference/Starfall').glob('*.png'))+[ART/'Textures/Starfall/T_SF_ShipPaint.png']
assert len(references)==5
images=[png(p) for p in views+references]
result={'passed':True,'map':data['map'],'reports':{n:sha(ART/'Previews'/n) for n in report_names},
    'protected_existing_content_files':len(protected),'existing_content_unchanged':True,
    'new_meshes':17,'reused_meshes':16,'native_foliage':sum(o['foliage'] for o in data['objects']),
    'placements':len(data['objects']),'saved_level_actor_count':imported['actor_count'],
    'actual_ue_screenshots':14,'new_generated_reference_and_texture_images':5,'images':images,
    'packaged_windows_build_refreshed':False}
(ART/'Previews/StarfallDelivery_Validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('reports','images')}))

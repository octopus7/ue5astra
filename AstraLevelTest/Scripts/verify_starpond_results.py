"""Consolidate saved UE evidence without launching another editor."""
import hashlib
import json
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREVIEWS=ROOT/'ArtSource/Previews'
MAP=ROOT/'Content/Astra/Maps/L_AstraStarPond.umap'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    reports={}
    for name in ('UE_StarPondImportValidation','UE_StarPondValidation',
                 'UE_StarPondRuntimeValidation','UE_SPDemoValidation'):
        path=PREVIEWS/(name+'.json')
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        assert value['passed'],name+' failed'
        assert path.stat().st_mtime>=MAP.stat().st_mtime,name+' predates the saved map'
        reports[name]={'sha256':digest(path),'passed':True}
    imported=json.loads((PREVIEWS/'UE_StarPondImportValidation.json').read_text())
    assert all(digest(ROOT/path)==expected for path,expected in imported['protected_asset_sha256'].items()),'Existing content changed'
    assert digest(ROOT/'ArtSource/Layout/starpond_layout.json')==imported['layout_sha256']
    assert digest(ROOT/'ArtSource/Layout/starpond_height.r16')==imported['terrain_sha256']
    images={}
    for view in ('SPPond','SPElephant','SPGate','SPConstellation','SPLilies','SPOverview','SPElephantLater'):
        path=PREVIEWS/('UE_'+view+'.png')
        data=path.read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n'
        dimensions=struct.unpack('>II',data[16:24])
        assert dimensions==(1600,1000),(view,dimensions)
        assert path.stat().st_mtime>=MAP.stat().st_mtime,view+' predates the saved map'
        log=(ROOT/'Saved'/('Review_'+view+'.log')).read_text(encoding='utf-8-sig')
        assert all(error not in log for error in ('Failed to compile Material','LogShaderCompilers: Error','LogMaterial: Error','missing bUsedWith'))
        images[view]={'file':path.relative_to(ROOT).as_posix(),'size':dimensions,'sha256':digest(path)}
    owned={}
    for path in (ROOT/'Content').rglob('*'):
        if path.is_file() and path.suffix in ('.umap','.uasset','.uexp','.ubulk') and ('StarPond' in path.parts or path==MAP):
            owned[path.relative_to(ROOT).as_posix()]=digest(path)
    report={'passed':True,'map':'/Game/Astra/Maps/L_AstraStarPond',
            'map_sha256':digest(MAP),'reports':reports,'actual_ue_captures':images,
            'protected_content_file_count':len(imported['protected_asset_sha256']),
            'owned_content_sha256':owned,
            'scope':'UE 5.7.4 editor game execution; this level has not been added to a new Shipping package.'}
    (PREVIEWS/'UE_StarPondFinalValidation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Star Pond evidence passed: 4 reports, 7 actual UE captures, '+str(len(owned))+' owned assets.')

if __name__=='__main__':main()

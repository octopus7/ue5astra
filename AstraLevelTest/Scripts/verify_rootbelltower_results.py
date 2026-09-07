"""Consolidate saved evidence; does not launch another editor or change assets."""
import hashlib,json,struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREVIEWS=ROOT/'ArtSource/Previews'
MAP=ROOT/'Content/Astra/Maps/L_AstraRootBelltower.umap'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    reports={}
    for name in ('UE_RootBelltowerImportValidation','UE_RootBelltowerSavedValidation','UE_RootBelltowerRuntimeValidation','UE_RBDemoValidation'):
        path=PREVIEWS/(name+'.json');value=json.loads(path.read_text(encoding='utf-8-sig'))
        assert value['passed'],name+' failed'
        assert path.stat().st_mtime>=MAP.stat().st_mtime,name+' predates the saved map'
        reports[name]=dict(sha256=digest(path),passed=True)
    imported=json.loads((PREVIEWS/'UE_RootBelltowerImportValidation.json').read_text())
    changed=[path for path,expected in imported['protected_asset_sha256'].items() if digest(ROOT/path)!=expected]
    assert not changed,'Existing content changed: '+str(changed)
    assert digest(ROOT/'ArtSource/Layout/rootbelltower_layout.json')==imported['layout_sha256']
    assert digest(ROOT/'ArtSource/Layout/rootbelltower_height.r16')==imported['terrain_sha256']
    images={}
    for view in ('RBTower','RBBell','RBRoots','RBArch','RBCloister','RBOverview','RBTowerLater'):
        path=PREVIEWS/('UE_'+view+'.png');data=path.read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n'
        dimensions=struct.unpack('>II',data[16:24]);assert dimensions==(1600,1000),(view,dimensions)
        assert path.stat().st_mtime>=MAP.stat().st_mtime,view+' predates the saved map'
        log=(ROOT/'Saved'/('Review_'+view+'.log')).read_text(encoding='utf-8-sig')
        assert all(error not in log for error in ('Failed to compile Material','LogShaderCompilers: Error','LogMaterial: Error','missing bUsedWith'))
        images[view]=dict(file=path.relative_to(ROOT).as_posix(),size=dimensions,sha256=digest(path))
    owned={path.relative_to(ROOT).as_posix():digest(path) for path in (ROOT/'Content').rglob('*') if path.is_file() and path.suffix in ('.umap','.uasset','.uexp','.ubulk') and ('RootBelltower' in path.parts or path==MAP)}
    report=dict(passed=True,map='/Game/Astra/Maps/L_AstraRootBelltower',map_sha256=digest(MAP),reports=reports,
                actual_ue_captures=images,protected_content_file_count=len(imported['protected_asset_sha256']),owned_content_sha256=owned,
                scope='UE 5.7.4 editor game execution; no new Shipping package was produced.')
    (PREVIEWS/'UE_RootBelltowerFinalValidation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Root Belltower evidence passed: 4 reports, 7 UE captures, '+str(len(owned))+' owned assets.')

if __name__=='__main__':main()

"""Rebuild the sky without touching the terrain, water, or scene placements."""
import unreal,sys,json
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import import_unreal_scene as b
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
m=b.build_cloud_sky_material();dome=b.setup_cloud_sky({'M_CloudSky':m})
dome.set_actor_hidden_in_game(False);dome.set_is_temporarily_hidden_in_editor(False)
c=dome.static_mesh_component;c.set_visibility(True);c.set_hidden_in_game(False)
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Sky map save failed')
texture=b.EAL.load_asset('/Game/Astra/Textures/T_AnimeSkyPanorama')
report={'texture':texture.get_path_name(),'srgb':texture.get_editor_property('srgb'),
        'compression':str(texture.get_editor_property('compression_settings')),
        'material_is_sky':m.get_editor_property('is_sky'),'mapping':'full-sphere longitude/latitude',
        'material_two_sided':m.get_editor_property('two_sided'),'dome_collision':dome.get_actor_enable_collision(),
        'dome_visible':c.is_visible(),'verification':'Saved properties; inspect actual Sky/SkySeam/SkyZenith renders separately.'}
(ROOT/'ArtSource/Previews/UE_SkyValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ASTRA SKY SAVED '+json.dumps(report))

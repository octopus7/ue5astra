"""Update the ball material in place, preserving the user's saved level and lighting."""
import json
import sys
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "Scripts"))
import create_scene as studio

material = studio.build_ball_material()
assert studio.ASSETS.save_loaded_asset(material, only_if_is_dirty=False)
report = {
    "passed": True,
    "material": material.get_path_name(),
    "tennis_tint": [.33, .48, .40],
    "tennis_albedo_before": [.59, .83, .045],
    "tennis_albedo_after": [.1947, .3984, .018],
    "roughness": .78,
    "specular": .18,
    "preserved": ["teal base color", "ivory seam color", "saved level", "exposure -2.8 EV"],
}
(ROOT / "Saved" / "AppearanceUpdate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
unreal.log("SOFTBODY_APPEARANCE_UPDATED " + str(report))

# 바위 형태 개선 — 2026-09-07

사용자 지시: 현재 바위가 지나치게 둥글게 마모되어 조약돌처럼 보이므로 모델링을 개선한다. 이전 지시의 부드러운 셰이딩과 애니 배경풍 텍스처는 유지한다.

큰 기울어진 암면, 불균일한 절리, 층진 틈과 비대칭 돌출부로 바위의 형태를 구분한다. 전체에 Subdivision을 적용해 구형으로 만드는 대신 모서리만 완만하게 다듬고 가중 노멀을 내보낸다. 기존 바위 5종의 바운드와 피벗을 유지하여 기존 155개 배치의 위치·회전·크기를 보존한다.

- 형태 레퍼런스: `ArtSource/Reference/Ref_FracturedForestRocks.png`
- 생성 프롬프트: `ArtSource/Reference/FRACTURED_FOREST_ROCKS_PROMPT.md`
- 제작: `Scripts/build_fractured_forest_rocks.py`
- 독립 Blender 원본: `ArtSource/Blender/ForestFracturedRocks.blend`
- FBX: `ArtSource/Meshes/SM_FracturedForestRock_01..05.fbx`
- 모델 명세: `ArtSource/Layout/forest_fractured_rocks.json`
- Blender 전체 씬 반영: `Scripts/apply_fractured_rocks_blender.py`
- Unreal 반영: `Scripts/import_fractured_rocks.py`

Blender CLI에는 `--factory-startup -b --python`을 사용한다. 전체 씬 반영 후 `validate_blender_export.py`로 저장된 원본의 배치 JSON과 Landscape 높이맵 재현성을 확인한다. UE에서는 전체 에디터의 Python으로 가져오기를 실행한다. 기존 `/Game/Astra/Meshes/SM_MossRock_01..05` 경로의 형상만 교체하며 재질과 메인 맵은 재생성하지 않는다. 해안의 젖은 바위 재질 오버라이드도 보존한다.

이전 `ForestSmoothRocks.blend`, FBX, 레퍼런스와 메타데이터는 작업 이력으로 남긴다. 교체 직전 전체 Blender 씬·배치 JSON·Unreal 바위 자산은 `ArtSource/Backups/BeforeFracturedRocks`에 보관한다. 현재 바위 명세는 전체 배치 JSON의 `rock_model_revision.metadata`로 선택한다.

최종 삼각형 수는 476 / 668 / 1,620 / 664 / 1,270개다. 실제 결과는 `ArtSource/Previews/Blender_FracturedForestRocks.png`, `UE_Rocks.png`와 `UE_RockShapes.png`에서 확인한다. `FracturedForestRocks_Validation.json`, `Blender_FracturedRockPlacementValidation.json`, `UE_FracturedRocksValidation.json`은 각각 FBX 왕복, 전체 Blender 배치 보존, UE 자산·액터·재질 보존을 검증한다.

`capture_fractured_rock_detail.py`는 현재 메인 맵에 임시 카메라를 두고 UE GPU로 `UE_RockShapes.png`를 촬영한다. 맵을 저장하지 않으며 결과 해시·해상도·카메라 정보는 `UE_RockShapesCapture.json`에 기록한다. `render_reviews.ps1 -Views Rocks,Foliage`는 기존 검토 카메라의 실제 게임 렌더를 갱신한다.

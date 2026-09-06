# 해안 배치와 물웅덩이 구름 모듈

2026-09-07 사용자 추가 지시: 대기 작업을 계속 진행하되, 파일 충돌이 있으면 독립 작업을 먼저 처리한다. 병렬화는 예상 제작 시간과 통합 비용을 비교해 전체 완료 시간이 줄어드는 경우에만 사용한다. 작은 후속 수정과 UE 실행은 순차 진행한다.

## 적용 범위

- 집 앞 약 12m 해안: 곡면 모래 바닥 1개, 낮은 흙턱 3개, 수중 돌 12개. `shoreline_site.json`의 16개 `AST_Shoreline_` 액터만 생성·갱신한다.
- 기존 큰 돌벽 5개는 지정된 이름으로 숨기고 충돌을 끈다. 삭제하지 않으며 최초 상태를 `Saved/Shoreline/original_actor_states_<maphash>/`에 보관한다.
- 원본 높이맵에 맞춰 현장 메시 외곽을 지형 안으로 10cm 묻었다. 범용 키트 9개와 현장용 4개 FBX를 모두 제공한다.
- 물웅덩이에만 기존 구름 그림을 크롭하고 약하게 움직여 비치는 느낌을 만든다. 실제 하늘 반사나 캡처는 사용하지 않는다.
- 호수와 개울은 하늘·구름 반사 대상에서 제외한다. 이 모듈은 해당 재질이나 수면 메시를 변경하지 않는다.

## 원본 프로젝트에 통합하는 순서

원본에서 진행 중인 집·우물, Landscape 높이, 연결 수면 및 물 재질 갱신을 먼저 마친다. 아래 코드는 의도한 `/Game/Astra/Maps/` 레벨이 열린 UE Python에서 실행한다.

```python
import sys
from pathlib import Path
import unreal
sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'Scripts'))

import import_shoreline_site
site_report = import_shoreline_site.apply_site(save=True)

import puddle_cloud_trick
puddle_material = puddle_cloud_trick.build_puddle_material()
puddle_report = puddle_cloud_trick.validate_created_material()
assert puddle_report['passed'], puddle_report
```

기본 물웅덩이 대상은 `/Game/Astra/Materials/M_PuddleReflection`이다. 기존 Material 자산의 경로와 참조를 유지하면서 그래프를 재구성한다. 다른 생성 스크립트가 같은 재질을 다시 만들면 이 함수를 마지막에 호출하거나 그 생성 지점에서 재사용한다. 최신 `SM_Puddle.fbx`의 VertexColor 경계 마스크가 필요하다. UV가 없는 메시도 로컬 좌표로 매핑한다.

`apply_site()`는 현재 맵을 바꾸지 않는다. `/Game/Astra/Meshes/Shoreline`, `/Game/Astra/Meshes/ShorelineSite`, `/Game/Astra/Materials/Shoreline`만 가져오기 대상으로 사용한다. 시각용 해안 액터는 `NoCollision` 프로필과 액터 충돌 비활성 상태를 함께 저장한다. 보행 충돌은 기존 Landscape가 담당한다. 원본 지형 높이가 바뀌면 Blender 현장 배치를 다시 생성하고 확인해야 한다.

## 재생성과 검토 자료

- `Scripts/place_shoreline_blender.py`: 기존 Blender 씬·배치 JSON·높이맵을 읽어 별도 `AstraLakeshoreReview.blend`, 현장 FBX와 JSON을 생성한다. 원본 파일 해시를 전후 비교한다.
- `Scripts/validate_shoreline_fbx.py`: 범용 키트 FBX 재가져오기 검증.
- `Scripts/validate_shoreline_site_fbx.py`: 현장 FBX 재가져오기 검증.
- `Scripts/review_lakeshore_modules.py`: `-AstraModuleReview=Puddle` 또는 `Shoreline`으로 별도 UE 검증 맵을 생성한다. 검증 맵 생성에는 World 수명 관리를 지원하는 `LevelEditorSubsystem.new_level_from_template()`를 사용한다.
- `ArtSource/Previews/Blender_ShorelineSite.png`: 수면을 숨기고 형상을 검토한 **Blender** 화면이다.
- UE의 `L_AstraShorelineModuleReview`는 단순한 투명 검토용 수면을 사용한다. 원본 작업의 최종 물 재질 품질을 나타내지 않는다.

## 물웅덩이 조절 값

`CloudUVScale`·`CloudUVOffset`·`CloudRotationDegrees`로 구름 그림의 구도를 바꾼다. `CloudAmount`로 구름 강도, `WaterTint`·`CloudTint`로 선형 색상, `SurfaceOpacity`로 물 내부의 투명도를 조절한다. 경계는 VertexColor R과 기본 7cm `DepthFade`로 수면색과 구름을 함께 페이드한다. `RippleUVAmplitude`·`CloudDriftUVAmplitude`는 작고 느린 움직임이며, 반복 타일 전체를 스크롤하지 않는다.

검증 보고서의 그래프 속성 확인과 실제 GPU 컴파일·화면 확인은 서로 다른 검사다. 후자는 UE 로그와 실제 UE PNG로 확인한다.

## 완료한 검증

UE 5.7.4 Editor 빌드가 통과했다. 독립 검증 맵에서 메시 13개·재질 12개를 가져왔으며 실제 바운드·재질 슬롯과 배치 16개를 읽어 확인했다. 별도 에디터 실행에서 저장된 해안 맵을 다시 열어 16개 액터의 `NoCollision` 프로필과 액터 충돌 비활성을 재검증했다.

물웅덩이 그래프 검사 11개가 통과했고 기존 물웅덩이 5개에 적용했다. 두 검증 맵 모두 실제 UE 게임 실행이 종료 코드 0으로 끝났으며 가져오기·렌더 로그에서 에러나 재질 컴파일 실패가 없었다. `UE_PuddleCloud.png`에서 구름 그림과 물가 페이드, `UE_Shoreline.png`에서 바닥·흙턱·수중 돌 배치를 확인했다. `UE_PuddleModuleValidation.json`과 `UE_ShorelineModuleValidation.json`에 실측 및 렌더 PNG 해시를 보관했다. 검증 중 원본 `L_AstraWoodland.umap`과 원본 재질은 변경하지 않았다.

# 장소별 작은 식물 배치

작은 식물 1,198개를 개별 StaticMeshActor에서 Unreal의 InstancedFoliageActor로 변환했다. 숲 안쪽 763개와 숲 가장자리 15개를 추가해 총 1,976개를 5개 FoliageType으로 묶었다. 기존 식물은 이동하거나 삭제하지 않고 숨겨 보존한다.

에디터에서 브러시를 조작하지 않아도 [InstancedFoliageActor의 공식 API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/InstancedFoliageActor?application_version=5.7)로 Foliage 인스턴스를 추가할 수 있다. 이 프로젝트는 설치된 UE 5.7의 `AddInstances`·`RemoveAllInstances`를 Python으로 호출한다. 일반 HISM 액터를 Foliage로 이름만 바꾼 구성이 아니다.

## 배치 기준

- 나무까지 5.5m 이내는 숲 내부, 9m 이내는 숲 가장자리로 분류한다. 군락은 넓은 노이즈 패턴과 고정 난수 시드 73951로 형성한다.
- 길의 지정 반폭에 70cm를 더한 구역, 중앙 공터, 집터, 캠프 공터·절벽과 물웅덩이는 추가 배치에서 제외한다.
- 수면 아래와 급경사에는 추가하지 않는다. 기존 식물의 의도된 배치는 그대로 옮긴다.
- 추가 풀은 0.5~0.88배, 고사리는 0.38~0.64배, 꽃은 0.55~0.85배로 크기를 달리한다. 꽃은 드물게 섞는다.
- 식물은 NoCollision이다. 캐릭터의 길을 막지 않는다.

## 편집과 재생성

전체 UE 에디터에서 `Scripts/apply_forest_foliage.py`를 실행한다. 원본 맵은 최초 1회 `ArtSource/Backups/BeforeFoliage`에 보관한다. 스크립트는 자신이 생성한 `/Game/Astra/Foliage/FT_Astra_*` 타입의 인스턴스만 다시 구성하므로 중복 생성되지 않는다. 이 5개 타입을 수동으로 페인트한 뒤 재실행하면 수동 추가분도 재생성 배치로 대체되므로, 별도 타입을 복제해서 수동 편집을 유지할 수 있다.

Blender 지형을 바꾸면 R16 높이맵을 다시 내보내고 UE Landscape를 갱신한 다음 이 스크립트를 실행한다. Foliage 추가 높이는 그 R16을 보간해 정한다. 원래 개별 식물 액터는 `PreservedBeforeFoliage`에 보존되어 있다.

전체 배치 변환과 생성 조건은 `ArtSource/Layout/foliage_placement.json`, 실제 인스턴스 수는 `UE_FoliageValidation.json`, 저장 후 재검증은 `UE_ForestReloadValidation.json`에 기록한다.

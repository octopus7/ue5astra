# 배치 수정 전 보관

`BeforePinkHouse_20260907_022956/L_AstraWoodland.umap`은 핑크 집을 적용하기 직전의 맵 원본이다. 현재 맵의 기존 Landscape 액터와 주변 식생도 보존했다. 숨긴 식생은 에디터의 `PreservedBeforePinkHouse` 폴더에 있다.

이 파일은 배치·지형 복원용이며 재질·메시는 같은 프로젝트의 Content 자산을 참조한다. 수정 이력 전체는 Git 커밋으로 보관한다.

`BeforeForestExpansion/`은 절벽·야영지 언덕을 만들기 전의 Blender 원본, 배치 JSON, R16 높이맵, Unreal 맵이다. 숲 확장 구역의 기존 식생은 `PreservedBeforeForestExpansion` 폴더에 숨기고 충돌을 끈 상태로 보존했다.

`BeforeSmoothRocks/`은 바위 데이터 교체 전 Blender 원본과 배치 JSON이다. `BeforeFoliage/`는 작은 식물을 Foliage 인스턴스로 전환하기 전의 UE 맵이다.

`BeforeLifeProps/`는 낚시터와 생활 소품 15종을 추가하기 전의 자료다. `AstraWoodland.blend`, `woodland_layout.json`, `landscape_height.r16`, `foliage_placement.json`, `UE_FoliageValidation.json`을 보관한다. `place_life_props.py`는 첫 실행 때만 원본을 복사하여 재실행해도 백업을 덮어쓰지 않는다. UE 적용 단계의 `import_life_props.py`도 수정 전 `L_AstraWoodland.umap`을 이 폴더에 보관한다.

생활 소품 배치에서는 Landscape 높이맵을 유지하고, 새 소품 공간과 겹치는 식생·바위는 삭제 대신 숨겨 보존한다. 제외한 Foliage 13개와 숨긴 원래 오브젝트의 기록은 `../Layout/life_props_placement.json`에 있으며, 백업의 Foliage 배치에는 적용 전 1,976개의 전체 변환이 남아 있다. 현재 배치 데이터의 1,963개와 비교하면 제외된 자리만 확인할 수 있다.

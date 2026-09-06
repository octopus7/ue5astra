# AstraLevelTest

Unreal Engine 5.7.4 프로젝트. 약 100m 숲을 탐색하는 직립 보행 삼색 고양이 게임.

실제 언리얼 실행 화면. 숲과 공터를 중심으로 호수, 개울, 나무다리와 목조 폐허가 이어진다.

![숲·공터·호수·다리·목조 폐허의 전체 배치](ArtSource/Previews/UE_Overview.png)

| 삼색 고양이와 나무다리 | 호수의 연꽃과 수초 |
| --- | --- |
| ![나무다리를 건넌 삼색 고양이](ArtSource/Previews/UE_Bridge.png) | ![연꽃과 수초가 있는 호수](ArtSource/Previews/UE_Lake.png) |

![호수 오른쪽의 핑크 지붕 집과 앞마당 우물](ArtSource/Previews/UE_House.png)

## 조작

- WASD: 화면 기준 상하좌우 이동
- 카메라: 회전 없는 고정 58도 직교 시점, 캐릭터 추적
- 마우스 입력 없음

`AstraLevelTest.uproject`를 UE 5.7로 열고 기본 맵에서 Play를 누른다. 에디터가 키보드 입력을 받도록 플레이 뷰포커스가 필요하다. 재생 중에는 WASD만 사용한다.

## 작업 자료

- `WORK_INSTRUCTIONS.md`: 사용자의 전체 작업 지시
- `ArtSource/Reference`: 전체 및 개별 모델링 참고 이미지, 생성 프롬프트
- `ArtSource/Textures`: 생성한 지면과 하늘 반사 텍스처
- `ArtSource/Blender/AstraWoodland.blend`: 모델과 전체 배치의 블렌더 원본
- `ArtSource/Meshes`: 블렌더에서 내보낸 FBX 모델
- `ArtSource/Layout/woodland_layout.json`: 블렌더에서 추출한 배치·재질·축변환 데이터
- `ArtSource/Layout/landscape_height.r16`: 실제 Landscape로 가져올 127×127 높이맵
- `ArtSource/Previews`: 블렌더 배치 렌더와 언리얼 검증 이미지

## 재생성

1. Blender 4.5 이상에서 `Scripts/build_blender_scene.py` 실행. 원본 `.blend`, FBX, JSON, 높이맵을 생성한다.
2. UE 5.7용 `AstraLevelTestEditor` 빌드.
3. **전체 언리얼 에디터**에서 `Scripts/import_unreal_scene.py` 실행. `-ExecutePythonScript=...`로도 실행할 수 있다. Content Browser를 사용하므로 UI 없는 Python commandlet로 텍스처 가져오기를 실행하지 않는다.
4. `/Game/Astra/Maps/L_AstraWoodland`를 열고 Play.

레벨 생성 스크립트는 생성된 맵을 다시 작성한다. 수동 편집을 유지하려면 다른 이름으로 복사한 맵을 사용한다. 블렌더에서 수정한 배치를 전달할 때에는 동일한 JSON 구조를 유지한다.

블렌더 원본을 열고 직접 위치·회전·크기를 변경한 뒤에는 `Scripts/export_blender_layout.py`를 실행한다. 이 스크립트는 현재 배치를 그대로 추출하며 다시 흩뿌리지 않는다. 지형은 XY 격자를 유지하고 Z 높이만 수정하면 Landscape 높이맵으로 추출된다.

## 기술 메모

지형은 일반 스태틱 메시가 아닌 Unreal Landscape이다. 오브젝트는 Blender의 미터 단위 변환을 센티미터 단위로 바꿔 배치한다. 큰 구조물에는 삼각형 충돌, 나무에는 별도의 줄기 충돌을 사용한다. 작은 장식물은 이동을 막지 않는다.

Directional Light Source Angle은 사용자 지정값인 50도이며 Exponential Height Fog를 약하게 적용했다. 호수와 개울은 겹침 없는 하나의 수면 메시를 사용한다. 버텍스 경계 마스크와 DepthFade로 가장자리를 부드럽게 하고, 최신 아트 지시대로 구름 반사 없이 맑은 청록색과 수심 차이를 표현한다.

핑크 집의 현관은 게임 카메라 쪽인 UE −X를 바라보고 우물은 앞마당에 있다. `import_pink_house_scene.py`는 기존 맵을 `ArtSource/Backups`에 보관한 뒤 배치한다. 집터의 기존 식생 22개와 줄기 충돌은 `PreservedBeforePinkHouse` 폴더에 숨겨 보존했다. `refresh_house_terrain.py`는 기존 Landscape 편집 레이어에 높이를 갱신하고 집·우물·계단 앞의 충돌 높이를 검증한다.

`ReviewCameras`의 Overview·Lake·Cabin·Puddle·House 카메라는 반복 촬영용이다. 플레이 카메라는 고양이의 카메라 하나이며, 촬영 카메라들은 일반 플레이에서 선택되지 않는다.

게임 실행 인자 `-AstraSmokeTest`는 WASD 입력 이벤트를 순서대로 주입하고, 이동 방향·접지·카메라 회전 고정을 검사한다. `-AstraReview=Overview` 등의 검토 인자는 엔진 렌더를 저장하고 해당 검토 실행을 종료한다. 일반 플레이에는 이 동작이 없다.

`Scripts/render_reviews.ps1`로 Gameplay, Overview, Lake, Cabin, Puddle 렌더를 저장한다. `-AstraBridgeTest -AstraReview=Bridge`는 정상 다리 횡단을 검사한다. 실제 결과는 [VALIDATION.md](VALIDATION.md)에 기록했다.

## 독립 호숫가 메시 키트

얕은 모래 바닥 2종, 낮은 흙 턱 3종, 수중 돌·자갈 4종을 별도 Blender 원본과 FBX로 준비했다. [메시 목록·Blender 검토 렌더·배치 기준](ArtSource/Meshes/Shoreline/README.md)에서 확인할 수 있다. 실제 게임 맵 배치와 수면 재질 통합은 아직 하지 않았다.

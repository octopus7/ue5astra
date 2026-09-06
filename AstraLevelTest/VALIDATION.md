# AstraLevelTest 검증 기록

2026-09-07, Windows / Unreal Engine 5.7.4 / Blender 4.5.12 LTS.

## 구현 상태

- 실제 Unreal Landscape: 127×127 높이 샘플, 80cm 간격, 100.8×100.8m.
- 블렌더 원본에서 28개 FBX 모델과 1,787개 배치 레코드를 추출했다. 언리얼 맵에는 충돌 보조 액터와 조명·카메라, 보존한 식생을 포함해 2,038개 액터가 있다.
- 숲·공터·호수·개울·정상 다리·무너진 다리·목조 폐허, 연꽃·수초·풀·고사리·꽃·버섯·바위·쓰러진 통나무를 배치했다.
- Directional Light의 실제 저장값: Source Angle 50°, Intensity 6. 부드러운 그림자를 위해 Virtual Shadow Maps를 사용한다.
- 호수·개울은 하나의 연결 수면으로 통합해 반투명 메시가 겹치는 자국을 제거했다. 버텍스 마스크와 DepthFade로 가장자리를 부드럽게 한다. 최신 지시대로 구름 반사를 제외한 Unlit 청록색 수면이며 수심 차이와 작은 움직이는 반짝임을 표현한다.
- Exponential Height Fog 밀도 0.001, 최대 불투명도 0.06, 시작 거리 32m. 스카이 돔의 충돌 프로필을 NoCollision으로 저장해 플레이어 이동을 방해하지 않는다.
- 분홍 지붕 집과 우물을 화면 오른쪽 호숫가에 배치했다. 현관은 UE −X로 화면을 바라본다. 원본 맵을 백업하고 기존 식생은 숨겨 보존했다.
- 기존 Landscape 액터의 기본 편집 레이어에 집터 높이를 갱신했다. 집·우물·계단 앞의 실제 충돌 높이는 98.432cm이며 맵을 닫고 다시 연 뒤에도 동일하다.
- 박스형 삼색 고양이의 두 발·팔·꼬리를 절차적으로 움직인다. WASD만 이동에 사용하고 카메라는 회전하지 않는다.

## 실행 검증

| 검사 | 결과 |
|---|---|
| AstraLevelTestEditor / Win64 / Development 빌드 | 성공 |
| 실제 에디터에서 텍스처·FBX·Landscape·맵 생성 및 저장 | 성공 |
| W/A/S/D 입력 이벤트 각각 주입 | 네 방향 모두 예상 방향으로 3.4m 이상 이동, 접지 유지 |
| 이동 중 카메라 회전 | Pitch −58°, Yaw 0° 유지, 직교 너비 3,000cm |
| 정상 나무다리 횡단 | 약 12.2m 이동, 개울 위에서 다리 충돌면에 지지됨 |
| 현재 블렌더 장면의 수동 배치 내보내기 | 1,787개 위치·자산·그룹·충돌 속성 유지, JSON과 높이맵 바이트 동일 |
| 집터 Landscape 저장·다시 열기 | 집·우물·계단 앞 충돌 높이 98.432cm 유지 |
| 실제 게임 렌더 검토 | Gameplay, Overview, Lake, House, Bridge 갱신 |

기계 판독 결과: [WASD와 카메라](ArtSource/Previews/UE_MovementValidation.json), [다리 횡단](ArtSource/Previews/UE_BridgeValidation.json), [블렌더 배치 추출](ArtSource/Previews/Blender_ExportValidation.json).

다리 입구의 초기 단차 문제는 블렌더 원본 경사로를 늘린 뒤 FBX를 다시 가져와 해결했다. 이 검증은 에디터 및 에디터의 게임 실행 모드에서 수행했다. 배포용 패키지는 이번 작업 범위에 포함하지 않았다.

## 보관 자료

생성 이미지 14장(전체 참고 2장, 개별 모델 참고 10장, 텍스처 2장)을 원본 PNG로 보관했다. [레퍼런스 목록](ArtSource/Reference/README.md)과 [생성 프롬프트](ArtSource/Reference/GENERATION_PROMPTS.md), 핑크 집 전용 프롬프트를 함께 저장했다.

아래 이미지는 생성 참고 이미지가 아닌 실제 언리얼 엔진 렌더다.

![전체 배치](ArtSource/Previews/UE_Overview.png)
![플레이 화면](ArtSource/Previews/UE_Gameplay.png)
![호수와 연꽃](ArtSource/Previews/UE_Lake.png)
![분홍 지붕 집과 우물](ArtSource/Previews/UE_House.png)
![목조 폐허](ArtSource/Previews/UE_Cabin.png)
![다리 횡단 후](ArtSource/Previews/UE_Bridge.png)

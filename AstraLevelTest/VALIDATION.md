# AstraLevelTest 검증 기록

2026-09-07, Windows / Unreal Engine 5.7.4 / Blender 4.5.12 LTS.

## 구현 상태

- 실제 Unreal Landscape: 127×127 높이 샘플, 80cm 간격, 100.8×100.8m.
- 블렌더 원본에서 41개 사용 모델과 1,805개 배치 레코드를 추출했다. 별도 해안 키트·현장 메시 13개도 통합했다. 언리얼 맵에는 충돌 보조 액터와 조명·카메라, 보존한 식생을 포함해 2,085개 액터가 있다. 작은 식물 1,198개는 숨기고 Foliage 인스턴스로 옮겼다.
- 숲·공터·호수·개울·정상 다리·무너진 다리·목조 폐허, 연꽃·수초·풀·고사리·꽃·버섯·바위·쓰러진 통나무를 배치했다.
- Directional Light의 실제 저장값: Source Angle 50°, Intensity 6. 부드러운 그림자를 위해 Virtual Shadow Maps를 사용한다.
- 호수·개울은 하나의 연결 수면으로 통합해 반투명 메시가 겹치는 자국을 제거했다. 버텍스 마스크와 DepthFade로 가장자리를 부드럽게 한다. 최신 지시대로 구름 반사를 제외한 Unlit 청록색 수면이며 수심 차이와 작은 움직이는 반짝임을 표현한다.
- Exponential Height Fog 밀도 0.001, 최대 불투명도 0.06, 시작 거리 32m. 스카이 돔의 충돌 프로필을 NoCollision으로 저장해 플레이어 이동을 방해하지 않는다.
- 분홍 지붕 집과 우물을 화면 오른쪽 호숫가에 배치했다. 현관은 UE −X로 화면을 바라본다. 원본 맵을 백업하고 기존 식생은 숨겨 보존했다.
- 기존 Landscape 액터의 기본 편집 레이어에 집터 높이를 갱신했다. 집·우물·계단 앞의 실제 충돌 높이는 98.432cm이며 맵을 닫고 다시 연 뒤에도 동일하다.
- 박스형 삼색 고양이의 두 발·팔·꼬리를 절차적으로 움직인다. WASD만 이동에 사용하고 카메라는 회전하지 않는다.
- 숲 확장 메시 13종을 독립 Blender 원본에서 제작하고 18개를 배치했다. 높이 8.035m 절벽 3종을 조립하고, 5.2m 언덕 위에 천막·화톳불·취사 장비·장작·랜턴·의자를 놓았다. 이정표는 두 곳에 배치했다.
- Landscape 높이 샘플 793개를 갱신해 캠프 언덕과 10m 진입 경사로를 만들었다. 기존 액터를 유지했으며 기존 식생 51개는 숨겨 보관하고 주변 25개는 지형 높이에 맞췄다.
- 하늘을 별도 생성한 2:1 파노라마와 경도·위도 매핑으로 바꿨다. 구면 극점·이음새를 부드럽게 합성한다. 파란 이미지가 자동으로 노멀맵 판정을 받지 않도록 sRGB 색상 텍스처로 명시한다.
- 집 앞 해안 16개 액터를 실제 메인 맵에 통합했다. 웅덩이 5개에는 스카이·주변 환경을 반사하는 Thin Translucent 재질을 적용했다. F0 0.02의 네이티브 프레넬, Lumen front-layer reflection, 부드러운 경계와 거의 투명한 바닥 투과를 사용한다. 수면에 이미지 샘플이나 Emissive 출력은 연결하지 않는다.
- 숲 바위 5종을 각 1,920삼각형의 smooth normals와 단일 생성 텍스처 재질로 교체했다. FBX custom normals를 가져왔으며 155개 기존 배치의 변환·자산 참조를 유지했다.
- 수중 바위·자갈 4종은 형상·UV·재질 슬롯을 유지하면서 smooth normals로 바꿨다. 독립 FBX 재가져오기에서 노멀 최대 오차 0.030도 이내를 확인했다.
- 네이티브 InstancedFoliageActor 1개와 FoliageType 5개로 작은 식물 1,976개를 배치했다. 기존 1,198개 전환 + 추가 778개이며 추가분은 숲 내부 763개, 숲 가장자리 15개다. 추가 식물은 길·공터·집터·캠프 동선과 급경사를 피한다.

## 실행 검증

| 검사 | 결과 |
|---|---|
| AstraLevelTestEditor / Win64 / Development 빌드 | 성공 |
| 실제 에디터에서 텍스처·FBX·Landscape·맵 생성 및 저장 | 성공 |
| W/A/S/D 입력 이벤트 각각 주입 | 네 방향 모두 예상 방향으로 2m 이상 이동, 접지 유지 |
| 이동 중 카메라 회전 | Pitch −58°, Yaw 0° 유지, 직교 너비 3,000cm |
| 정상 나무다리 횡단 | 약 12.2m 이동, 개울 위에서 다리 충돌면에 지지됨 |
| 현재 블렌더 장면의 수동 배치 내보내기 | 1,805개 위치·자산·그룹·충돌 속성 유지, JSON과 높이맵 바이트 동일 |
| 집터 Landscape 저장·다시 열기 | 집·우물·계단 앞 충돌 높이 98.432cm 유지 |
| 야영지 경사로 보행 | 약 15.3m 이동, 약 4.04m 상승, 접지 유지 |
| 부드러운 바위 가져오기 | 5종 각 1,920삼각형, 원본 바운드·155개 배치 변환 유지, custom normals 가져오기 |
| Foliage 변환·추가 | 5개 타입, 1,976개 인스턴스 실측, 원본 1,198개 식물 보관 |
| 저장된 메인 맵 다시 열기 | 숲 소품·바위·Foliage 수와 NoCollision·스카이 sRGB 색상 설정 재검증 통과 |

기계 판독 결과: [WASD와 카메라](ArtSource/Previews/UE_MovementValidation.json), [다리 횡단](ArtSource/Previews/UE_BridgeValidation.json), [블렌더 배치 추출](ArtSource/Previews/Blender_ExportValidation.json).

숲 확장 검증: [야영지 오르막](ArtSource/Previews/UE_CampMovementValidation.json), [저장 후 다시 열기](ArtSource/Previews/UE_ForestReloadValidation.json), [부드러운 바위](ArtSource/Previews/UE_SmoothRocksValidation.json), [실제 Foliage 수](ArtSource/Previews/UE_FoliageValidation.json). Foliage 재질은 인스턴스 메시용 셰이더 사용 플래그를 명시적으로 저장한다.

[최종 렌더 기록](ArtSource/Previews/UE_FinalReviewValidation.json)은 실제 UE 화면 17장의 PNG 해시·해상도, 게임 렌더 로그의 재질 컴파일/인스턴싱 사용 오류 여부, 이동 및 저장 후 검증 결과를 함께 보관한다. 생성 참고 이미지는 여기에 포함하지 않는다. 웅덩이는 메인 맵의 탑다운·낮은 시점 두 방향으로 촬영한다.

다리 입구의 초기 단차 문제는 블렌더 원본 경사로를 늘린 뒤 FBX를 다시 가져와 해결했다. 이 검증은 에디터 및 에디터의 게임 실행 모드에서 수행했다. 배포용 패키지는 이번 작업 범위에 포함하지 않았다.

## 보관 자료

생성 이미지 21장(전체 참고 2장, 개별 모델 참고 14장, 텍스처 5장)을 원본 PNG로 보관했다. [레퍼런스 목록](ArtSource/Reference/README.md)과 각 생성 프롬프트를 함께 저장했다.

아래 이미지는 생성 참고 이미지가 아닌 실제 언리얼 엔진 렌더다.

![전체 배치](ArtSource/Previews/UE_Overview.png)
![플레이 화면](ArtSource/Previews/UE_Gameplay.png)
![호수와 연꽃](ArtSource/Previews/UE_Lake.png)
![분홍 지붕 집과 우물](ArtSource/Previews/UE_House.png)
![목조 폐허](ArtSource/Previews/UE_Cabin.png)
![다리 횡단 후](ArtSource/Previews/UE_Bridge.png)

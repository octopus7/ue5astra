# Softbody — UE 5.7

3인칭 템플릿 Manny로 세 크기의 부드러운 공을 만지는 실시간 시뮬레이션.

| 공 | 지름 | 조작 |
|---|---:|---|
| 테니스공 | 6.7cm | 손을 뻗어 위에서 쥐기 |
| 두 배 크기 공 | 13.4cm | 손을 뻗어 위에서 쥐기 |
| 대형 공 | 1m | 캐릭터 몸으로 밀고 누르기 |

## 실행

- **Play.cmd**: 플레이 창 실행.
- **OpenEditor.cmd** 또는 **softbody.uproject**: UE 에디터 열기. 기본 레벨에서 Play.
- 설치 엔진: UE **5.7.4**, `C:\Program Files\Epic Games\UE_5.7`.

소스만 새로 받은 PC에서는 Visual Studio C++ 도구와 UE 5.7 설치 후 빌드한다.

```powershell
.\Scripts\run.ps1 -Mode Build
.\Scripts\run.ps1 -Mode Play
```

| 키 | 동작 |
|---|---|
| WASD / 마우스 | 이동 / 시점 회전 |
| Space | 점프 |
| E | 가까운 작은 공 위로 손 뻗기 / 상호작용 종료 |
| 마우스 왼쪽 버튼 누르고 유지 | 쥐기. 놓으면 손이 열리고 공 복원 |
| C | 손 확대 / 마네킹 전체 시점 전환 |
| Tab | 선택한 작은 공 쥐기·놓기 자동 반복 |
| R | 손 상호작용 중 해당 공 초기화; 이동 중 세 공 초기화 |

대형 청록색 공은 이동해서 몸으로 민다. 오른쪽 위에는 가까운 공의 크기·변형량·부피가 표시된다.

## 구현

- Epic UE 5.7 **Third Person 템플릿의 Manny, ABP_Unarmed, 재질**을 사용했다. 캐릭터는 네이티브 C++로 구성했다.
- 두 관절 팔 IK, 아래를 향한 손바닥, 엄지와 네 손가락의 관절을 직접 제어한다. 화면의 손 뼈에서 얻은 47개 접촉 구가 실제 공 입자를 누른다.
- 공마다 642개 물리 입자와 1,280개 삼각형으로 구성된 **CPU XPBD 소프트바디 솔버**를 쓴다. 거리 제약, 부피 보존, 접촉, 중력과 감쇠를 120Hz로 계산한다.
- 렌더링 표면은 물리 입자 변위를 보간한 20,480개 삼각형이다. 테니스공의 흰 곡선도 변형을 따라간다.
- 대형 공은 Chaos 강체 코어와 변형 표면을 결합했다. 캐릭터 몸통 캡슐이 표면을 누르고 코어를 민다.

작은 공은 받침대에 고정된다. 대형 공은 이동·충돌하며, 바닥 제약을 수평으로 유지하도록 강체 회전은 잠겨 있다. Chaos Flesh 에셋이나 실제 테니스공의 재료 계수를 사용하는 정밀 FEM 해석은 아니다.

## 검증 및 재생성

```powershell
.\Scripts\run.ps1 -Mode Test       # 솔버 자동 테스트 4개
.\Scripts\run.ps1 -Mode Scene      # 저장된 레벨과 재질 재생성
.\Scripts\run.ps1 -Mode Appearance # 공의 재질만 갱신
.\Scripts\run.ps1 -Mode Validate   # 실제 엔진 렌더링, 접촉/복원/이동 검사
.\Scripts\run.ps1 -Mode Demo       # 반복 쥐기 실행
```

검증 수치는 `Docs/Validation.json`, 실제 UE 화면은 `Previews/`에 있다. 실행 로그와 새 보고서는 `Saved/`에 생성된다. 레벨 생성 스크립트는 `/Game/Softbody`의 생성 에셋과 생성 태그가 있는 액터를 갱신한다.

핵심 파일: `Source/Softbody/SoftBodySolver.cpp`, `SoftBodyBall.cpp`, `SoftbodyCharacter.cpp`, `SoftbodyGameMode.cpp`, `Scripts/create_scene.py`.

공의 표면은 진한 황록색과 무광 재질로 보정했다. `M_Ball`의 `TennisTint` 파라미터가 테니스공 색을 조절한다. 보정값·비교 화면은 `Docs/Appearance.md`를 참고한다.

엔진 API 참고: [PoseableMeshComponent](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/Components/UPoseableMeshComponent), [ProceduralMeshComponent](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/ProceduralMeshComponent/UProceduralMeshComponent).

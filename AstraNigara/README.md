# AstraNigara

UE 5.7 Niagara 테스트용 프로젝트.

## 애니풍 작은 폭포

`L_AnimeWaterfall`은 Blender로 모델링한 2.2m 폭포와 3.6m 물웅덩이 쇼케이스다.
수직 메시의 UV 흐름과 Niagara 파문·물방울·안개·거품을 조합했다.
[에셋 구성, 조절 및 Blender 원본](Docs/AnimeWaterfall.md).

## 폭발 규모 비교

`L_ExplosionScaleShowcase`에서 1m / 3m / 10m 받침대와 1m 격자를 기준으로
소규모·중규모·대규모 효과를 비교한다. 중규모·대규모는 각각 일회성과
반복 재생 시스템을 포함한다. [에셋 경로, 설정 및 재생성](Docs/ExplosionVariants.md).

## 소규모 파괴 쇼케이스

`L_SmallDestructionShowcase`는 지름 100cm 받침대와 10cm 바닥·배경 격자를 기준으로 작은 파괴 효과를 확인하는 맵이다.

- `VFX/SmallDestruction/NS_SmallDestruction`: 일회성 효과.
- `VFX/SmallDestruction/NS_SmallDestruction_Showcase`: 동일한 구성으로 2초마다 반복.
- 파편, 화염, 연기, 열 왜곡을 각각 독립 이미터로 구성.
- 파편 22개는 볼트·너트·스프링·기어·와셔·샤프트 커플러 6종 메시를 무작위로 사용한다. [부품 원본과 재생성](ArtSource/MechanicalParts/README.md).
- 부품마다 LOD0/1/2를 생성하고 화면 크기에 따라 자동 선택한다. LOD1/2 삼각형 목표는 원본의 50%/20%다.
- [효과 구성과 제한](Docs/SmallDestruction.md), [에디터 상태와 화면 점검](Docs/EditorStatus.md).

처음 체크아웃한 PC에서는 Visual Studio 2022 C++ 도구와 UE 5.7로 에디터 전용 모듈을 빌드한다. 생성된 Niagara 에셋 자체는 엔진 기본 모듈만 사용한다.

```powershell
.\Scripts\build_tools.ps1
.\Scripts\open_showcase.ps1
.\Scripts\check_editor.ps1
.\Scripts\check_editor.ps1 -Screenshot -NiagaraAgeSeconds 0.15 -WaitSeconds 50
```

열린 에디터에서는 `.\Scripts\check_editor.ps1 -RebuildAssets -WaitSeconds 60`으로 에셋을 재생성한다. 에디터를 닫은 상태에서는 `.\Scripts\open_showcase.ps1 -RebuildAssets`를 사용한다. 재생성은 작은 파괴 에셋과 `SD_` 접두사 액터의 편집을 덮어쓴다. 프로젝트를 열면 로컬 상태 점검기가 자동으로 시작된다.

## 최초 분수 예제

1. `AstraNigara.uproject`를 UE 5.7로 연다.
2. `Content/Maps/L_Showcase`를 열고 Play 또는 Simulate를 실행한다.
3. 받침대 위에서 분수 형태로 반복 방출되는 스프라이트 파티클을 확인한다.
4. `Content/VFX/NS_SimpleFountain`을 열어 이미터를 편집한다.

UE 내장 `FountainLightweight` 템플릿을 복제한 Niagara System이며, 시스템 안에 단일 Lightweight 이미터가 포함된다. 별도 NE 에셋은 없다. 바닥, 받침대, 조명, 시작 위치 및 자동 활성화 카메라를 포함한다. 엔진 기본 메시와 Niagara 플러그인 콘텐츠를 참조한다.

## 재생성 및 검증

아래 명령은 프로젝트 폴더에서 PowerShell로 실행한다. 재생성은 쇼케이스 레벨 배치를 덮어쓰므로 편집 내용을 먼저 저장/백업한다.

```powershell
$editor = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$project = Join-Path $PWD 'AstraNigara.uproject'
& $editor $project "-ExecutePythonScript=$PWD\Scripts\build_showcase.py" -unattended -RenderOffscreen -d3d11 -DDC=NoZenLocalFallback "-LocalDataCachePath=$PWD\DerivedDataCache"
& $editor $project "-ExecutePythonScript=$PWD\Scripts\validate_showcase.py" -unattended -nullrhi -DDC=NoZenLocalFallback "-LocalDataCachePath=$PWD\DerivedDataCache"
```

검증 스크립트는 저장된 맵/시스템 재로드, Niagara 액터 1개, 자동 활성화 상태, 시스템 연결, 카메라 및 무대 메시 2개를 검사한다. `-nullrhi` 검증은 GPU 파티클의 화면 출력을 검증하지 않는다.

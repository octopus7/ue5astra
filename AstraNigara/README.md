# AstraNigara

UE 5.7 Niagara 테스트용 프로젝트.

1. `AstraNigara.uproject`를 UE 5.7로 연다.
2. 기본 레벨 `Content/Maps/L_Showcase`에서 Play 또는 Simulate를 실행한다.
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

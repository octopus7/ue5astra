# Windows x64 패키지

`Scripts/package_windows.ps1`로 UE 5.7의 Shipping 빌드·쿠킹·패키징을 실행한다. 기본 출력은 저장소의 `Builds/AstraLevelTest_Win64/Windows`이며 `AstraLevelTest.exe`와 전체 하위 폴더를 함께 배포한다.

| 실행 파일 | 출력 | 내부 렌더링 | 업스케일러 |
| --- | --- | --- | --- |
| `AstraLevelTest.exe` / `Play_4K_DLSS.cmd` | 3840×2160 | 1920×1080 | NVIDIA DLSS Performance |
| `Play_1080p_Native.cmd` | 1920×1080 | 1920×1080 | 네이티브 |
| `Play_4K_Native.cmd` | 3840×2160 | 3840×2160 | 네이티브 |

DLSS 지원 여부를 실행 시 검사하고 지원하지 않으면 1080p 네이티브로 실행한다. 동적 해상도는 끈다. P 데모 영상 모드와 WASD 조작은 패키지에서도 동일하다. Alt+F4로 종료한다.

## 빌드 환경

- Unreal Engine 5.7.4, Visual Studio 2022 C++ 도구, Windows SDK.
- `Engine/Plugins/Marketplace/DLSS`에 UE 5.7용 NVIDIA DLSS 플러그인 필요. 현재 설치 버전은 `8.6.0-NGX310.6.0`이며 자동 의존 플러그인 `StreamlineNGXCommon`을 사용한다.
- 프로젝트는 Windows x64 / DX12 / Shader Model 6으로 패키징한다.
- NVIDIA의 [공식 DLSS 페이지](https://developer.nvidia.com/rtx/dlss)에서 UE 5.7용 플러그인을 받을 수 있다.
- 필수 런타임 설치 파일 `Engine/Extras/Redist/en-us/vc_redist.x64.exe`를 함께 포함한다.

## 설정과 검증

실행 인수 `-AstraRenderProfile=DLSS4K`, `Native1080`, `Native4K`로 프로필을 선택한다. `-ResX`와 `-ResY`를 명시하면 창 해상도를 지정할 수 있다. 실제 적용 상태는 게임의 `Saved/GraphicsSettings.json`에 기록한다.

`-AstraGraphicsTest`는 실제 렌더링 프레임에서 출력 크기·내부 크기·사용된 temporal upscaler 이름을 읽어 `Saved/GraphicsValidation.json`과 화면을 저장하고 성공/실패 종료 코드를 반환한다. 단순 플러그인 활성 플래그와 실제 렌더링 결과를 구분해 확인한다. `-AstraDemoTest`는 P 입력·7개 촬영 컷·원래 상태 복원·WASD를 검사한다.

저장소 루트에서 실행한다:

```powershell
./AstraLevelTest/Scripts/package_windows.ps1
./AstraLevelTest/Scripts/validate_windows_package.ps1
```

`-SkipEditorBuild`는 이미 필요한 에디터 모듈을 빌드해 둔 상태에서만 사용한다. 현재 패키지는 열린 에디터의 DLL 잠금을 피하기 위해 이 옵션으로 생성했으며, 게임용 Shipping 실행 파일은 새 코드를 빌드했다. 이번 변경은 런타임 설정이며 쿠킹에 필요한 에디터 자산 구조는 바꾸지 않았다.

2026-09-07 RTX 4060에서 세 그래픽 프로필과 최상위 기본 실행 파일, P 데모 전체를 검증했다. [실측 결과](../VALIDATION.md#windows-x64-패키지와-dlss--2026-09-07)를 참고한다. 배포 ZIP `Builds/AstraLevelTest_Win64_DLSS.zip`에는 실행에 필요한 전체 폴더와 세 실행 옵션을 포함한다.

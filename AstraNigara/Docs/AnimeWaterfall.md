# 작은 애니풍 폭포

`/Game/Maps/L_AnimeWaterfall`을 열고 Play로 재생한다. `WF_ShowcaseCamera`가 자동 활성화된다.
에디터에서도 Realtime을 켜면 물줄기 UV와 Niagara가 계속 움직인다.

## 구성

높이 약 2.2m의 굽은 수직 물줄기, 폭 약 3.6m의 타원형 물웅덩이,
이끼 낀 바위·고사리·풀·관목을 부드러운 청록/녹색 팔레트로 구성했다.
스타일은 단순화된 면과 수채화 배경을 참고한 색감이다. 외부 다운로드 에셋은 사용하지 않았다.

| 에셋 | 역할 |
|---|---|
| `VFX/Waterfall/NS_AnimeWaterfall` | 낙수 지점의 계속 방출되는 Niagara Lightweight 시스템 |
| `Meshes/SM_WF_WaterCurtain` | Blender 원본, 888삼각형, 곡면 크레스트와 수직 흐름용 UV0 |
| `Meshes/SM_WF_UpperStream` | 192삼각형, 커튼과 같은 경계 정점·UV를 공유하는 윗물길 |
| `Meshes/SM_WF_Pool` | 576삼각형, 평면 UV0 수면 |
| `Meshes/SM_WF_RippleRing` | 128삼각형의 굴곡진 수평 링, Niagara에서 얇고 끊어진 호로 표현 |
| `Meshes/SM_WF_ImpactApron` | 640삼각형의 낮은 곡면, 낙수 끝에서 수면 앞으로 퍼지는 포말 받침 |
| `Materials/M_WF_Waterfall_UV` | Time과 UV를 이용한 하향 흐름, 흰 줄무늬와 낙수 끝의 포말 색 |
| `Materials/M_WF_ImpactFoam` | 흐르며 갈라지는 포말 무늬와 불규칙하게 사라지는 외곽 |
| `Materials/M_WF_Pool` | 움직이는 수면 무늬, 잔광, 얕은 가장자리 색 |

위 표의 Meshes/Materials 경로는 `/Game/VFX/Waterfall/` 아래다.
8종 배경·수면 메시의 원본 합계는 9,114삼각형이며, Niagara 파문 링은 입자마다 별도다.
Nanite나 자동 LOD에 의존하지 않는 낮은 폴리곤 수로 제작했다.

| 이미터 | 방출량/초 | 수명 | 동작 |
|---|---:|---:|---|
| Ripples | 3.2 | 1.15–2.10초 | 분산된 중심에서 커지며 수면 앞으로 흐르는 불규칙한 호 |
| Splash | 92 | 0.32–0.62초 | 낙수 폭 전체에서 짧게 튀는 길쭉한 물방울 |
| Mist | 16 | 0.75–1.35초 | 충돌선에 넓게 퍼져 떠오르는 옅은 물안개 |
| Foam | 30 | 0.85–1.55초 | 수면 방향을 유지하며 앞으로 흘러가는 불규칙한 거품 조각 |

낙수 메시의 끝은 수면 아래까지 이어진다. 그 위에 곡면 포말과 물방울·물안개를 겹쳐
수직 물줄기가 수면과 만나는 부분을 연결한다. 포말은 낙수 부근에 모이고,
앞으로 퍼질수록 무늬와 외곽이 갈라지며 투명해지도록 구성했다.

파문은 위치·수명·XY 크기를 입자마다 다르게 정하고, 수평을 유지한 채 Z축으로만 회전한다.
링 자체의 완만한 굴곡, 입자별 위상이 다른 끊김, 불균일한 띠 폭을 함께 사용한다.
확장 속도는 수명에 따라 느려지며, 약한 전방 이동과 소멸 곡선을 더해
같은 중심에서 일정한 간격으로 생기는 동심원 반복을 줄인다.

## 조절과 재사용

### 재사용 Blueprint 에셋

`/Game/VFX/Waterfall/Blueprints/BP_AnimeWaterfall`은 콘텐츠 브라우저에 저장된 Actor Blueprint다.
레벨에는 기존 폭포 액터 4개 대신 `WF_AnimeWaterfall` 인스턴스 하나가 배치된다.
기본 Scene Root 아래 `UpperStream`, `WaterCurtain`, `ImpactApron` Static Mesh Component와
`ImpactNiagara` Niagara Component를 포함한다. BP를 이동·회전하면 네 요소가 함께 이동한다.
현재의 낮은 물보라와 기존 상대 배치를 유지하며, 물웅덩이·바위·풀·카메라는 포함하지 않는다.

다른 프로젝트로 옮길 때:

1. 콘텐츠 브라우저에서 `BP_AnimeWaterfall`을 우클릭 → **Asset Actions → Migrate**.
2. 의존성 목록의 체크를 유지하고 대상 프로젝트의 **Content** 폴더를 선택한다.
3. UE 5.7 호환 프로젝트에서 Niagara 플러그인을 활성화하고 BP를 레벨에 드래그한다.

프로젝트 콘텐츠 의존성은 BP 1개, 메시 4개(파문 링 포함), 머티리얼 6개, Niagara System 1개다.
엔진 Niagara 콘텐츠도 참조한다. 대상 프로젝트에 `AstraNigaraTools`, Python 생성 스크립트,
Blender 원본은 필요하지 않다. BP 파일 하나만 탐색기로 복사하면 의존성이 누락되므로 Migrate를 사용한다.
수면은 대상 레벨에 별도로 배치한다. 기존 키트 원점 기준 수면 높이는 Z=5cm다.
입자 움직임은 기존 Niagara 공간 설정을 유지하므로 이동 중인 폭포를 위한 추적 효과로 검증한 것은 아니다.

생성 스크립트는 `Scripts/build_waterfall_blueprint.py`, 검증 보고서는
`Saved/waterfall_blueprint_report.json`이다. 변환 전 맵 사본은 `Saved/WaterfallBlueprintBackup/`에 보관한다.
이미 BP가 있는 경우 `build_waterfall.py` 전체 재생성 후에도 다시 BP로 묶는다.

`M_WF_Waterfall_UV`에서 Material Instance를 만들고 `FlowSpeed`를 조절한다(기본 0.85).
양수는 아래로 흐른다. Blender UV의 V는 접합부0→아래1이며 윗물길은 음수 V로 이어진다.
UV는 중심선을 따라 흐르는 거리로 계산하고, 두 메시의 경계 정점 13개는 위치와 UV가 같다.
윗물길과 낙수 사이에는 부드러운 곡면을 사용하며, 꺾이는 부분에만 약한 포말 띠를 더한다.
UE FBX 임포터가 V를 뒤집으므로
머티리얼에서 `(1 - UV.y) - Time * FlowSpeed`로 보정한다.
수직 메시와 윗물길은 같은 머티리얼을 공유한다.

Niagara의 Spawn Rate와 Initialize Particle에서 각 층의 밀도·크기·수명을 바꿀 수 있다.
Ripples의 Scale Mesh Size와 Scale Color 곡선이 파문의 확장과 소멸을 제어한다.
Initialize Particle의 Mesh Scale은 XY 비율, Initial Position은 발생 범위를 제어한다.
Initial Mesh Orientation은 None 모드에서 Rotation의 Z만 0–360도로 분산한다.
Random 모드는 모든 축을 회전하므로 수평 파문에 사용하지 않는다.
입자 색의 RGB는 머티리얼 무늬의 고정 난수 위상으로 사용하고, A는 소멸을 제어한다.
파문은 실제 수평 메시이며 카메라를 따라 회전하지 않는다.

Blender에서 내보낸 배경 메시들은 모두 같은 원점을 사용한다. 장면 전체를 다른 레벨로 옮길 때
`WF_AnimeWaterfall`, `WF_Pool`, `WF_Rockwork`, `WF_Moss`, `WF_Ground`,
`WF_Foliage`와 추가 풀을 관리하는 `InstancedFoliageActor`를 함께 고려한다.
Niagara 위치는 현재 원점 기준 `(0,-33,9)`cm이다.
배경·카메라·노출 액터는 쇼케이스용이다.

수면은 불투명한 스타일라이즈드 셰이더다. 유체 시뮬레이션, 실제 굴절, 입자 충돌,
수영/보행 충돌과 물소리는 포함하지 않는다. 물방울은 충돌 처리 없이 수명으로 소멸한다.

## 원본과 재생성

- Blender 원본: `ArtSource/Waterfall/AnimeWaterfall.blend`
- FBX: `ArtSource/Waterfall/FBX/`
- Blender 생성 스크립트: `Scripts/build_waterfall_blender.py`
- UE 생성 스크립트: `Scripts/build_waterfall.py`
- UE 통합 검증: `Scripts/validate_waterfall.py`
- 두 물길의 공통 형상: `Scripts/waterfall_flow_geometry.py`
- 기존 Blender에서 물길만 갱신: `Scripts/update_waterfall_crest_blender.py`
- UE 물길 메시·머티리얼만 갱신: `Scripts/update_waterfall_crest.py`

Blender 4.5에서 `--background --factory-startup --python`으로 모델링 스크립트를 실행한다.
UE 에디터 콘솔에서는 `py "D:/github/ue5astra/AstraNigara/Scripts/build_waterfall.py"`를 실행한다.
재생성은 위의 생성 대상 메시·머티리얼·시스템과 `WF_` 액터 설정을 갱신한다.
수동 수정이 있으면 먼저 별도 복제한다.

생성 뒤 `NS_AnimeWaterfall`을 열어 **Compile → Save**한다.
처음 생성하는 경우 원본 복제 이미터 이름 Debris/Flame/Smoke/Distortion을
Ripples/Splash/Mist/Foam으로 바꾼다. 기존 저장 에셋은 이름 정리가 완료되어 있다.
검증 스크립트는 UV 채널·크기·머티리얼 참조·방출률·확장 곡선·수평 방향·실행 상태를 검사하며
`Saved/waterfall_validation.json`에 결과를 기록한다.

`Scripts/check_editor.ps1 -Screenshot -NiagaraAgeSeconds 1.6`으로 실제 UE 렌더를 캡처할 수 있다.
Blender 렌더는 `Docs/Previews/Waterfall_Blender.png`, UE 렌더는 `Docs/Previews/Waterfall_UE.png`다.
접합부 개선 후 Niagara 1.6초와 2.8초 시점의 UE 렌더를 확인했다.
2.8초 캡처는 `Docs/Previews/Waterfall_UE_Impact_Late.png`다.
통합 검증은 메시 12종과 이미터 4종을 통과했으며, 회전 모드 None과 Z축 범위는 Niagara 편집 화면에서도 확인했다.

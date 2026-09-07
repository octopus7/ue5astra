# 별이 잠긴 연못 — Astra Star Pond

낮빛이 드는 숲 안에서 연못에만 밤하늘이 펼쳐지는 약 100.8×100.8m 독립 레벨이다. 연못 둘레 산책로가 별자리 관측대, 초승달 석문, 버드나무와 은백색 연꽃 군락, 뿔 달린 코끼리의 쉼터를 연결한다.

- 맵: `/Game/Astra/Maps/L_AstraStarPond`
- 관측대에 가까이 서면 물속 여섯 별이 연결된다. 멀어지면 연결선이 서서히 사라진다.
- 수면은 이 장소만 사용하는 밤하늘·별자리 머터리얼이다. 기존 하늘과 물웅덩이 머터리얼은 재사용 상태를 보존한다.
- 기존 WASD 삼색 고양이와 회전 없는 탑다운 카메라를 사용한다. P 키 데모는 이 맵 전용 일곱 동선을 보여준다.
- 깊은 연못 둘레에는 투명한 Pawn 전용 충돌 경계가 있어 캐릭터가 깊은 물에 들어가지 않는다.

## 코끼리 제작 방향

최신 사용자 수정: 사실적인 피부를 없애고 매끈한 동화풍으로 제작한다. 머리와 몸통이 자연스럽게 한 덩어리로 이어지며 앞뒤로 약 30% 더 긴 통통한 타원형이다. 작은 발, 짧게 말린 코, 둥근 귀, 이마의 나선형 뿔과 연보라색 피부를 사용한다.

실제 스켈레톤 16본과 가중치가 적용된 `SK_SP_UnicornElephant`에 8초 반복 아이들 `A_SP_UnicornElephant_Idle`을 넣는다. 몸통 호흡, 귀·코·꼬리 움직임과 눈깜빡임이 포함되고 루트와 발은 제자리에 유지한다. 애니메이션 재생 상태는 SkeletalMeshComponent의 `override_animation_data`로 맵에 저장한다.

완성 자산은 `/Game/Astra/Characters/StarPond/Guardian`에 있다. FBX 재임포트 시 저장된 애니메이션 가져오기 설정까지 축 변환에 맞추고, 정지한 Root의 241개 키를 메시 기준 포즈에 맞춘다. 모든 자식 본의 모션 보존과 16본 기준 포즈 일치를 검사한다. 이 보정은 `import_starpond_elephant.py`에 포함되어 전체 재생성 때도 적용된다.

![실제 UE 코끼리 아이들 화면](../ArtSource/Previews/UE_SPElephant.png)

## 원본과 재생성

1. `ArtSource/Reference/StarPond`에 전체·유적·식물·코끼리 레퍼런스와 `GENERATION_PROMPTS.md`를 보존한다. 현재 코끼리 기준은 `Ref_StarPondElephantOval.png`다. 앞선 두 버전은 이력이다. 이미지 생성은 내장 image_gen을 사용했다.
2. Blender 4.5에서 `Scripts/build_starpond_ruins.py`, `build_starpond_botany.py`, `build_starpond_elephant.py`를 실행한다. 각 `.blend`, FBX, 자산 명세와 실제 검토 렌더를 만든다.
   코끼리 제작 후 `Scripts/export_starpond_elephant_ue.py`를 실행한다. 미터 단위 `.blend`와 원본 FBX를 보존하고, 메시·본 좌표를 센티미터로 변환한 `SK_SP_UnicornElephant_UE.fbx`를 별도로 생성한다. UE에서는 이 파일을 배율 1로 임포트한다.
3. `Scripts/build_starpond_scene.py`로 `ArtSource/Blender/AstraStarPond.blend` 전체 배치, `starpond_layout.json`, 127×127 `starpond_height.r16`과 지형 셰이더를 추출한다.
4. UE 모듈을 빌드한 뒤 전체 에디터의 `-ExecutePythonScript=.../Scripts/import_starpond_level.py`로 전용 자산과 Landscape, Foliage, 스켈레탈 코끼리를 적용하고 맵을 저장한다.
5. `Scripts/validate_starpond_level.py`로 저장된 맵을 다시 열어 메시·변환·Foliage·지형·애니메이션을 검증한다. `-AstraStarPondTest` 게임 실행은 실제 WASD 입력·관측대 반응·물 경계 충돌·스켈레탈 움직임을 검사한다.
6. `Scripts/validate_starpond_all.ps1`로 저장된 맵 검사, 실제 게임 입력·아이들 검사, P 데모 일곱 동선 검사와 실제 UE 화면 일곱 장 촬영을 순차 실행한다. 생성 참고 이미지는 실제 엔진 결과와 구별하여 보관한다.

전체 모델링 라이브러리와 FBX 원본은 `ArtSource/Blender` 및 `ArtSource/Meshes/StarPond`, 자산·배치는 `ArtSource/Layout/starpond_*.json`에 저장된다. 수면 생성 텍스처는 `ArtSource/Textures/StarPond/T_SP_SubmergedStars.png`다.

## 검증 기록

개별 Blender 검증 JSON은 `ArtSource/Previews/*StarPond*Validation.json`에 보관한다. 실제 엔진 통합·재열기·플레이 검증은 실행 후 같은 폴더의 `UE_StarPond*.json`에 기록한다. 작업 완료 여부는 실제 검증 결과를 기준으로 갱신한다.

- 배치 4,815개: 정적 액터 388개와 실제 Foliage 인스턴스 4,427개. 새 정적 메시 9종, 재사용 메시 16종과 별도 스켈레탈 코끼리다.
- 저장된 맵을 새 에디터에서 다시 열어 5,321개 항목을 통과했다. 실제 Landscape 높이 15,625지점, Foliage 일대일 변환, 메시·충돌·물 경계·저장된 아이들·16본 기준 포즈를 포함한다.
- 실제 게임 입력 14개 검사 통과: WASD 각 방향 1.54~1.61m 이동, 관측대 별자리 연결·해제, 깊은 물 진입 방지, 코끼리 본 모션과 발 고정. 발의 최대 이동 오차는 0cm였다.
- P 데모는 월드 시간 72.923초에 7개 경로를 완료했다. 반복, P 복귀, 재진입 직후 취소, 카메라·위치·이동 상태 복원과 복귀 후 WASD를 통과했다. 석문 계단을 내려오는 짧은 0.077초를 제외한 나머지 동선의 비접지 시간은 0초였고 모든 동선은 접지 상태로 끝났다.
- `Scripts/verify_starpond_results.py`는 보고서·맵의 최신성, 기존 Content 해시와 실제 렌더 7장의 크기·셰이더 로그를 확인하고 `UE_StarPondFinalValidation.json`에 해시를 보관한다.
- 검증 범위는 UE 5.7.4 에디터의 게임 실행이다. 앞서 만든 Shipping 패키지에는 이 새 레벨이 아직 포함되지 않는다.

석문의 Blender 원본은 22,728개 면이며, 0.02mm² 미만의 베벨 조각 8개를 포함한다. UE FBX 가져오기 후 22,727개 면이 남았다. `inspect_starpond_gate.py`와 `StarPondGate_TopologyInspection.json`에 원본 측정값을 보존한다. 검증은 이 측정 범위 안의 미세 면 정리를 허용하며, 크기·노멀·UV·재질과 통행 검사를 별도로 유지한다.

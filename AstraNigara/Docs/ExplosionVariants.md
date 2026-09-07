# 중규모·대규모 폭발

`/Game/Maps/L_ExplosionScaleShowcase`에서 소규모, 중규모, 대규모를 비교한다.
바닥 격자는 1m, 원형 받침대 지름은 각각 1m / 3m / 10m다.
3m와 10m는 연출 규모의 기준이며 게임플레이 피해 반경이 아니다.

| 설정 | 중규모 | 대규모 |
| --- | --- | --- |
| 일회성 에셋 | `NS_MediumExplosion` | `NS_LargeExplosion` |
| 반복 에셋 | `NS_MediumExplosion_Showcase` | `NS_LargeExplosion_Showcase` |
| 반복 간격 | 4초 | 6초 |
| 파편 / 화염 / 연기 / 왜곡 개수 | 52 / 26 / 32 / 3 | 104 / 48 / 64 / 4 |
| 파편 수명 | 0.60–0.85초 | 1.0–1.4초 |
| 화염 수명 | 0.28–0.48초 | 0.45–0.75초 |
| 연기 시작 지연 | 0.18초 | 0.32초 |
| 연기 수명 | 1.5–2.2초 | 2.8–4.2초 |
| 표시 경계 반경 (각 축) | 220cm | 650cm |

에셋 위치는 `/Game/VFX/Explosions`다. 네 효과층은 독립 Lightweight
이미터다. 액터 스케일은 1이며 크기·속도·수명·생성 수를 에셋 내부에서
각각 조정했다. 초기 섬광 이후 연기가 들어오도록 시간차를 두었다.

파편은 기존 볼트·너트·스프링·기어·와셔·샤프트 커플러 메시를 사용한다.
세 단계 LOD와 Niagara `ComponentOrigin` 선택을 유지한다. 대규모라도
부품 메시 전체를 10배 키우지 않고 파편 수와 퍼지는 속도를 늘렸다.

실제 Chaos 파괴, 바닥 충돌, 피해 판정, 음향은 포함하지 않는다. 파편은
중력을 받는 시각 효과이며 수명 종료 시 사라진다. 화염·연기는 절차적
스프라이트를 사용한다. 반투명 연기와 열 왜곡의 GPU 비용은 적용할 씬과
해상도에서 따로 프로파일링해야 한다.

## 재생성 및 점검

열린 UE 5.7 에디터의 Cmd 입력란에서 프로젝트의 절대 경로를 사용한다.

```text
py "D:/github/ue5astra/AstraNigara/Scripts/build_explosion_variants.py"
py "D:/github/ue5astra/AstraNigara/Scripts/validate_explosion_variants.py"
```

생성 스크립트는 기존 소규모 쇼케이스 시스템을 복제한다. 기존 소규모
에셋의 모듈을 수정하지 않는다. 재실행하면 위 네 폭발 에셋, 전용 무대
머티리얼, 비교 레벨의 `EX_` 액터 속성을 갱신한다. 다른 레벨로 전환하기
전에 현재 레벨을 저장한다. 비교 레벨의 사용자 추가 액터는 유지한다.

검증은 네 시스템의 유효성·반복 동작·방출 개수·연기 타이밍·머티리얼·
메시 LOD 및 비교 레벨 연결을 검사한다. 결과는 `Saved/` 아래의
`explosion_variants_report.json`, `explosion_variants_validation.json`에 남는다.
화면 검사는 기존 `Scripts/check_editor.ps1 -Screenshot -NiagaraAgeSeconds`
기능으로 폭발 직후와 연기 단계를 각각 확인할 수 있다.

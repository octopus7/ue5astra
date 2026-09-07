# AstraLevelTest

UE 5.7.4에서 실행하는 약 100×100m 숲 탐색 프로젝트. 박스 형태의 삼색 고양이를 WASD로 움직이고 고정 탑다운 카메라가 따라간다.

실제 언리얼 실행 화면. 숲과 공터를 중심으로 호수, 개울, 나무다리와 목조 폐허가 이어진다.

![숲·공터·호수·다리·목조 폐허의 전체 배치](AstraLevelTest/ArtSource/Previews/UE_Overview.png)

낚시터와 집 주변에는 잠시 사람이 자리를 비운 듯한 생활 소품을 더했다. 나무 데크 위의 낚시 자리, 작은 텃밭과 빨랫줄, 공터의 피크닉, 무너진 다리 옆의 수리 도구가 각 장소의 용도를 보여준다.

| 호수의 나무 낚시터 | 핑크 집 앞의 생활 공간 |
| --- | --- |
| ![나무 낚시 데크와 낚싯대·의자·양동이](AstraLevelTest/ArtSource/Previews/UE_Fishing.png) | ![빨랫줄·텃밭·장화와 손수레](AstraLevelTest/ArtSource/Previews/UE_HomeLife.png) |

| 나무 그늘의 피크닉 | 무너진 다리의 수리 자리 |
| --- | --- |
| ![체크 담요와 먹거리·채집 바구니](AstraLevelTest/ArtSource/Previews/UE_Picnic.png) | ![새 판자·공구 상자·밧줄](AstraLevelTest/ArtSource/Previews/UE_Repair.png) |

| 삼색 고양이와 나무다리 | 호수의 연꽃과 수초 |
| --- | --- |
| ![나무다리를 건넌 삼색 고양이](AstraLevelTest/ArtSource/Previews/UE_Bridge.png) | ![연꽃과 수초가 있는 호수](AstraLevelTest/ArtSource/Previews/UE_Lake.png) |

![호수 오른쪽의 핑크 지붕 집과 앞마당 우물](AstraLevelTest/ArtSource/Previews/UE_House.png)

![돌 절벽 위의 천막과 화톳불 야영지](AstraLevelTest/ArtSource/Previews/UE_Camp.png)

![부드러운 바위와 장소별 밀도를 적용한 Foliage](AstraLevelTest/ArtSource/Previews/UE_Foliage.png)

Blender 배치 원본에는 메시 정의 56종과 배치 기록 1,820개가 있다. 작은 식물은 생활 소품과 겹치는 자리만 비워 Foliage 배치 데이터 1,963개를 유지한다. 새 낚시터·생활 소품 15종의 원본과 재생성 방법은 [프로젝트 안내](AstraLevelTest/README.md#낚시터와-생활-소품)에 정리했다. 엔진 적용·이동 검증 상태는 검증 문서를 기준으로 확인한다.

- [프로젝트 안내와 실행 방법](AstraLevelTest/README.md)
- [사용자 작업 지시](AstraLevelTest/WORK_INSTRUCTIONS.md)
- [검증 결과](AstraLevelTest/VALIDATION.md)
- [생성 레퍼런스 목록](AstraLevelTest/ArtSource/Reference/README.md)

# 별내림 숲 — Astra Starfall

사용자 요청(2026-09-07): 기존과 같은 약 100×100m 새 레벨. 첨부한 은색 우주선이 기울어 착륙한 공터, 오솔길, 기존보다 큰 웅덩이, 갓 부러진 나무와 오래된 통나무, 15×15m 버섯 군락, 5×5m 발광 버섯 군락, 작은 옹달샘과 분홍 나무를 구성한다. 분홍 수관은 겹겹의 잎으로 감싼 구형 뭉치다.

새 레퍼런스를 먼저 생성하고 개별 모델링은 우주선 / 나무·통나무 / 버섯·옹달샘 키트로 병렬 제작한다. **물 반사 머터리얼과 스카이는 기존 자산을 재사용한다.**

- 새 맵: `/Game/Astra/Maps/L_AstraStarfall`
- 레퍼런스와 프롬프트: `ArtSource/Reference/Starfall`
- 새 선체 페인트: `ArtSource/Textures/Starfall/T_SF_ShipPaint.png`
- 원본 전체 배치: `ArtSource/Blender/AstraStarfall.blend`
- 미터 단위 공간 설계: `Scripts/starfall_layout.py`

전체 레퍼런스는 목표 이미지이며 실제 UE 렌더는 `ArtSource/Previews/UE_SF*.png`로 별도 보관한다.

![새 전체 레퍼런스](../ArtSource/Reference/Starfall/Ref_StarfallOverview.png)

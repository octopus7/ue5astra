# 군사시설 보스전장 — 레퍼런스

2026-09-08. Built-in ImageGen, `stylized-concept`. 현재 작업은 레퍼런스 제작이며 UE 레벨·모델 구현은 포함하지 않는다. 생성 이미지는 실제 엔진 화면이 아니다.

## 사용자 요청

실외 약 30×20m 군사시설 느낌의 보스전 구역. 철조망과 콘크리트 기둥 구조물, 일부 컨테이너, 전투를 위한 넓은 중앙 공터와 작은 장애물 2개, 2층 높이 목재 가건물 초소, 헬리패드가 필요하다. 우선 레퍼런스 이미지를 만든다.

## 구성 가정

- 30×20m 구역의 외곽에 큰 구조물을 붙인다.
- 컨테이너 2개, 계단 포함 약 5×5m의 높이 5~6m 목재 초소, 약 8×8m 소형 게임용 헬리패드.
- 중앙에는 최소 약 17×10m의 공터를 읽을 수 있게 두고, 짧은 콘크리트 방호물 1개와 낮은 목재 상자 1개만 놓는다.
- 기존 게임의 고정 탑다운 시점, 애니 배경풍 텍스처와 부드러운 50도 광원 그림자 방향을 따른다.
- 최종 파일: `Ref_BossOutpostOverview.png`. 크기와 배치는 아트 레퍼런스의 목표이며 아직 실제 UE 수치로 검증한 배치가 아니다.

## 최종 생성 프롬프트

생성 결과는 [Ref_BossOutpostOverview.png](Ref_BossOutpostOverview.png)로 저장했다. 철조망·콘크리트 기둥 둘레, 목재 2층 높이 초소, 헬리패드, 외곽 컨테이너 2개와 중앙 장애물 2개를 시각적으로 확인했다. 원본 PNG와 프로젝트 복사본의 SHA256은 `c098bac27597694a015e70195db7fec52dd1418642b77363b63ad6357413f5d4`로 일치한다.

Use case: stylized-concept.
Asset type: new environment reference image for AstraLevelTest, a cozy stylized anime-background top-down action game.
Primary request: a compact OUTDOOR military-facility boss arena, approximately 30 metres wide by 20 metres deep. Create one polished, detailed game-environment concept image, not an actual Unreal screenshot.
Composition: elevated fixed orthographic game camera looking down about 58 degrees, landscape 1536x1024. The entire rectangular fenced compound, all corners, entrance and every requested structure fit in the frame with a narrow strip of surrounding grass and woodland. Ground dominates the view; the central combat space is intentionally broad and uncluttered, with generous running loops.
Architecture: substantial weathered reinforced-concrete upright pillars support galvanized chain-link wire fence panels around the boundary. The fence has clearly readable strands of barbed wire along its top, about 2.5 metres tall. A modest concrete post-and-beam gate frame at the front entrance reinforces the abandoned outpost silhouette. Outdoor open sky above, no ceiling spanning the arena.
Perimeter structures: TWO weathered shipping containers, each roughly 6 by 2.5 metres, parked along the side perimeter; one muted olive and one faded blue-gray, restrained painted wear. A TWO-STOREY-HEIGHT temporary WOODEN guard post near a rear corner, roughly 5 to 6 metres tall: timber posts, obvious cross bracing, usable open lower storey, enclosed upper sentry cabin, small wooden balcony, exterior wooden stairs with handrails and a simple plank roof. Its footprint including stairs is about 5 by 5 metres; its front and stairs face the arena and the camera so the two levels are readable. Toward the other rear corner, a compact approximately 8 by 8 metre HELIPAD structure: a low raised concrete/metal deck with a beveled curb and short access ramp, faded perimeter landing ring and a single clear H marking. No helicopter.
Central combat clearing: one connected broad level area of compacted earth, worn gravel and modest concrete patches, at least roughly 17 by 10 metres, unobstructed lines of sight. EXACTLY TWO SMALL FREESTANDING OBSTACLES within this clearing, separated by several metres: one waist-high short concrete road barrier approximately 1.8 by 0.7 metres and one single squat wooden supply crate approximately 1.3 by 1.1 metres. Both are small relative to the open arena. No extra barrels, sandbags, vehicles, rubble piles, rocks, cover pieces or other objects inside the central fighting floor. All large infrastructure hugs the outer edges.
Art direction: charming modeled game forms, softly beveled edges, smooth shading, sufficiently described hand-painted anime background textures. Concrete has broad subtle cracks and cool blue shaded faces; warm timber has readable planks and restrained grain; chain-link and barbed wire are thin but readable at game scale. Muted military olive, warm sand, cool gray-blue ambient shadows and subdued woodland green, consistent with the existing gentle forest game aesthetic. Soft broad daylight and very soft shadows as with a directional-light source angle of 50 degrees, avoid harsh black shadows and gritty photoreal war imagery.
No characters, no boss creature, no weapons, no explosions, no blood. No labels, no dimension arrows, no UI, no watermark or logos. Only the H on the helipad. This is a spatially coherent playable level reference, not a collage, not a blueprint, not a miniature floating slab.

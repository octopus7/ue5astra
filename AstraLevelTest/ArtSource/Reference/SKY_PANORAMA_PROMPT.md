# 하늘 전용 파노라마

2026-09-07. Built-in image generation으로 생성. 최종 원본: `../Textures/T_AnimeSkyPanorama.png`.
하늘 지오메트리에 구름 그림을 평면 투영해 세로로 늘어나던 문제를 교체한다.
UE 재질은 경도 atan2(Y,X), 위도 acos(Z)의 2:1 구면 좌표를 사용한다. 양끝 이음새와 천정은 재질에서 매끄럽게 합성한다.

## 생성 프롬프트

Use case: stylized-concept. Asset type: seamless 360 degree equirectangular lat-long SKY environment texture for Unreal Engine skydome, full sphere 2:1 aspect, 4096 by 2048 if possible. Create a beautiful clean bright anime background painted daytime sky ONLY. This is the flattened full spherical environment map, NOT a perspective landscape illustration. Latitude top edge +90 degrees zenith, horizon exactly horizontal at image vertical midpoint, bottom edge -90 nadir. Upper hemisphere airy cerulean blue zenith gradually transitions to pale light cyan at horizon. A few well separated soft white cumulus cloud islands with elegant hand-painted wisps and cool periwinkle shadows, mainly at 10 to 40 degrees above the horizon (upper-middle region); clouds naturally foreshortened near horizon. Zenith cap top 15 percent is clean cloudless even blue with NO detailed features so pole has no pinching. Bottom half entirely calm smooth pale sky gradient without objects, no horizon line, no ground. Left and right edges must match seamlessly in color and cloud continuation; keep edges mostly clear sky to hide wrap. Cloud coverage about 25 percent, plenty of saturated but gentle blue breathing room, not overcast. No terrain, water, buildings, sun disk, trees, foreground, borders, text, icons, UI, vertical bands, panels or labels. Soft luminous white clouds, fresh cheerful pastoral woodland game atmosphere, no photographic grain.

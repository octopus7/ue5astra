# Smooth forest rock: anime painted albedo

Generated with the built-in imagegen tool. The selected original was copied without resizing or color edits into `ArtSource/Textures/T_AnimeForestRockPaint.png`. Native output is 1254 × 1254 RGB PNG; the prompt requested 2048 × 2048 or greater, but the built-in tool selected its native size.

## Prompt

Use case: stylized-concept
Asset type: seamless tileable ALBEDO / BASE COLOR texture for smooth forest boulder and cliff meshes in a cute top-down 3D game.
Primary request: a professionally hand-painted anime background forest rock surface, beautifully described broad weathered stone, light neutral cool gray-blue rock as the dominant color with restrained desaturated sage moss patches occupying around 12 percent. Rich but gentle large mineral brushwork, subtle chipped paintlike mineral transitions, short irregular weathered fissures and sparse fine grain, natural varied scale. The surface is a continuous stone mass, NOT separate stones.
Composition: straight-on perfectly flat material swatch filling the entire square, 2048 by 2048 pixels or greater. Uniform visual density across all four edges. Seamlessly repeatable left-right and top-bottom, no border, no focal object, no perspective. A single tile should depict approximately 3 metres of rock face.
Color palette: light misty stone gray, silver gray-blue, subdued warm-gray mineral patches, gentle dusty blue in dark crevices, small sage and muted olive moss. Preserve a bright clean readable overall value, midtone rather than washed white. Blue shadow colors are pigment tint only, not directional light.
Style: premium hand-painted anime woodland background, organic gouache-like brush marks, smooth rounded mineral shapes, abundant intentional painterly surface detail visible at top-down game scale, stylized rather than photorealistic. Keep broad masses readable and rest areas between details.
Technical constraints: color/albedo only. Flat soft neutral illumination, no baked directional lighting, no hard shadows, no AO, no metallic highlight, no specular reflections, no normal map colors. Low to medium contrast with subtle creases. No polygon triangles, no faceted low-poly shapes, no polygon mosaic, no bricks, no paving stones, no repeating grid, no cobblestones, no labels, no numbers, no watermark.

## Inspection and intended use

The generated original and saved local PNG were visually inspected. Broad gray-blue stone masses, muted blue fissures and restrained sage moss create an anime background painting treatment. No visible triangular facets, masonry grid, labels or specular lighting are present. Surface detail should come from this albedo with smooth vertex normals, not a faceted normal map.

Use roughly 3 metres per texture tile (2.5–3.5 m range) and rotate the mesh instances to vary the pattern. The edges are visually compatible but not mathematically periodic: mean absolute opposite-edge RGB differences are 7.286/255 horizontally and 8.395/255 vertically. If a repeated seam is exposed on a large cliff, blended triplanar projection is preferable to shrinking the tile until the pattern becomes noisy.

Import as sRGB color/albedo with wrap addressing. Roughness 0.88, metallic 0, specular 0.20 are starting values. No AO, metallic, roughness or normal texture was generated. The source is intentionally preserved at its native size; engine power-of-two resampling may be used for mip generation where required.

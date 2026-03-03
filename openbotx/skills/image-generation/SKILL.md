---
name: image-generation
description: Generate images from text descriptions using AI. Use when the user asks to create, generate, draw, or design an image, illustration, icon, or any visual content.
---

# Image Generation

Generate images using the `generate_image` tool.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | yes | Detailed description of the image |
| `filename` | string | yes | Output filename (e.g. `poster.png`) |
| `aspect_ratio` | string | no | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `4:5`, `5:4`, `21:9` |
| `size` | string | no | `1K` (default), `2K`, `4K` |
| `reference_images` | array | no | Storage paths to reference images |
| `style` | string | no | Style hint (e.g. `photorealistic`, `illustration`) |
| `negative_prompt` | string | no | What to avoid (e.g. `blurry, watermark`) |
| `google_search` | boolean | no | Enable real-time data grounding |

## Prompt Structure

Build prompts with these 5 components:

1. **Style/medium** — photograph, illustration, watercolor, digital art, vector, 3D render
2. **Subject** — who or what, with specific details (pose, clothing, expression, material)
3. **Setting** — location, time of day, atmosphere, weather
4. **Action** — what is happening in the scene
5. **Composition** — camera angle, framing (close-up, wide shot, bird's eye, low angle)

Example: "Cinematic photograph of a futuristic city skyline at golden hour, with flying vehicles crossing between skyscrapers, shot from a rooftop balcony with shallow depth of field, warm amber tones"

## Aspect Ratio Guide

Choose based on the intended use:

- `1:1` — social media posts (Instagram feed, profile pictures)
- `16:9` — banners, landscape, YouTube thumbnails, presentations
- `9:16` — stories, reels, vertical mobile content
- `4:3` — classic photo, presentations
- `3:2` — standard photography
- `4:5` — Instagram portrait posts
- `21:9` — ultrawide cinematic banners

## Reference Images

Reference images provide visual context. The model sees them BEFORE the text prompt.

**For logos and brand assets:**
- Add the logo path to `reference_images`
- In the prompt, be explicit: "Place the provided logo at the bottom center of the image. Do not modify the logo's shape, colors, or proportions — use it exactly as provided, only resize it to fit the composition"
- Never describe what the logo looks like — just describe where and how to use it

**For style references:**
- Add the style image to `reference_images`
- In the prompt: "Generate in the same visual style as the provided reference image"

**For editing existing images:**
- Add the image to `reference_images`
- Describe the desired changes: "Change the background to a sunset beach scene while keeping the subject unchanged"

## Text in Images

- Enclose exact text in quotes: `Write the text "SALE 50% OFF"`
- Describe typography explicitly: "bold white sans-serif font with a subtle drop shadow"
- Specify placement: "centered at the top of the image"
- Keep text minimal for social media — one headline maximum to avoid clutter

## Google Search Grounding

Set `google_search: true` when the image needs real-time or factual data:
- Stock prices and financial charts
- Weather forecasts
- Current events and news topics
- Sports scores and standings
- Real product data

Example: "Visualize the Bitcoin price trend over the last 7 days as an infographic"

## Quality Tips

- **Be descriptive, not repetitive.** Don't use "4K, masterpiece, trending on artstation" — the model understands natural language. Describe the scene vividly instead.
- **Use photographic language** for realistic images: camera model, focal length (85mm f/1.4), lighting setup (soft key light with rim light), film stock (Kodak Portra 400)
- **Be specific about colors and materials:** "matte black aluminum with brushed gold accents" instead of just "dark with gold"
- **Resolution matters:** Use `size: "2K"` for social media, `size: "4K"` for print-quality assets
- **Composition keywords:** rule of thirds, symmetrical, leading lines, negative space, flat lay, isometric

## What NOT to Do

- Don't describe reference images — just describe how to USE them
- Don't add quality spam keywords — focus on scene description
- Don't leave aspect ratio unset for social media — always pick the right ratio
- Don't put too much text in the prompt for text-in-image — keep it to one headline
- Don't forget to use `google_search` when the image needs current real-world data

## After Generation

Always share the saved file URL with the user so they can preview the result.

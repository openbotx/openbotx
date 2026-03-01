---
name: image-generation
description: Generate images from text descriptions using AI. Use when the user asks to create, generate, draw, or design an image, illustration, icon, or any visual content.
---

# Image Generation

Generate images from text prompts using the `generate_image` tool.

## How to Use

Use the `generate_image` tool with these parameters:
- **prompt**: Detailed description of the desired image
- **filename**: Output filename (e.g. `sunset.png`)
- **reference_images**: Optional list of storage paths to use as reference for image editing

## Tips
- Write detailed, descriptive prompts for better results
- Use descriptive filenames — the tool saves to `public/media/` automatically, organized by date
- Inform the user of the saved file path after generation

---
name: image-generation
description: Generate images from text descriptions using AI
---

# Image Generation

Generate images from text prompts using the `generate_image` tool.

## When to Use
Use this skill when the user asks to create, generate, or draw an image.

## How to Use

Use the `generate_image` tool with these parameters:
- **prompt**: Detailed description of the desired image
- **filename**: Output filename (e.g. `sunset.png`)
- **reference_images**: Optional list of storage paths to use as reference for image editing

## Tips
- Write detailed, descriptive prompts for better results
- Use descriptive filenames — the tool saves to `public/media/` automatically, organized by date
- Inform the user of the saved file path after generation

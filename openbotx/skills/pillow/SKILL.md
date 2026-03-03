---
name: pillow
description: >-
  Manipulate images locally using Python and PIL/Pillow. Use when the user
  asks to resize, crop, rotate, flip, filter, enhance, combine, overlay,
  watermark, add text to, convert, compress, create, or edit images locally.
  Also use for thumbnails, borders, color adjustments, transparency,
  animated GIFs, or extracting image metadata.
---

# Pillow — Local Image Manipulation

Use `write_file` to create a Python script, then `exec` to run it.

## Workflow

1. Write a `.py` script with `write_file`
2. Run it with `exec(command="python3 script.py")`
3. Print output so you can read the result
4. Clean up the script after use

Always use paths relative to the workspace. Print confirmation messages so the result is visible.

```python
# example: resize an image
from PIL import Image
img = Image.open("photos/input.jpg")
img = img.resize((800, 600), Image.Resampling.LANCZOS)
img.save("photos/output.jpg", quality=90)
print(f"Saved {img.size[0]}x{img.size[1]}")
```

## Open, Save, Convert

```python
from PIL import Image

img = Image.open("photo.jpg")          # auto-detects format
img.save("photo.png")                  # format from extension
img.save("photo.webp", quality=85)     # WebP with quality
img.save("photo.jpg", quality=95, optimize=True)  # optimized JPEG

# format conversion
rgb = img.convert("RGB")               # drop alpha for JPEG
rgba = img.convert("RGBA")             # add alpha channel
gray = img.convert("L")                # grayscale
```

**Supported formats:** JPEG, PNG, WebP, GIF, BMP, TIFF, ICO, PPM, AVIF

## Create from Scratch

```python
from PIL import Image

# solid color
img = Image.new("RGB", (800, 600), (255, 255, 255))       # white
img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))         # transparent

# gradient
img = Image.new("RGB", (800, 100))
pixels = img.load()
for x in range(800):
    r = int(255 * x / 800)
    for y in range(100):
        pixels[x, y] = (r, 0, 255 - r)
```

## Resize and Transform

```python
from PIL import Image

img = Image.open("photo.jpg")

# resize to exact dimensions
resized = img.resize((800, 600), Image.Resampling.LANCZOS)

# thumbnail — preserves aspect ratio, modifies in place
img.thumbnail((400, 400), Image.Resampling.LANCZOS)

# crop (left, upper, right, lower)
cropped = img.crop((100, 50, 500, 400))

# rotate (degrees counterclockwise, expand=True to fit)
rotated = img.rotate(45, expand=True, fillcolor=(255, 255, 255))

# flip and transpose
flipped_h = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
flipped_v = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
rotated_90 = img.transpose(Image.Transpose.ROTATE_90)
rotated_180 = img.transpose(Image.Transpose.ROTATE_180)
rotated_270 = img.transpose(Image.Transpose.ROTATE_270)
```

**Resampling:** `LANCZOS` (best quality), `BICUBIC`, `BILINEAR`, `NEAREST` (fastest)

## Draw Shapes

```python
from PIL import Image, ImageDraw

img = Image.new("RGB", (600, 400), "white")
draw = ImageDraw.Draw(img)

# rectangle
draw.rectangle([(50, 50), (200, 150)], fill="red", outline="black", width=2)

# rounded rectangle
draw.rounded_rectangle([(250, 50), (400, 150)], radius=20, fill="blue")

# ellipse / circle
draw.ellipse([(50, 200), (200, 350)], fill="green", outline="black", width=2)

# polygon
draw.polygon([(300, 200), (400, 350), (200, 350)], fill="orange")

# line
draw.line([(0, 0), (600, 400)], fill="black", width=3)

# arc (start_angle, end_angle in degrees)
draw.arc([(420, 50), (580, 200)], 0, 270, fill="purple", width=3)

# pie slice (filled arc)
draw.pieslice([(420, 220), (580, 370)], 0, 270, fill="cyan")

# regular polygon (bounding_circle, n_sides)
draw.regular_polygon((500, 100, 40), 6, fill="gold")  # hexagon
```

## Add Text

```python
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (600, 200), "white")
draw = ImageDraw.Draw(img)

# load font (use default if truetype not available)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
except OSError:
    font = ImageFont.load_default(40)

# simple text
draw.text((50, 50), "Hello World", fill="black", font=font)

# centered text using anchor
draw.text((300, 100), "Centered", fill="blue", font=font, anchor="mm")

# multiline text
draw.multiline_text((50, 120), "Line 1\nLine 2", fill="gray", font=font, spacing=8)

# measure text
bbox = font.getbbox("Hello")           # (left, top, right, bottom)
width = font.getlength("Hello")        # width in pixels
```

**Anchors:** First letter = horizontal (`l`eft, `m`iddle, `r`ight), second = vertical (`t`op, `m`iddle, `b`aseline, `d`escent). Common: `mm` = center, `lt` = top-left, `rm` = right-center.

**Font paths:**
- Linux: `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
- macOS: `/System/Library/Fonts/Helvetica.ttc`
- Fallback: `ImageFont.load_default(size)` (no file needed)

## Filters and Effects

```python
from PIL import Image, ImageFilter

img = Image.open("photo.jpg")

# predefined filters
blurred = img.filter(ImageFilter.BLUR)
sharp = img.filter(ImageFilter.SHARPEN)
edges = img.filter(ImageFilter.FIND_EDGES)
contour = img.filter(ImageFilter.CONTOUR)
emboss = img.filter(ImageFilter.EMBOSS)
detail = img.filter(ImageFilter.DETAIL)

# parameterized filters
gaussian = img.filter(ImageFilter.GaussianBlur(radius=5))
box = img.filter(ImageFilter.BoxBlur(radius=3))
unsharp = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
median = img.filter(ImageFilter.MedianFilter(size=5))
```

See `references/api.md` for all filters including MinFilter, MaxFilter, ModeFilter, RankFilter, and custom Kernel.

## Color Adjustments

```python
from PIL import Image, ImageEnhance, ImageOps

img = Image.open("photo.jpg")

# ImageEnhance — factor: 0.0=min, 1.0=original, >1=more
bright = ImageEnhance.Brightness(img).enhance(1.3)     # brighter
contrast = ImageEnhance.Contrast(img).enhance(1.5)     # more contrast
saturated = ImageEnhance.Color(img).enhance(1.4)        # more vivid
sharpened = ImageEnhance.Sharpness(img).enhance(2.0)    # sharper

# ImageOps — quick operations
gray = ImageOps.grayscale(img)
inverted = ImageOps.invert(img)
auto = ImageOps.autocontrast(img)
equalized = ImageOps.equalize(img)
posterized = ImageOps.posterize(img, bits=4)
solarized = ImageOps.solarize(img, threshold=128)

# colorize a grayscale image
colored = ImageOps.colorize(gray, black="navy", white="gold")
```

## Compositing

```python
from PIL import Image

base = Image.open("background.png").convert("RGBA")
overlay = Image.open("foreground.png").convert("RGBA")

# paste at position (no blending — replaces pixels)
base.paste(overlay, (100, 50))

# paste with alpha mask (transparent areas preserved)
base.paste(overlay, (100, 50), mask=overlay)

# alpha composite (full RGBA blending, images must be same size)
overlay_resized = overlay.resize(base.size)
result = Image.alpha_composite(base, overlay_resized)

# blend two images (same size, alpha 0.0=img1, 1.0=img2)
blended = Image.blend(img1, img2, alpha=0.5)

# composite with mask (where mask=255: img1, mask=0: img2)
result = Image.composite(img1, img2, mask)
```

## Watermarks

### Text watermark with transparency

```python
from PIL import Image, ImageDraw, ImageFont

img = Image.open("photo.jpg").convert("RGBA")
w, h = img.size

# create transparent overlay
txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
draw = ImageDraw.Draw(txt_layer)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
except OSError:
    font = ImageFont.load_default(48)

# semi-transparent white text, centered
draw.text((w // 2, h // 2), "WATERMARK", fill=(255, 255, 255, 100),
          font=font, anchor="mm")

result = Image.alpha_composite(img, txt_layer)
result.convert("RGB").save("watermarked.jpg", quality=90)
```

### Image watermark with opacity

```python
from PIL import Image, ImageEnhance

base = Image.open("photo.jpg").convert("RGBA")
logo = Image.open("logo.png").convert("RGBA")

# resize logo
logo = logo.resize((150, 150), Image.Resampling.LANCZOS)

# reduce opacity
alpha = logo.split()[3]
alpha = ImageEnhance.Brightness(alpha).enhance(0.4)  # 40% opacity
logo.putalpha(alpha)

# position at bottom-right with margin
pos = (base.width - logo.width - 20, base.height - logo.height - 20)
base.paste(logo, pos, mask=logo)
base.convert("RGB").save("branded.jpg", quality=90)
```

## Borders and Padding

```python
from PIL import Image, ImageOps

img = Image.open("photo.jpg")

# add solid border
bordered = ImageOps.expand(img, border=20, fill="black")
bordered = ImageOps.expand(img, border=(10, 20, 10, 20), fill="white")  # L, T, R, B

# pad to target size (letterbox/pillarbox)
padded = ImageOps.pad(img, (800, 800), color="black", centering=(0.5, 0.5))

# contain — resize to fit within box, preserving aspect ratio
contained = ImageOps.contain(img, (800, 800))

# cover — resize to fill box, preserving aspect ratio (may crop)
covered = ImageOps.cover(img, (800, 800))

# fit — resize and crop to fill exact size
fitted = ImageOps.fit(img, (800, 800))
```

## Animated GIFs

### Extract frames

```python
from PIL import Image

gif = Image.open("animation.gif")
for i in range(gif.n_frames):
    gif.seek(i)
    gif.copy().save(f"frame_{i:03d}.png")
print(f"Extracted {gif.n_frames} frames")
```

### Create animated GIF

```python
from PIL import Image

frames = [Image.open(f"frame_{i:03d}.png") for i in range(10)]
frames[0].save(
    "animation.gif",
    save_all=True,
    append_images=frames[1:],
    duration=100,       # ms per frame
    loop=0,             # 0 = infinite loop
    optimize=True,
)
```

## Image Info

```python
from PIL import Image

img = Image.open("photo.jpg")

print(f"Size: {img.size}")             # (width, height)
print(f"Mode: {img.mode}")             # RGB, RGBA, L, etc.
print(f"Format: {img.format}")         # JPEG, PNG, etc.
print(f"Info: {img.info}")             # metadata dict (dpi, exif, etc.)
print(f"Bbox: {img.getbbox()}")        # bounding box of non-zero regions
print(f"Colors: {img.getcolors(256)}") # list of (count, color) or None
print(f"Extrema: {img.getextrema()}")  # (min, max) per channel
```

## Channel Operations

```python
from PIL import Image

img = Image.open("photo.jpg")

# split into bands
r, g, b = img.split()

# merge bands
swapped = Image.merge("RGB", (b, g, r))  # swap red and blue

# get single channel
red = img.getchannel("R")  # or by index: img.getchannel(0)
```

## Tips

- Always `convert("RGBA")` before alpha compositing or watermark operations
- Use `thumbnail()` to resize preserving aspect ratio — it modifies in place
- Use `img.copy()` before destructive in-place operations
- Use `Image.Resampling.LANCZOS` for best quality when resizing
- Convert back to `"RGB"` before saving as JPEG (no alpha support)
- Use `ImageOps.exif_transpose(img)` to auto-rotate photos based on EXIF orientation
- For detailed API reference with all parameters, read `references/api.md`

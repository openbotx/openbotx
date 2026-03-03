# Pillow API Reference

Complete module-by-module reference for PIL/Pillow.

## Image Module

### Constructors

```python
Image.new(mode, size, color=0)
# mode: "RGB", "RGBA", "L", "CMYK", "1", "P", "LA"
# size: (width, height)
# color: int, tuple, or color name

Image.open(fp, mode="r", formats=None)
# fp: filename (str/Path) or file object
# returns lazy-loaded Image — call .load() to force read
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `size` | tuple | (width, height) in pixels |
| `width` | int | image width |
| `height` | int | image height |
| `mode` | str | pixel mode (RGB, RGBA, L, etc.) |
| `format` | str | source format (JPEG, PNG, etc.) or None |
| `info` | dict | metadata (dpi, exif, icc_profile, etc.) |
| `n_frames` | int | number of frames (animated images) |
| `is_animated` | bool | True if multi-frame |

### Mode Conversion

```python
img.convert(mode, matrix=None, dither=None, palette=None, colors=256)
# mode: target mode string
```

| Mode | Description | Channels |
|------|-------------|----------|
| `1` | 1-bit binary (black/white) | 1 |
| `L` | 8-bit grayscale | 1 |
| `P` | 8-bit palette | 1 |
| `RGB` | 24-bit true color | 3 |
| `RGBA` | 32-bit true color + alpha | 4 |
| `CMYK` | 32-bit color separation | 4 |
| `YCbCr` | video color format | 3 |
| `LAB` | CIE L*a*b* | 3 |
| `HSV` | hue, saturation, value | 3 |
| `LA` | grayscale + alpha | 2 |
| `PA` | palette + alpha | 2 |
| `I` | 32-bit signed integer | 1 |
| `F` | 32-bit floating point | 1 |

### Resize and Transform

```python
img.resize(size, resample=BICUBIC, box=None, reducing_gap=None)
# size: (width, height)
# resample: Resampling enum
# box: (left, upper, right, lower) — region to resize from

img.thumbnail(size, resample=LANCZOS, reducing_gap=2.0)
# modifies in place, preserves aspect ratio

img.crop(box)
# box: (left, upper, right, lower)

img.rotate(angle, resample=NEAREST, expand=False, center=None, translate=None, fillcolor=None)
# angle: degrees counterclockwise
# expand: True to enlarge canvas to fit rotated image
# fillcolor: color for uncovered areas

img.transpose(method)
# method: Image.Transpose.FLIP_LEFT_RIGHT, FLIP_TOP_BOTTOM,
#         ROTATE_90, ROTATE_180, ROTATE_270, TRANSPOSE, TRANSVERSE

img.transform(size, method, data=None, resample=BICUBIC, fill=1, fillcolor=None)
# method: Image.Transform.AFFINE, PERSPECTIVE, QUAD, MESH
# AFFINE data: 6-tuple (a, b, c, d, e, f)
# PERSPECTIVE data: 8-tuple
```

### Resampling Methods

| Method | Quality | Speed | Use |
|--------|---------|-------|-----|
| `NEAREST` | lowest | fastest | pixel art, icons |
| `BOX` | low | fast | downscaling |
| `BILINEAR` | medium | medium | general |
| `HAMMING` | medium | medium | downscaling |
| `BICUBIC` | high | slow | general (default) |
| `LANCZOS` | highest | slowest | final output |

### Compositing

```python
img.paste(im, box=None, mask=None)
# box: (x, y) or (left, upper, right, lower)
# mask: L or RGBA image — 255=paste, 0=keep original

Image.alpha_composite(im1, im2)
# both must be RGBA, same size — blends using alpha channels

Image.blend(im1, im2, alpha)
# same mode and size — result = im1*(1-alpha) + im2*alpha

Image.composite(im1, im2, mask)
# mask: L mode — where 255 picks im1, 0 picks im2
```

### Channel Operations

```python
img.split()                   # returns tuple of single-band Images
Image.merge(mode, bands)      # combine bands into multi-band Image
img.getchannel(channel)       # "R", "G", "B", "A" or int index
img.point(lut, mode=None)     # apply function or lookup table per pixel
```

### Pixel Access

```python
img.getpixel((x, y))         # returns pixel value (int or tuple)
img.putpixel((x, y), value)  # set pixel value

pixels = img.load()           # returns PixelAccess object (faster)
pixels[x, y]                  # read pixel
pixels[x, y] = (r, g, b)     # write pixel
```

### Analysis

```python
img.getbbox()                 # (left, upper, right, lower) of non-zero regions
img.getcolors(maxcolors=256)  # list of (count, color) or None if too many
img.getextrema()              # (min, max) per band
img.histogram(mask=None)      # list of pixel counts (256 per band)
img.getdata()                 # flat sequence of pixel values
```

### Save Parameters

```python
img.save(fp, format=None, **params)
# format: override format detection — "JPEG", "PNG", "WEBP", "GIF"
```

**JPEG:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quality` | int | 75 | 1-95 (avoid >95) |
| `optimize` | bool | False | extra compression pass |
| `progressive` | bool | False | progressive JPEG |
| `subsampling` | int/str | 2 | 0 (4:4:4), 1 (4:2:2), 2 (4:2:0) |
| `exif` | bytes | - | raw EXIF data |

**PNG:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `compress_level` | int | 6 | 0-9 (9=max compression) |
| `optimize` | bool | False | optimal encoder settings |

**WebP:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quality` | int | 80 | 1-100 |
| `lossless` | bool | False | lossless compression |
| `method` | int | 4 | 0 (fast) to 6 (slow/better) |
| `exact` | bool | False | preserve transparent RGB values |

**GIF:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `save_all` | bool | False | save all frames |
| `append_images` | list | [] | additional frames |
| `duration` | int/list | 0 | ms per frame |
| `loop` | int | 0 | 0=infinite, N=repeat N times |
| `disposal` | int | 0 | frame disposal (2=restore bg) |
| `transparency` | int | - | palette index for transparency |
| `optimize` | bool | False | minimize palette |

---

## ImageDraw Module

```python
from PIL import ImageDraw
draw = ImageDraw.Draw(img, mode=None)
# mode: override drawing mode (e.g. "RGBA" on RGB image)
```

### Shape Methods

All `xy` parameters accept `[(x0, y0), (x1, y1)]` or `[x0, y0, x1, y1]`.

```python
draw.rectangle(xy, fill=None, outline=None, width=1)

draw.rounded_rectangle(xy, radius=0, fill=None, outline=None, width=1, corners=None)
# corners: tuple of 4 bools (top_left, top_right, bottom_right, bottom_left)

draw.ellipse(xy, fill=None, outline=None, width=1)

draw.polygon(xy, fill=None, outline=None, width=1)
# xy: list of (x, y) vertices

draw.regular_polygon(bounding_circle, n_sides, rotation=0, fill=None, outline=None, width=1)
# bounding_circle: (x, y, radius) or ((x, y), radius)

draw.line(xy, fill=None, width=0, joint=None)
# xy: list of (x, y) points
# joint: "curve" for rounded joints

draw.arc(xy, start, end, fill=None, width=1)
# start/end: degrees (0=3 o'clock, counterclockwise)

draw.chord(xy, start, end, fill=None, outline=None, width=1)
# filled arc (connects endpoints with straight line)

draw.pieslice(xy, start, end, fill=None, outline=None, width=1)
# filled arc (connects endpoints through center)

draw.point(xy, fill=None)
# xy: single (x, y) or list of (x, y) points
```

### Text Methods

```python
draw.text(xy, text, fill=None, font=None, anchor=None, spacing=4,
          align="left", direction=None, features=None,
          language=None, stroke_width=0, stroke_fill=None)
# anchor: 2-char string (see anchor reference below)
# stroke_width: text outline thickness
# stroke_fill: text outline color

draw.multiline_text(xy, text, fill=None, font=None, anchor=None,
                    spacing=4, align="left", direction=None,
                    features=None, language=None,
                    stroke_width=0, stroke_fill=None)
# align: "left", "center", "right" (for multiline)

draw.textbbox(xy, text, font=None, anchor=None, spacing=4,
              align="left", direction=None, features=None,
              language=None, stroke_width=0)
# returns (left, top, right, bottom) bounding box

draw.textlength(text, font=None, direction=None, features=None, language=None)
# returns text width in pixels
```

### Text Anchors

Two-character code: horizontal + vertical alignment.

| | `a` (ascender) | `t` (top) | `m` (middle) | `s` (baseline) | `b` (bottom) | `d` (descender) |
|---|---|---|---|---|---|---|
| `l` (left) | `la` | `lt` | `lm` | `ls` | `lb` | `ld` |
| `m` (middle) | `ma` | `mt` | `mm` | `ms` | `mb` | `md` |
| `r` (right) | `ra` | `rt` | `rm` | `rs` | `rb` | `rd` |

Common: `mm` = center, `lt` = top-left (default for single-line), `la` = top-left (default for multiline).

### Color Specification

All `fill` and `outline` parameters accept:
- RGB tuple: `(255, 0, 0)`
- RGBA tuple: `(255, 0, 0, 128)` (on RGBA images)
- Hex string: `"#FF0000"`
- Color name: `"red"`, `"blue"`, `"white"`, `"black"`, `"gold"`, etc.
- Integer: grayscale value 0-255

---

## ImageFont Module

```python
from PIL import ImageFont

ImageFont.truetype(font, size=10, index=0, encoding="", layout_engine=None)
# font: filename or file object
# size: point size
# index: font face index (for .ttc collections)

ImageFont.load_default(size=None)
# built-in bitmap font, no file needed
# size: optional point size (requires freetype)

font.getbbox(text, mode="", direction=None, features=None, language=None,
             stroke_width=0, anchor=None)
# returns (left, top, right, bottom) bounding box

font.getlength(text, mode="", direction=None, features=None, language=None)
# returns advance width in pixels

font.getmask(text, mode="", direction=None, features=None, language=None,
             stroke_width=0, anchor=None)
# returns internal glyph bitmap
```

**Common font paths:**

| OS | Path |
|----|------|
| Linux (Debian/Ubuntu) | `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` |
| Linux (bold) | `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` |
| macOS | `/System/Library/Fonts/Helvetica.ttc` |
| macOS (mono) | `/System/Library/Fonts/Monaco.ttf` |

---

## ImageFilter Module

### Predefined Filters

| Filter | Effect |
|--------|--------|
| `BLUR` | 5x5 averaging blur |
| `CONTOUR` | edge contour detection |
| `DETAIL` | detail enhancement |
| `EDGE_ENHANCE` | subtle edge enhancement |
| `EDGE_ENHANCE_MORE` | stronger edge enhancement |
| `EMBOSS` | emboss/3D relief effect |
| `FIND_EDGES` | edge detection |
| `SHARPEN` | sharpen |
| `SMOOTH` | slight smoothing |
| `SMOOTH_MORE` | stronger smoothing |

### Parameterized Filters

```python
ImageFilter.GaussianBlur(radius=2)
# radius: blur radius in pixels

ImageFilter.BoxBlur(radius)
# radius: box size (faster than Gaussian)

ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
# radius: blur radius, percent: strength, threshold: min difference

ImageFilter.MedianFilter(size=3)
# size: kernel size (must be odd)

ImageFilter.MinFilter(size=3)
# picks minimum value in kernel (erosion)

ImageFilter.MaxFilter(size=3)
# picks maximum value in kernel (dilation)

ImageFilter.ModeFilter(size=3)
# picks most common value in kernel

ImageFilter.RankFilter(size, rank)
# picks the rank-th value (0=min, size*size//2=median)
```

### Custom Kernels

```python
ImageFilter.Kernel(size, kernel, scale=None, offset=0)
# size: (width, height) — must be 3x3 or 5x5
# kernel: sequence of values (length = width * height)
# scale: normalization divisor (default: sum of kernel)
# offset: added to each result pixel
```

Example — sharpen kernel:
```python
sharpen = ImageFilter.Kernel((3, 3), [0, -1, 0, -1, 5, -1, 0, -1, 0])
```

---

## ImageEnhance Module

All enhancers follow the same pattern:

```python
from PIL import ImageEnhance

enhancer = ImageEnhance.Brightness(img)
result = enhancer.enhance(factor)
# factor: 0.0=minimum, 1.0=original, >1.0=increase
```

| Enhancer | factor=0 | factor=1 | factor>1 |
|----------|----------|----------|----------|
| `Brightness` | black image | original | brighter |
| `Contrast` | solid gray | original | more contrast |
| `Color` | grayscale | original | more saturated |
| `Sharpness` | blurred | original | sharper |

---

## ImageOps Module

### Color Operations

```python
from PIL import ImageOps

ImageOps.autocontrast(img, cutoff=0, ignore=None, mask=None, preserve_tone=False)
# cutoff: percent of lightest/darkest pixels to clip

ImageOps.equalize(img, mask=None)
# flatten histogram for uniform distribution

ImageOps.grayscale(img)
# convert to grayscale (returns "L" mode)

ImageOps.invert(img)
# invert all pixel values

ImageOps.posterize(img, bits)
# reduce number of bits per channel (1-8)

ImageOps.solarize(img, threshold=128)
# invert pixels above threshold

ImageOps.colorize(img, black, white, mid=None, blackpoint=0, whitepoint=255, midpoint=127)
# colorize a grayscale image — black/white/mid are color values
```

### Size Operations

```python
ImageOps.expand(img, border=0, fill=0)
# border: int (all sides) or tuple (left, top, right, bottom)
# fill: border color

ImageOps.pad(img, size, method=BICUBIC, color=None, centering=(0.5, 0.5))
# resize to fit within size, pad remaining space
# centering: (0,0)=top-left, (0.5,0.5)=center, (1,1)=bottom-right

ImageOps.contain(img, size, method=BICUBIC)
# resize to fit within size, preserving aspect ratio (no padding)

ImageOps.cover(img, size, method=BICUBIC)
# resize to cover size, preserving aspect ratio (may exceed)

ImageOps.fit(img, size, method=BICUBIC, bleed=0.0, centering=(0.5, 0.5))
# resize and crop to fill exact size

ImageOps.scale(img, factor, resample=BICUBIC)
# scale by factor (2.0 = double size)
```

### Transform Operations

```python
ImageOps.flip(img)            # flip top to bottom
ImageOps.mirror(img)          # flip left to right

ImageOps.exif_transpose(img)
# auto-rotate based on EXIF orientation tag
# always call this when opening photos from cameras/phones
```

---

## Animated Images

### Reading Frames

```python
img = Image.open("animation.gif")
img.n_frames                  # total frame count
img.is_animated               # True if multi-frame
img.seek(frame_number)        # jump to frame (0-indexed)
img.tell()                    # current frame number

# iterate all frames
for i in range(img.n_frames):
    img.seek(i)
    frame = img.copy()        # copy() required — seek reuses buffer
    duration = img.info.get("duration", 100)  # frame duration in ms
```

### Creating Animated GIFs

```python
frames[0].save(
    "output.gif",
    save_all=True,
    append_images=frames[1:],
    duration=100,             # ms per frame (int or list)
    loop=0,                   # 0=infinite
    disposal=2,               # 2=restore background between frames
    optimize=True,            # minimize palette
)
```

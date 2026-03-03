import base64
import io
import logging
from typing import Any

from openbotx.config.schema import CredentialConfig, ImageConfig, ProviderConfig
from openbotx.helpers.path import media_path
from openbotx.storage.base import StorageProvider
from openbotx.tools.base import Tool

logger = logging.getLogger(__name__)

VALID_ASPECT_RATIOS = {
    "1:1",
    "1:4",
    "1:8",
    "2:3",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "16:9",
    "21:9",
}

VALID_SIZES = {"1K", "2K", "4K"}


class ImageGenerationTool(Tool):
    """Generate images using AI models with provider-routed backends."""

    name = "generate_image"
    description = (
        "Generate an image from a text prompt and save it to storage. "
        "Supports aspect ratio, resolution, reference images, style hints, "
        "and Google Search grounding for real-time data. "
        "Reference images are used as visual context — place logos, style "
        "references, or content to incorporate."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Detailed description of the image to generate. "
                    "Include style, subject, setting, action, and composition."
                ),
            },
            "filename": {
                "type": "string",
                "description": "Output filename (e.g. poster.png, banner.jpg)",
            },
            "aspect_ratio": {
                "type": "string",
                "description": (
                    "Image aspect ratio. Options: 1:1, 16:9, 9:16, 4:3, 3:4, "
                    "3:2, 2:3, 4:5, 5:4, 21:9. Use 1:1 for social posts, "
                    "16:9 for banners, 9:16 for stories."
                ),
            },
            "size": {
                "type": "string",
                "description": (
                    "Image resolution. Options: 1K (default), 2K, 4K. "
                    "Use 2K for social media, 4K for print."
                ),
            },
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Storage paths to reference images. These are sent as visual "
                    "context BEFORE the prompt. For logos, describe in the prompt "
                    "how to use them (e.g. 'place the provided logo at the bottom')."
                ),
            },
            "style": {
                "type": "string",
                "description": (
                    "Style hint (e.g. photorealistic, illustration, watercolor, "
                    "minimal, cinematic, digital art, vector, pixel art)"
                ),
            },
            "negative_prompt": {
                "type": "string",
                "description": "What to avoid in the image (e.g. blurry, text, watermark)",
            },
            "google_search": {
                "type": "boolean",
                "description": (
                    "Enable Google Search grounding for real-time data "
                    "(stock prices, weather, current events, charts)"
                ),
            },
        },
        "required": ["prompt", "filename"],
    }

    def __init__(
        self,
        config: ImageConfig,
        provider: ProviderConfig,
        credential: CredentialConfig,
        storage: StorageProvider,
    ):
        self._config = config
        self._provider = provider
        self._credential = credential
        self._storage = storage

    def _is_gemini(self) -> bool:
        model = self._config.model.lower()
        return model.startswith("gemini/") or "gemini" in model.split("/")[0]

    def _gemini_model_id(self) -> str:
        """Extract the model id stripping the provider prefix."""
        model = self._config.model
        if "/" in model:
            return model.split("/", 1)[1]
        return model

    async def execute(self, **kwargs: Any) -> str:
        prompt = kwargs["prompt"]
        filename = kwargs["filename"]
        aspect_ratio = kwargs.get("aspect_ratio") or self._config.default_aspect_ratio or None
        size = kwargs.get("size") or self._config.default_size or "1K"
        reference_images = kwargs.get("reference_images") or []
        style = kwargs.get("style") or ""
        negative_prompt = kwargs.get("negative_prompt") or ""
        google_search = kwargs.get("google_search", False)

        # validate aspect ratio
        if aspect_ratio and aspect_ratio not in VALID_ASPECT_RATIOS:
            return f"Error: invalid aspect_ratio '{aspect_ratio}'. Valid: {', '.join(sorted(VALID_ASPECT_RATIOS))}"

        # validate size
        if size and size not in VALID_SIZES:
            return f"Error: invalid size '{size}'. Valid: {', '.join(sorted(VALID_SIZES))}"

        # build the final prompt with style and negative hints
        final_prompt = prompt
        if style:
            final_prompt = f"Style: {style}. {final_prompt}"
        if negative_prompt:
            final_prompt = f"{final_prompt}. Avoid: {negative_prompt}"

        try:
            if self._is_gemini():
                image_bytes, mime_type = await self._generate_gemini(
                    final_prompt, aspect_ratio, size, reference_images, google_search
                )
            else:
                image_bytes, mime_type = await self._generate_litellm(
                    final_prompt, reference_images
                )
        except Exception as e:
            logger.error("image generation failed: %s", e, exc_info=True)
            return f"Error: image generation failed: {e}"

        path = media_path(filename)
        await self._storage.write(path, image_bytes)
        url = self._storage.get_url(path)

        return f"Image saved: {url}"

    async def _generate_gemini(
        self,
        prompt: str,
        aspect_ratio: str | None,
        size: str,
        reference_paths: list[str],
        google_search: bool,
    ) -> tuple[bytes, str]:
        """Generate image using Google GenAI SDK."""
        from google import genai
        from google.genai import types
        from PIL import Image

        client = genai.Client(api_key=self._credential.key)
        model_id = self._gemini_model_id()

        # build contents: reference images BEFORE text prompt
        contents: list[Any] = []

        for ref_path in reference_paths:
            ref_data = await self._storage.read(ref_path)
            ref_image = Image.open(io.BytesIO(ref_data))
            contents.append(ref_image)

        contents.append(prompt)

        # build image config
        image_config_kwargs: dict[str, str] = {}
        if aspect_ratio:
            image_config_kwargs["aspect_ratio"] = aspect_ratio
        if size:
            image_config_kwargs["image_size"] = size

        image_config = types.ImageConfig(**image_config_kwargs) if image_config_kwargs else None

        # build generation config
        config_kwargs: dict[str, Any] = {
            "response_modalities": ["IMAGE", "TEXT"],
        }
        if image_config:
            config_kwargs["image_config"] = image_config
        if google_search:
            config_kwargs["tools"] = [{"google_search": {}}]

        config = types.GenerateContentConfig(**config_kwargs)

        # call the api
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=contents,
            config=config,
        )

        # extract image from response parts
        if response.parts:
            for part in response.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return part.inline_data.data, part.inline_data.mime_type

        raise RuntimeError("no image in response")

    async def _generate_litellm(
        self,
        prompt: str,
        reference_paths: list[str],
    ) -> tuple[bytes, str]:
        """Generate image using litellm (OpenAI-compatible providers)."""
        from litellm import aimage_edit, aimage_generation

        model = self._config.model
        provider_kwargs = {
            "api_key": self._credential.key or None,
            "api_base": self._provider.base_url or None,
            "extra_headers": self._provider.request_headers or None,
            "timeout": 120,
            **self._provider.request_options,
        }

        if reference_paths:
            buffers = await self._load_image_buffers(reference_paths)
            image_input = buffers[0] if len(buffers) == 1 else buffers
            response = await aimage_edit(
                prompt=prompt,
                model=model,
                image=image_input,
                response_format="b64_json",
                **provider_kwargs,
            )
        else:
            response = await aimage_generation(
                prompt=prompt,
                model=model,
                response_format="b64_json",
                **provider_kwargs,
            )

        if not response.data or not response.data[0].b64_json:
            raise RuntimeError("no image data in response")

        return base64.b64decode(response.data[0].b64_json), "image/png"

    async def _load_image_buffers(self, paths: list[str]) -> list[io.BytesIO]:
        buffers = []
        for path in paths:
            data = await self._storage.read(path)
            buf = io.BytesIO(data)
            buf.name = path.rsplit("/", 1)[-1]
            buffers.append(buf)
        return buffers

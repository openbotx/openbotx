from __future__ import annotations

import base64
import io
import logging

from litellm import aimage_edit, aimage_generation

from openbotx.config.schema import ImageConfig
from openbotx.storage.base import StorageProvider
from openbotx.tools.base import Tool

logger = logging.getLogger(__name__)


class ImageGenerationTool(Tool):
    def __init__(self, config: ImageConfig, storage: StorageProvider):
        self._config = config
        self._storage = storage

    @property
    def name(self) -> str:
        return "generate_image"

    @property
    def description(self) -> str:
        return (
            "Generate an image from a text prompt and save it to storage. "
            "Optionally accepts reference images (paths in storage) for "
            "image-to-image editing. When reference_images are provided, "
            "the prompt describes the desired edits."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the image to generate or edit",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename for the output image (e.g. sunset.png)",
                },
                "reference_images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional list of storage paths to reference images "
                        "(e.g. ['public/media/photo.png']). When provided, "
                        "the model will edit based on these references."
                    ),
                },
            },
            "required": ["prompt", "filename"],
        }

    def _build_model(self) -> str:
        prov = self._config.provider
        model = self._config.model
        if prov.name:
            model = f"{prov.name}/{model}"
        return model

    def _provider_kwargs(self) -> dict:
        prov = self._config.provider
        return {
            "api_key": prov.api_key or None,
            "api_base": prov.api_base,
            "extra_headers": prov.headers or None,
            "timeout": 120,
            **prov.options,
        }

    async def _load_images(self, paths: list[str]) -> list[io.BytesIO]:
        buffers = []
        for path in paths:
            data = await self._storage.read(path)
            buf = io.BytesIO(data)
            buf.name = path.rsplit("/", 1)[-1]
            buffers.append(buf)
        return buffers

    async def execute(self, **kwargs) -> str:
        prompt = kwargs["prompt"]
        filename = kwargs["filename"]
        reference_images = kwargs.get("reference_images") or []

        model = self._build_model()
        provider_kwargs = self._provider_kwargs()

        try:
            if reference_images:
                buffers = await self._load_images(reference_images)
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
        except Exception as e:
            logger.error("image generation failed: %s", e)
            return f"Error: image generation failed: {e}"

        if not response.data:
            return "Error: no image generated"

        image_b64 = response.data[0].b64_json
        if not image_b64:
            return "Error: empty image data"

        path = f"public/media/{filename}"
        await self._storage.write(path, base64.b64decode(image_b64))
        url = self._storage.get_url(path)

        return f"Image saved: {url}"

from __future__ import annotations

import base64
import logging

from litellm import aimage_generation

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
        return "Generate an image from a text prompt and save it to storage."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the image to generate",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename for the image (e.g. sunset.png)",
                },
            },
            "required": ["prompt", "filename"],
        }

    async def execute(self, **kwargs) -> str:
        prompt = kwargs["prompt"]
        filename = kwargs["filename"]

        prov = self._config.provider
        model = self._config.model
        if prov.name:
            model = f"{prov.name}/{model}"

        try:
            response = await aimage_generation(
                prompt=prompt,
                model=model,
                api_key=prov.api_key or None,
                api_base=prov.api_base,
                extra_headers=prov.headers or None,
                response_format="b64_json",
                timeout=120,
                **prov.options,
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

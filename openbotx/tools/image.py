import base64
import logging
from pathlib import Path

import httpx

from openbotx.tools.base import Tool

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class ImageGenerationTool(Tool):

    def __init__(self, provider: str, model: str, api_key: str, workspace: Path):
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._workspace = workspace

    @property
    def name(self) -> str:
        return "generate_image"

    @property
    def description(self) -> str:
        return "Generate an image from a text prompt and save it to a file."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the image to generate",
                },
                "output_path": {
                    "type": "string",
                    "description": "File path relative to workspace to save the image (e.g. images/photo.png)",
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4",
                    "default": "1:1",
                },
            },
            "required": ["prompt", "output_path"],
        }

    async def execute(self, **kwargs) -> str:
        prompt = kwargs["prompt"]
        output_path = kwargs["output_path"]
        aspect_ratio = kwargs.get("aspect_ratio", "1:1")

        full_path = (self._workspace / output_path).resolve()
        if not str(full_path).startswith(str(self._workspace.resolve())):
            return "Error: path outside workspace"

        if self._provider == "gemini":
            return await self._generate_gemini(prompt, aspect_ratio, full_path, output_path)

        return f"Error: unsupported provider '{self._provider}'"

    async def _generate_gemini(
        self, prompt: str, aspect_ratio: str, full_path: Path, rel_path: str
    ) -> str:
        url = f"{GEMINI_API_URL}/{self._model}:predict"
        headers = {"x-goog-api-key": self._api_key}
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": 1,
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=body, headers=headers)

        if response.status_code != 200:
            return f"Error: API returned {response.status_code}: {response.text[:200]}"

        data = response.json()
        predictions = data.get("predictions", [])
        if not predictions:
            return "Error: no image generated"

        image_b64 = predictions[0].get("bytesBase64Encoded", "")
        if not image_b64:
            return "Error: empty image data"

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(base64.b64decode(image_b64))

        return f"Image saved to {rel_path}"

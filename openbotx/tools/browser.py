import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from openbotx.tools.base import Tool

logger = logging.getLogger(__name__)

CHROME_PROFILE = Path.home() / ".openbotx-chrome-profile"


class BrowserTool(Tool):
    """Control Chrome browser via CDP for web automation and scraping."""

    name = "browser"
    description = (
        "Control Chrome browser. Actions: navigate, snapshot, screenshot, "
        "click, type, evaluate, wait."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "snapshot",
                    "screenshot",
                    "click",
                    "type",
                    "evaluate",
                    "wait",
                ],
                "description": "Browser action to perform",
            },
            "url": {"type": "string", "description": "URL to navigate to"},
            "selector": {
                "type": "string",
                "description": "CSS selector for click/type actions",
            },
            "text": {
                "type": "string",
                "description": "Text to type into element",
            },
            "script": {
                "type": "string",
                "description": "JavaScript to evaluate",
            },
            "seconds": {
                "type": "integer",
                "description": "Seconds to wait",
            },
            "max_chars": {
                "type": "integer",
                "description": "Max characters for snapshot (default: 50000)",
            },
        },
        "required": ["action"],
    }

    def __init__(self):
        self._connection = None
        self._session = None
        self._process = None

    async def execute(self, action: str, **kwargs: Any) -> str:
        try:
            if action == "wait":
                seconds = kwargs.get("seconds", 2)
                await asyncio.sleep(seconds)
                return f"Waited {seconds} seconds."

            await self._ensure_browser()

            if action == "navigate":
                return await self._navigate(kwargs.get("url", ""))
            if action == "snapshot":
                return await self._snapshot(kwargs.get("max_chars", 50000))
            if action == "screenshot":
                return await self._screenshot()
            if action == "click":
                return await self._click(kwargs.get("selector", ""))
            if action == "type":
                return await self._type_text(
                    kwargs.get("selector", ""), kwargs.get("text", "")
                )
            if action == "evaluate":
                return await self._evaluate(kwargs.get("script", ""))

            return f"Unknown action: {action}"
        except Exception as e:
            return f"Error: {e}"

    async def _ensure_browser(self) -> None:
        if self._session is not None:
            return

        try:
            from pycdp import cdp
            from pycdp.browser import ChromeLauncher, ChromeSession
        except ImportError:
            raise RuntimeError(
                "python-cdp is required for browser tool. "
                "Install it with: pip install python-cdp"
            )

        chrome_path = self._find_chrome()
        if not chrome_path:
            raise RuntimeError("Google Chrome not found")

        CHROME_PROFILE.mkdir(parents=True, exist_ok=True)

        launcher = ChromeLauncher(
            binary=chrome_path,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={CHROME_PROFILE}",
                "--remote-debugging-port=9222",
            ],
            headless=True,
        )

        self._process = await launcher.launch()
        await asyncio.sleep(1)

        self._connection = await ChromeSession.connect("http://127.0.0.1:9222")
        targets = await self._connection.get_targets()
        page_target = next(
            (t for t in targets if t.get("type") == "page"), targets[0]
        )
        self._session = await self._connection.connect_session(
            page_target["id"]
        )

    async def _navigate(self, url: str) -> str:
        if not url:
            return "Error: url is required for navigate"
        await self._session.execute(
            self._session.cdp.page.navigate(url=url)
        )
        await asyncio.sleep(2)
        return f"Navigated to {url}"

    async def _snapshot(self, max_chars: int = 50000) -> str:
        result = await self._session.execute(
            self._session.cdp.runtime.evaluate(
                expression="document.body.innerText"
            )
        )
        text = str(result[0].value) if result and result[0] else ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (truncated)"
        return text if text else "(empty page)"

    async def _screenshot(self) -> str:
        import base64

        result = await self._session.execute(
            self._session.cdp.page.capture_screenshot(format_="png")
        )
        data = base64.b64encode(result[0]).decode() if result else ""
        return f"Screenshot captured ({len(data)} bytes base64)"

    async def _click(self, selector: str) -> str:
        if not selector:
            return "Error: selector is required for click"
        js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            if (!el) return 'Element not found: {selector}';
            el.click();
            return 'Clicked: {selector}';
        }})()
        """
        result = await self._session.execute(
            self._session.cdp.runtime.evaluate(expression=js)
        )
        return str(result[0].value) if result and result[0] else "Click executed"

    async def _type_text(self, selector: str, text: str) -> str:
        if not selector:
            return "Error: selector is required for type"
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            if (!el) return 'Element not found: {selector}';
            el.focus();
            el.value = '{escaped}';
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            return 'Typed into: {selector}';
        }})()
        """
        result = await self._session.execute(
            self._session.cdp.runtime.evaluate(expression=js)
        )
        return str(result[0].value) if result and result[0] else "Type executed"

    async def _evaluate(self, script: str) -> str:
        if not script:
            return "Error: script is required for evaluate"
        result = await self._session.execute(
            self._session.cdp.runtime.evaluate(expression=script)
        )
        if result and result[0]:
            return str(result[0].value)
        return "(no result)"

    @staticmethod
    def _find_chrome() -> str | None:
        import platform

        system = platform.system()
        if system == "Darwin":
            path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if Path(path).exists():
                return path
        elif system == "Linux":
            for name in ("google-chrome", "google-chrome-stable", "chromium"):
                found = shutil.which(name)
                if found:
                    return found
        elif system == "Windows":
            for path in (
                Path.home()
                / "AppData/Local/Google/Chrome/Application/chrome.exe",
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path(
                    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
                ),
            ):
                if path.exists():
                    return str(path)
        return shutil.which("google-chrome")

    async def cleanup(self) -> None:
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None

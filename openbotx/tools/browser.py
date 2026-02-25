import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from openbotx.tools.base import Tool

logger = logging.getLogger(__name__)


class _ChromeInstance:
    """Singleton Chrome process shared across all BrowserTool instances.

    Each caller gets its own tab (CDP target) via open_tab().
    The Chrome process starts lazily on the first open_tab() call
    and is terminated by cleanup().
    """

    PROFILE = Path.home() / ".openbotx" / "chrome-profile"
    CDP_URL = "http://127.0.0.1:9222"

    _instance: "_ChromeInstance | None" = None

    def __init__(self):
        self._process = None
        self._connection = None
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "_ChromeInstance":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _ensure_running(self) -> None:
        if self._connection is not None:
            return

        from pycdp.browser import ChromeLauncher, ChromeSession

        chrome_path = self._find_chrome()
        if not chrome_path:
            raise RuntimeError("Google Chrome not found")

        self.PROFILE.mkdir(parents=True, exist_ok=True)

        launcher = ChromeLauncher(
            binary=chrome_path,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={self.PROFILE}",
                "--remote-debugging-port=9222",
            ],
            headless=True,
        )

        self._process = await launcher.launch()
        await asyncio.sleep(1)
        self._connection = await ChromeSession.connect(self.CDP_URL)

    async def open_tab(self):
        """Open a new browser tab. Returns (session, target_id)."""
        async with self._lock:
            await self._ensure_running()

            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.put(f"{self.CDP_URL}/json/new")
                target = resp.json()

            session = await self._connection.connect_session(target["id"])
            return session, target["id"]

    async def close_tab(self, target_id: str) -> None:
        """Close a browser tab by its target ID."""
        async with self._lock:
            import httpx

            async with httpx.AsyncClient() as client:
                await client.post(f"{self.CDP_URL}/json/close/{target_id}")

    async def cleanup(self) -> None:
        """Terminate the Chrome process."""
        async with self._lock:
            if self._connection:
                await self._connection.close()
                self._connection = None
            if self._process:
                self._process.terminate()
                self._process = None
            _ChromeInstance._instance = None

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
                Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            ):
                if path.exists():
                    return str(path)
        return shutil.which("google-chrome")


class BrowserTool(Tool):
    """Control Chrome browser via CDP.

    Each BrowserTool instance manages its own tab. The Chrome process
    is shared across all instances via _ChromeInstance singleton.
    Tabs are always closed on cleanup, even after errors.
    """

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
        self._session = None
        self._target_id: str | None = None

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "wait":
            seconds = kwargs.get("seconds", 2)
            await asyncio.sleep(seconds)
            return f"Waited {seconds} seconds."

        await self._ensure_tab()

        if action == "navigate":
            return await self._navigate(kwargs.get("url", ""))
        if action == "snapshot":
            return await self._snapshot(kwargs.get("max_chars", 50000))
        if action == "screenshot":
            return await self._screenshot()
        if action == "click":
            return await self._click(kwargs.get("selector", ""))
        if action == "type":
            return await self._type_text(kwargs.get("selector", ""), kwargs.get("text", ""))
        if action == "evaluate":
            return await self._evaluate(kwargs.get("script", ""))

        return f"Unknown action: {action}"

    async def _ensure_tab(self) -> None:
        if self._session is not None:
            return
        chrome = _ChromeInstance.get()
        self._session, self._target_id = await chrome.open_tab()

    async def _navigate(self, url: str) -> str:
        if not url:
            return "Error: url is required for navigate"
        await self._session.execute(self._session.cdp.page.navigate(url=url))
        await asyncio.sleep(2)
        return f"Navigated to {url}"

    async def _snapshot(self, max_chars: int = 50000) -> str:
        result = await self._session.execute(
            self._session.cdp.runtime.evaluate(expression="document.body.innerText")
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
        result = await self._session.execute(self._session.cdp.runtime.evaluate(expression=js))
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
        result = await self._session.execute(self._session.cdp.runtime.evaluate(expression=js))
        return str(result[0].value) if result and result[0] else "Type executed"

    async def _evaluate(self, script: str) -> str:
        if not script:
            return "Error: script is required for evaluate"
        result = await self._session.execute(self._session.cdp.runtime.evaluate(expression=script))
        if result and result[0]:
            return str(result[0].value)
        return "(no result)"

    async def close_tab(self) -> None:
        """Close this instance's tab. Safe to call multiple times."""
        if self._target_id is None:
            return
        await _ChromeInstance.get().close_tab(self._target_id)
        self._session = None
        self._target_id = None

    async def cleanup(self) -> None:
        """Terminate the entire Chrome process (server shutdown)."""
        await _ChromeInstance.get().cleanup()
        self._session = None
        self._target_id = None

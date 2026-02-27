import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from openbotx.cdp import protocol as cdp
from openbotx.cdp.browser import ChromeLauncher
from openbotx.cdp.connection import CDPConnection, CDPSession, connect_cdp
from openbotx.cdp.protocol.input_ import MouseButton
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
        self._headless = False
        self._launcher: ChromeLauncher | None = None
        self._connection: CDPConnection | None = None
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "_ChromeInstance":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _ensure_running(self, headless: bool = False) -> None:
        if self._connection is not None:
            return

        self._headless = headless
        chrome_path = self._find_chrome()
        if not chrome_path:
            raise RuntimeError("Google Chrome not found")

        self.PROFILE.mkdir(parents=True, exist_ok=True)

        self._launcher = ChromeLauncher(
            binary=chrome_path,
            profile=str(self.PROFILE),
            headless=self._headless,
            args=["--remote-debugging-port=9222"],
            log=False,
        )

        self._launcher.launch()
        await asyncio.sleep(1)
        self._connection = await connect_cdp(self.CDP_URL)

    async def open_tab(self, headless: bool = False) -> tuple[CDPSession, cdp.target.TargetID]:
        """Open a new browser tab. Returns (session, target_id)."""
        async with self._lock:
            await self._ensure_running(headless=headless)

            target_id = await self._connection.execute(cdp.target.create_target("about:blank"))
            session = await self._connection.connect_session(target_id)
            return session, target_id

    async def close_tab(self, target_id: cdp.target.TargetID) -> None:
        """Close a browser tab by its target ID."""
        async with self._lock:
            if self._connection is not None:
                await self._connection.execute(cdp.target.close_target(target_id))

    async def cleanup(self) -> None:
        """Terminate the Chrome process."""
        async with self._lock:
            if self._connection:
                try:
                    await self._connection.close()
                except Exception:
                    pass
                self._connection = None
            if self._launcher:
                self._launcher.kill()
                self._launcher = None
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
        "click, type, press, inspect, evaluate, wait. Use inspect after navigating "
        "to discover interactive elements and their selectors. "
        "By default opens a visible browser window. Set headless=true for invisible mode."
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
                    "press",
                    "inspect",
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
            "key": {
                "type": "string",
                "description": "Key to press: Enter, Tab, Escape, Backspace, ArrowDown, ArrowUp, etc.",
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
            "headless": {
                "type": "boolean",
                "description": "Run browser in headless (invisible) mode. Default: false (visible).",
            },
        },
        "required": ["action"],
    }

    def __init__(self):
        self._session: CDPSession | None = None
        self._target_id: cdp.target.TargetID | None = None
        self._tab_lock = asyncio.Lock()

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "wait":
            seconds = kwargs.get("seconds", 2)
            await asyncio.sleep(seconds)
            return f"Waited {seconds} seconds."

        headless = kwargs.get("headless", False)
        await self._ensure_tab(headless=headless)

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
        if action == "press":
            return await self._press_key(kwargs.get("key", ""))
        if action == "inspect":
            return await self._inspect()
        if action == "evaluate":
            return await self._evaluate(kwargs.get("script", ""))

        return f"Unknown action: {action}"

    async def _ensure_tab(self, headless: bool = False) -> None:
        async with self._tab_lock:
            if self._session is not None:
                return
            chrome = _ChromeInstance.get()
            self._session, self._target_id = await chrome.open_tab(headless=headless)

    async def _navigate(self, url: str) -> str:
        if not url:
            return "Error: url is required for navigate"
        await self._session.execute(cdp.page.navigate(url=url))
        await asyncio.sleep(2)
        return f"Navigated to {url}"

    async def _snapshot(self, max_chars: int = 50000) -> str:
        result = await self._session.execute(
            cdp.runtime.evaluate(expression="document.body.innerText")
        )
        text = str(result[0].value) if result and result[0] else ""
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (truncated)"
        return text if text else "(empty page)"

    async def _screenshot(self) -> str:
        data = await self._session.execute(cdp.page.capture_screenshot(format_="png"))
        return f"Screenshot captured ({len(data)} bytes base64)"

    async def _resolve_element(self, selector: str) -> cdp.runtime.RemoteObjectId | None:
        """Resolve a CSS selector to a CDP RemoteObjectId."""
        # Use JSON encoding for safe JS string interpolation (handles all special chars)
        escaped = json.dumps(selector)
        result = await self._session.execute(
            cdp.runtime.evaluate(expression=f"document.querySelector({escaped})")
        )
        remote_obj = result[0]
        if not remote_obj or not remote_obj.object_id:
            return None
        return remote_obj.object_id

    async def _click_point(self, x: float, y: float) -> None:
        """Dispatch a full CDP mouse click at the given coordinates."""
        await self._session.execute(
            cdp.input_.dispatch_mouse_event(
                "mouseMoved",
                x=x,
                y=y,
                pointer_type="mouse",
            )
        )
        await self._session.execute(
            cdp.input_.dispatch_mouse_event(
                "mousePressed",
                x=x,
                y=y,
                button=MouseButton.LEFT,
                click_count=1,
                buttons=1,
                pointer_type="mouse",
            )
        )
        await self._session.execute(
            cdp.input_.dispatch_mouse_event(
                "mouseReleased",
                x=x,
                y=y,
                button=MouseButton.LEFT,
                click_count=1,
                pointer_type="mouse",
            )
        )

    async def _click(self, selector: str) -> str:
        if not selector:
            return "Error: selector is required for click"

        object_id = await self._resolve_element(selector)
        if not object_id:
            return f"Element not found: {selector}"

        await self._session.execute(cdp.dom.scroll_into_view_if_needed(object_id=object_id))

        quads = await self._session.execute(cdp.dom.get_content_quads(object_id=object_id))
        if not quads:
            return f"Could not determine position of: {selector}"

        quad = quads[0]
        x = (quad[0] + quad[2] + quad[4] + quad[6]) / 4
        y = (quad[1] + quad[3] + quad[5] + quad[7]) / 4

        await self._click_point(x, y)
        return f"Clicked: {selector}"

    async def _type_text(self, selector: str, text: str) -> str:
        if not selector:
            return "Error: selector is required for type"

        # Click element to focus it via CDP
        click_result = await self._click(selector)
        if "not found" in click_result.lower() or "could not" in click_result.lower():
            return click_result
        await asyncio.sleep(0.1)

        # Type each character using CDP keyboard events
        for char in text:
            await self._session.execute(
                cdp.input_.dispatch_key_event("keyDown", text=char, key=char)
            )
            await self._session.execute(cdp.input_.dispatch_key_event("keyUp", key=char))
        return f"Typed into: {selector}"

    _KEY_MAP = {
        "enter": ("Enter", "Enter", 13),
        "tab": ("Tab", "Tab", 9),
        "escape": ("Escape", "Escape", 27),
        "backspace": ("Backspace", "Backspace", 8),
        "delete": ("Delete", "Delete", 46),
        "arrowup": ("ArrowUp", "ArrowUp", 38),
        "arrowdown": ("ArrowDown", "ArrowDown", 40),
        "arrowleft": ("ArrowLeft", "ArrowLeft", 37),
        "arrowright": ("ArrowRight", "ArrowRight", 39),
        "home": ("Home", "Home", 36),
        "end": ("End", "End", 35),
        "space": (" ", "Space", 32),
    }

    async def _press_key(self, key_name: str) -> str:
        if not key_name:
            return "Error: key is required for press"

        mapped = self._KEY_MAP.get(key_name.lower())
        if not mapped:
            return (
                f"Unknown key: {key_name}. Available: {', '.join(k.title() for k in self._KEY_MAP)}"
            )

        key, code, keycode = mapped
        await self._session.execute(
            cdp.input_.dispatch_key_event(
                "keyDown",
                key=key,
                code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
        await self._session.execute(
            cdp.input_.dispatch_key_event(
                "keyUp",
                key=key,
                code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
        return f"Pressed: {key_name}"

    async def _inspect(self) -> str:
        js = """
        (function() {
            var items = [];
            var seen = new Set();
            var els = document.querySelectorAll(
                'a, button, input, textarea, select, [role="button"], [role="link"], '
                + '[role="textbox"], [contenteditable="true"], [tabindex]'
            );
            for (var i = 0; i < els.length && items.length < 50; i++) {
                var el = els[i];
                var rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                if (rect.bottom < 0 || rect.top > window.innerHeight) continue;

                var selector = '';
                if (el.id) {
                    selector = '#' + el.id;
                } else if (el.getAttribute('data-testid')) {
                    selector = '[data-testid="' + el.getAttribute('data-testid') + '"]';
                } else if (el.getAttribute('aria-label')) {
                    selector = '[aria-label="' + el.getAttribute('aria-label') + '"]';
                } else if (el.name) {
                    selector = el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                } else if (el.className && typeof el.className === 'string') {
                    var cls = el.className.trim().split(/\\s+/).slice(0, 2).join('.');
                    selector = el.tagName.toLowerCase() + '.' + cls;
                } else {
                    selector = el.tagName.toLowerCase();
                }

                if (seen.has(selector)) continue;
                seen.add(selector);

                var label = (
                    el.textContent || el.getAttribute('aria-label')
                    || el.getAttribute('placeholder') || el.value || ''
                ).trim().substring(0, 60);

                var tag = el.tagName.toLowerCase();
                var role = el.getAttribute('role') || '';
                var type = el.type || '';
                var desc = tag;
                if (role) desc += '[' + role + ']';
                if (type) desc += '[' + type + ']';

                items.push({s: selector, t: desc, l: label});
            }
            return JSON.stringify(items);
        })()
        """
        result = await self._session.execute(cdp.runtime.evaluate(expression=js))
        raw = str(result[0].value) if result and result[0] else "[]"
        try:
            elements = json.loads(raw)
        except Exception:
            return f"Inspect failed: {raw}"

        if not elements:
            return "No interactive elements found on page."

        lines = ["Interactive elements on page:", ""]
        for el in elements:
            label = f' "{el["l"]}"' if el["l"] else ""
            lines.append(f"  {el['t']}{label}  →  selector: {el['s']}")
        return "\n".join(lines)

    async def _evaluate(self, script: str) -> str:
        if not script:
            return "Error: script is required for evaluate"
        result = await self._session.execute(cdp.runtime.evaluate(expression=script))
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

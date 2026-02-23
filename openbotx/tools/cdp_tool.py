"""CDP browser tool - control Chrome via Chrome DevTools Protocol.

Launches Chrome with remote debugging and controls it via CDP.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from pycdp import cdp
from pycdp.asyncio import connect_cdp
from pycdp.browser import ChromeLauncher

from openbotx.core.tools_registry import tool
from openbotx.helpers.logger import get_logger
from openbotx.models.tool_result import ToolResult

_logger = get_logger("cdp_tool")

_chrome_launcher: ChromeLauncher | None = None
_cdp_connection: Any = None
_cdp_session: Any = None
_chrome_port = 9222

# console, errors
_cdp_console_logs: list[dict] = []
_cdp_page_errors: list[dict] = []
_cdp_listeners_attached: bool = False
_MAX_CONSOLE = 500
_MAX_ERRORS = 200


def _get_chrome_binary() -> str:
    """Get Chrome binary path for the current OS."""
    import platform
    import shutil

    system = platform.system()
    if system == "Darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Linux":
        paths = ["google-chrome", "chromium-browser", "chromium"]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    for path in paths:
        if Path(path).exists() if "/" in path or "\\" in path else shutil.which(path):
            return path

    raise RuntimeError("Chrome not found. Install Chrome or Chromium.")


async def _ensure_chrome_running() -> tuple[Any, Any]:
    """Ensure Chrome is running and return connection and session."""
    global _chrome_launcher, _cdp_connection, _cdp_session

    if _cdp_session is not None:
        return _cdp_connection, _cdp_session

    profile_dir = Path.home() / ".openbotx-chrome-profile"
    profile_dir.mkdir(exist_ok=True)

    if _chrome_launcher is None:
        _logger.debug("cdp_launching_chrome", port=_chrome_port)
        _chrome_launcher = ChromeLauncher(
            binary=_get_chrome_binary(),
            args=[
                f"--remote-debugging-port={_chrome_port}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        await asyncio.get_running_loop().run_in_executor(None, _chrome_launcher.launch)
        await asyncio.sleep(2)
        _logger.debug("cdp_chrome_launched")

    if _cdp_connection is None:
        _logger.debug("cdp_connecting", port=_chrome_port)
        _cdp_connection = await asyncio.wait_for(
            connect_cdp(f"http://localhost:{_chrome_port}"), timeout=10.0
        )
        _logger.debug("cdp_connected")

    if _cdp_session is None:
        target_id = await asyncio.wait_for(
            _cdp_connection.execute(cdp.target.create_target("about:blank")),
            timeout=5.0,
        )
        _cdp_session = await asyncio.wait_for(
            _cdp_connection.connect_session(target_id), timeout=5.0
        )
        await _cdp_session.execute(cdp.page.enable())
        await _cdp_session.execute(cdp.runtime.enable())

    return _cdp_connection, _cdp_session


async def close_cdp_resources() -> None:
    """Close CDP connection and Chrome. Call on app shutdown."""
    global _chrome_launcher, _cdp_connection, _cdp_session

    if _cdp_session is not None:
        try:
            await _cdp_session.execute(cdp.page.close())
        except Exception:
            pass
        _cdp_session = None

    if _cdp_connection is not None:
        try:
            await _cdp_connection.close()
        except Exception:
            pass
        _cdp_connection = None

    if _chrome_launcher is not None:
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, _chrome_launcher.kill
            )
        except Exception:
            pass
        _chrome_launcher = None

    _clear_listeners()


def _clear_listeners() -> None:
    global _cdp_listeners_attached
    _cdp_console_logs.clear()
    _cdp_page_errors.clear()
    _cdp_listeners_attached = False


def _ensure_cdp_listeners(session: Any) -> None:
    """Attach console/error listeners to session."""
    global _cdp_listeners_attached

    if _cdp_listeners_attached:
        return

    def on_console(event: cdp.runtime.ConsoleAPICalled) -> None:
        if len(_cdp_console_logs) < _MAX_CONSOLE:
            args_text = " ".join(
                str(arg.value) if hasattr(arg, "value") else str(arg)
                for arg in event.args
            )
            _cdp_console_logs.append({"type": event.type_.value, "text": args_text})

    def on_exception(event: cdp.runtime.ExceptionThrown) -> None:
        if len(_cdp_page_errors) < _MAX_ERRORS:
            _cdp_page_errors.append({"message": event.exception_details.text})

    session.listen(cdp.runtime.ConsoleAPICalled, on_console)
    session.listen(cdp.runtime.ExceptionThrown, on_exception)

    _cdp_listeners_attached = True


@tool(
    name="cdp_navigate",
    description="Navigate to a URL in Chrome. Use when user says 'access [site]', 'open [URL]', 'go to', 'navigate to'.",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_navigate(url: str, wait_seconds: int = 2) -> ToolResult:
    """Navigate to url."""
    result = ToolResult()
    try:
        _, session = await _ensure_chrome_running()
        await session.execute(cdp.page.navigate(url))
        await asyncio.sleep(max(1, min(10, wait_seconds)))
        result.add_text(
            f"Navigated to {url}. Next: if the user asked for information from this page, call cdp_snapshot to read the content, then cdp_click/cdp_type as needed. Do not reply with only text until you have the data they asked for."
        )
        return result
    except Exception as e:
        _logger.error("cdp_navigate_failed", error=str(e), exc_info=True)
        result.add_error(f"CDP navigate failed: {e}")
        return result


@tool(
    name="cdp_snapshot",
    description="Get text snapshot of the current page (truncated to max_chars, default 12000). Use after cdp_navigate to read page content.",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_snapshot(max_chars: int = 12000) -> ToolResult:
    """Get body text of the page."""
    result = ToolResult()
    limit = max(1000, min(200_000, max_chars))
    try:
        _, session = await _ensure_chrome_running()
        response = await session.execute(
            cdp.runtime.evaluate(
                expression="document.body.innerText", return_by_value=True
            )
        )
        # runtime.evaluate returns tuple: (result_object, exception_details)
        text = (response[0].value or "").strip()
        if len(text) > limit:
            text = (
                text[:limit]
                + "\n\n[... truncated, "
                + str(len(text) - limit)
                + " chars omitted ...]"
            )
        result.add_text(text or "(empty)")
        return result
    except Exception as e:
        result.add_error(f"CDP snapshot failed: {e}")
        return result


@tool(
    name="cdp_screenshot",
    description="Take a screenshot of the current page.",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_screenshot(full_page: bool = False) -> ToolResult:
    """Capture screenshot."""
    result = ToolResult()
    try:
        _, session = await _ensure_chrome_running()
        screenshot_data = await session.execute(
            cdp.page.capture_screenshot(format="png", capture_beyond_viewport=full_page)
        )
        import base64

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
            f.write(base64.b64decode(screenshot_data))

        result.add_image(path=path)
        result.add_text("Screenshot captured")
        return result
    except Exception as e:
        result.add_error(f"CDP screenshot failed: {e}")
        return result


@tool(
    name="cdp_click",
    description="Click an element by CSS selector.",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_click(selector: str, double_click: bool = False) -> ToolResult:
    """Click the first element matching selector."""
    result = ToolResult()
    try:
        _, session = await _ensure_chrome_running()
        script = f"""
        const el = document.querySelector({json.dumps(selector)});
        if (el) {{
            el.click();
            if ({json.dumps(double_click)}) el.click();
            'clicked';
        }} else {{
            'not found';
        }}
        """
        response = await session.execute(
            cdp.runtime.evaluate(expression=script, return_by_value=True)
        )
        # runtime.evaluate returns tuple: (result_object, exception_details)
        if response[0].value == "not found":
            result.add_error(f"Element not found: {selector}")
        else:
            result.add_text(
                f"{'Double-clicked' if double_click else 'Clicked'}: {selector}"
            )
        return result
    except Exception as e:
        result.add_error(f"CDP click failed: {e}")
        return result


@tool(
    name="cdp_type",
    description="Type text into an element (e.g. input) by CSS selector.",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_type(selector: str, text: str, submit: bool = False) -> ToolResult:
    """Fill and optionally submit (Enter)."""
    result = ToolResult()
    try:
        _, session = await _ensure_chrome_running()
        script = f"""
        const el = document.querySelector({json.dumps(selector)});
        if (el) {{
            el.value = {json.dumps(text)};
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            if ({json.dumps(submit)}) {{
                el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13 }}));
            }}
            'typed';
        }} else {{
            'not found';
        }}
        """
        response = await session.execute(
            cdp.runtime.evaluate(expression=script, return_by_value=True)
        )
        # runtime.evaluate returns tuple: (result_object, exception_details)
        if response[0].value == "not found":
            result.add_error(f"Element not found: {selector}")
        else:
            result.add_text(
                f"Typed into {selector}" + (" (submitted)" if submit else "")
            )
        return result
    except Exception as e:
        result.add_error(f"CDP type failed: {e}")
        return result


@tool(
    name="cdp_evaluate",
    description="Run JavaScript in the page. Returns JSON-serializable result.",
    security={"approval_required": False, "dangerous": True},
)
async def tool_cdp_evaluate(script: str) -> ToolResult:
    """Execute script in the page."""
    result = ToolResult()
    try:
        _, session = await _ensure_chrome_running()
        response = await session.execute(
            cdp.runtime.evaluate(expression=script, return_by_value=True)
        )
        # runtime.evaluate returns tuple: (result_object, exception_details)
        if response[0].value is not None:
            result.add_text(
                json.dumps(response[0].value)
                if not isinstance(response[0].value, str)
                else response[0].value
            )
        else:
            result.add_text("ok")
        return result
    except Exception as e:
        result.add_error(f"CDP evaluate failed: {e}")
        return result


@tool(
    name="cdp_wait",
    description="Wait for a specified number of seconds (useful between actions to let page load).",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_wait(seconds: int = 2) -> ToolResult:
    """Wait for specified seconds."""
    result = ToolResult()
    try:
        wait_time = max(1, min(30, seconds))
        await asyncio.sleep(wait_time)
        result.add_text(f"Waited {wait_time} seconds")
        return result
    except Exception as e:
        result.add_error(f"CDP wait failed: {e}")
        return result


@tool(
    name="cdp_console_start",
    description="Start collecting console messages and page errors.",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_console_start() -> ToolResult:
    """Start collecting console/errors."""
    result = ToolResult()
    try:
        _, session = await _ensure_chrome_running()
        _ensure_cdp_listeners(session)
        result.add_text("Collecting console and errors.")
        return result
    except Exception as e:
        result.add_error(f"CDP console start failed: {e}")
        return result


@tool(
    name="cdp_console_get",
    description="Get collected console messages (call cdp_console_start first).",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_console_get(clear: bool = False) -> ToolResult:
    """Return collected console messages."""
    result = ToolResult()
    try:
        result.add_text(json.dumps(_cdp_console_logs, indent=2))
        if clear:
            _cdp_console_logs.clear()
        return result
    except Exception as e:
        result.add_error(f"CDP console get failed: {e}")
        return result


@tool(
    name="cdp_errors_get",
    description="Get collected page errors (call cdp_console_start first).",
    security={"approval_required": False, "dangerous": False},
)
async def tool_cdp_errors_get(clear: bool = False) -> ToolResult:
    """Return collected page errors."""
    result = ToolResult()
    try:
        result.add_text(json.dumps(_cdp_page_errors, indent=2))
        if clear:
            _cdp_page_errors.clear()
        return result
    except Exception as e:
        result.add_error(f"CDP errors get failed: {e}")
        return result

"""Close browser resources on app shutdown."""

import asyncio

from openbotx.helpers.logger import get_logger

logger = get_logger("browser_cleanup")

_SHUTDOWN_TIMEOUT = 5.0


async def close_browser_tools() -> None:
    """Close browser and CDP resources. Call once on app shutdown."""
    try:
        from openbotx.tools.cdp_tool import close_cdp_resources

        await asyncio.wait_for(close_cdp_resources(), timeout=_SHUTDOWN_TIMEOUT)
    except TimeoutError:
        logger.warning("browser_cleanup_timeout", which="cdp", timeout=_SHUTDOWN_TIMEOUT)
    except Exception as e:
        logger.debug("browser_cleanup_error", which="cdp", error=str(e))

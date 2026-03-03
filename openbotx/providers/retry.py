import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from openbotx.providers.errors import (
    LLMError,
    LLMErrorType,
    RateLimitError,
    TransientError,
    classify_error,
)

logger = logging.getLogger(__name__)

RETRYABLE_TYPES = {LLMErrorType.RATE_LIMIT, LLMErrorType.TRANSIENT}

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0


async def retry_with_backoff(
    fn: Callable[[], Awaitable[Any]],
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
) -> Any:
    """Retry an async callable with exponential backoff for transient errors.

    Only retries RateLimitError and TransientError.
    All other exceptions (ContextOverflowError, BillingError, AuthError, etc.)
    propagate immediately.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except (RateLimitError, TransientError) as e:
            last_error = e
            if attempt >= max_retries:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(
                "LLM call failed (attempt %d/%d, %s): %s — retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                e.error_type.value,
                e,
                delay,
            )
            await asyncio.sleep(delay)
        except LLMError:
            # non-retryable classified errors (context overflow, billing, auth)
            raise
        except Exception as e:
            # unclassified exceptions — check if retryable
            error_type = classify_error(e)
            if error_type in RETRYABLE_TYPES:
                last_error = e
                if attempt >= max_retries:
                    break
                delay = min(base_delay * (2**attempt), max_delay)
                logger.warning(
                    "LLM call failed (attempt %d/%d, %s): %s — retrying in %.1fs",
                    attempt + 1,
                    max_retries + 1,
                    error_type.value,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                raise

    raise last_error  # type: ignore[misc]

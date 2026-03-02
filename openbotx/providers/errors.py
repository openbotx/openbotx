import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class LLMErrorType(StrEnum):
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMIT = "rate_limit"
    BILLING = "billing"
    AUTH = "auth"
    TRANSIENT = "transient"
    INVALID_REQUEST = "invalid_request"
    MODEL_NOT_FOUND = "model_not_found"
    UNKNOWN = "unknown"


class LLMError(Exception):
    """Base exception for classified LLM errors."""

    def __init__(self, message: str, error_type: LLMErrorType):
        super().__init__(message)
        self.error_type = error_type


class ContextOverflowError(LLMError):
    def __init__(self, message: str):
        super().__init__(message, LLMErrorType.CONTEXT_OVERFLOW)


class RateLimitError(LLMError):
    def __init__(self, message: str):
        super().__init__(message, LLMErrorType.RATE_LIMIT)


class BillingError(LLMError):
    def __init__(self, message: str):
        super().__init__(message, LLMErrorType.BILLING)


class AuthError(LLMError):
    def __init__(self, message: str):
        super().__init__(message, LLMErrorType.AUTH)


class TransientError(LLMError):
    def __init__(self, message: str):
        super().__init__(message, LLMErrorType.TRANSIENT)


_ERROR_PATTERNS: dict[LLMErrorType, list[str]] = {
    LLMErrorType.CONTEXT_OVERFLOW: [
        "context_length_exceeded",
        "maximum context length",
        "max tokens",
        "context window",
        "too many tokens",
        "prompt is too long",
        "request too large",
        "content_too_large",
        "max_tokens",
    ],
    LLMErrorType.RATE_LIMIT: [
        "rate_limit",
        "rate limit",
        "429",
        "too many requests",
        "quota exceeded",
        "throttl",
        "overloaded",
    ],
    LLMErrorType.BILLING: [
        "billing",
        "insufficient_quota",
        "payment",
        "credit",
        "402",
        "exceeded your current quota",
    ],
    LLMErrorType.AUTH: [
        "authentication",
        "unauthorized",
        "401",
        "403",
        "invalid api key",
        "invalid_api_key",
        "permission denied",
        "access denied",
    ],
    LLMErrorType.MODEL_NOT_FOUND: [
        "model_not_found",
        "model not found",
        "does not exist",
        "not available",
    ],
}

_TRANSIENT_PATTERNS = [
    "timeout",
    "timed out",
    "connection",
    "503",
    "502",
    "500",
    "internal server error",
    "bad gateway",
    "service unavailable",
    "eof",
    "reset by peer",
    "broken pipe",
]

_ERROR_TYPE_TO_CLASS: dict[LLMErrorType, type[LLMError]] = {
    LLMErrorType.CONTEXT_OVERFLOW: ContextOverflowError,
    LLMErrorType.RATE_LIMIT: RateLimitError,
    LLMErrorType.BILLING: BillingError,
    LLMErrorType.AUTH: AuthError,
    LLMErrorType.TRANSIENT: TransientError,
}


def classify_error(error: Exception) -> LLMErrorType:
    """Classify an LLM exception into a known error type."""
    msg = str(error).lower()

    for error_type, patterns in _ERROR_PATTERNS.items():
        if any(p in msg for p in patterns):
            return error_type

    if any(p in msg for p in _TRANSIENT_PATTERNS):
        return LLMErrorType.TRANSIENT

    return LLMErrorType.UNKNOWN


def raise_classified(error: Exception) -> None:
    """Classify and re-raise as a typed LLMError if applicable."""
    error_type = classify_error(error)
    cls = _ERROR_TYPE_TO_CLASS.get(error_type)
    if cls:
        raise cls(str(error)) from error

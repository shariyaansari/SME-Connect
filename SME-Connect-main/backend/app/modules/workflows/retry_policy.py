from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.modules.workflows.mapping import MappingResolutionError


class FailureCategory(str, Enum):
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMIT = "rate_limit"
    CONNECTOR_ERROR = "connector_error"
    TIMEOUT = "timeout"
    CONDITION_ERROR = "condition_error"
    MAPPING_ERROR = "mapping_error"
    SYSTEM_ERROR = "system_error"


# Categories that are safe and transient to automatically retry
RETRYABLE_CATEGORIES: frozenset[FailureCategory] = frozenset({
    FailureCategory.RATE_LIMIT,
    FailureCategory.TIMEOUT,
    FailureCategory.CONNECTOR_ERROR,
})

# Categories that require user configuration or code intervention (must not loop/retry)
NON_RETRYABLE_CATEGORIES: frozenset[FailureCategory] = frozenset({
    FailureCategory.AUTHENTICATION_ERROR,
    FailureCategory.AUTHORIZATION_ERROR,
    FailureCategory.VALIDATION_ERROR,
    FailureCategory.MAPPING_ERROR,
    FailureCategory.CONDITION_ERROR,
    FailureCategory.SYSTEM_ERROR,
})

# Configurable constants (avoiding scattered magic numbers)
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_DELAYS_SECONDS: tuple[int, ...] = (60, 300, 900)  # 1 min, 5 mins, 15 mins
MAX_RETRY_DELAY_CAP_SECONDS: int = 3600  # 1 hour safety ceiling


@dataclass
class RetryDecision:
    should_retry: bool
    failure_category: FailureCategory
    retry_count: int
    next_retry_at: datetime | None
    reason: str


def classify_failure(
    error: Exception | str,
    error_category_hint: str | None = None,
) -> FailureCategory:
    """
    Classifies an error or exception into a standardized FailureCategory.
    Connector-agnostic: relies on generic error signatures, standard HTTP status codes,
    and generic exception types. Guarantees secrets are never exposed.
    """
    if error_category_hint:
        try:
            return FailureCategory(error_category_hint.lower())
        except ValueError:
            pass

    if isinstance(error, MappingResolutionError):
        return FailureCategory.MAPPING_ERROR

    msg = str(error).lower()

    # 1. Mapping error
    if "mapping resolution error" in msg or "mapping" in msg and "error" in msg:
        return FailureCategory.MAPPING_ERROR

    # 2. Rate limit (429, Too Many Requests)
    if "rate limit" in msg or "too many requests" in msg or "429" in msg or "quota exceeded" in msg or "throttl" in msg:
        return FailureCategory.RATE_LIMIT

    # 3. Timeout & Network failures
    if any(k in msg for k in (
        "timeout", "timed out", "connect timeout", "read timeout", "network",
        "connection reset", "connection refused", "econnreset", "econnrefused"
    )):
        return FailureCategory.TIMEOUT

    # 4. Authentication / Missing Connection / Expired tokens
    if any(k in msg for k in (
        "no active connection", "connection not found", "unauthorized",
        "invalid credentials", "token expired", "expired token", "401"
    )):
        return FailureCategory.AUTHENTICATION_ERROR

    # 5. Authorization / Permissions
    if any(k in msg for k in ("forbidden", "permission denied", "not permitted", "403")):
        return FailureCategory.AUTHORIZATION_ERROR

    # 6. Condition evaluation configuration error
    if "condition" in msg and any(k in msg for k in ("evaluat", "operator", "invalid", "unsupported")):
        return FailureCategory.CONDITION_ERROR

    # 7. Validation / Unsupported capability / Bad Request
    if any(k in msg for k in (
        "validation", "not registered", "invalid step", "not implemented",
        "missing required", "invalid input", "bad request", "400", "422"
    )):
        return FailureCategory.VALIDATION_ERROR

    # 8. Temporary connector or remote service errors (500, 502, 503, 504)
    if any(k in msg for k in (
        "service unavailable", "bad gateway", "gateway timeout", "502", "503", "504",
        "internal server error", "500", "temporary connector failure", "connector error"
    )):
        return FailureCategory.CONNECTOR_ERROR

    # 9. Fallback generic system error
    return FailureCategory.SYSTEM_ERROR


def calculate_next_retry_time(
    retry_count: int,
    base_time: datetime | None = None,
    delays: tuple[int, ...] = DEFAULT_RETRY_DELAYS_SECONDS,
    retry_after_seconds: int | None = None,
) -> datetime:
    """
    Calculates the exact timestamp for the next retry attempt using bounded backoff delays.
    retry_count: 0 for the first retry, 1 for the second, etc.
    """
    if base_time is None:
        base_time = datetime.now(timezone.utc)

    if retry_after_seconds is not None and retry_after_seconds > 0:
        delay = min(retry_after_seconds, MAX_RETRY_DELAY_CAP_SECONDS)
    else:
        delay_index = min(max(retry_count, 0), len(delays) - 1)
        delay = delays[delay_index]

    return base_time + timedelta(seconds=delay)


def should_retry(
    failure_category: FailureCategory,
    current_retry_count: int,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> bool:
    """
    Determines whether an execution should be scheduled for retry based on category
    and current retry attempt count.
    """
    if failure_category not in RETRYABLE_CATEGORIES:
        return False
    return current_retry_count < max_retries


def evaluate_retry(
    error: Exception | str,
    current_retry_count: int,
    max_retries: int = DEFAULT_MAX_RETRIES,
    delays: tuple[int, ...] = DEFAULT_RETRY_DELAYS_SECONDS,
    base_time: datetime | None = None,
    retry_after_seconds: int | None = None,
    category_hint: str | None = None,
) -> RetryDecision:
    """
    Evaluates failure and determines retry scheduling with bounded backoff.
    Enforces maximum retry bounds and distinguishes retryable vs non-retryable errors.
    """
    category = classify_failure(error, error_category_hint=category_hint)
    is_retryable = category in RETRYABLE_CATEGORIES

    if not is_retryable:
        return RetryDecision(
            should_retry=False,
            failure_category=category,
            retry_count=current_retry_count,
            next_retry_at=None,
            reason=f"Failure category '{category.value}' is non-retryable",
        )

    if current_retry_count >= max_retries:
        return RetryDecision(
            should_retry=False,
            failure_category=category,
            retry_count=current_retry_count,
            next_retry_at=None,
            reason=f"Exceeded maximum retry count ({max_retries})",
        )

    next_retry_at = calculate_next_retry_time(
        retry_count=current_retry_count,
        base_time=base_time,
        delays=delays,
        retry_after_seconds=retry_after_seconds,
    )

    return RetryDecision(
        should_retry=True,
        failure_category=category,
        retry_count=current_retry_count + 1,
        next_retry_at=next_retry_at,
        reason=f"Retryable failure '{category.value}' scheduled for retry",
    )

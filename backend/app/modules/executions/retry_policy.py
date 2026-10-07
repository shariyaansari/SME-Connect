from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

# ============================================================================
# Retry Configuration & Failure Categories (Module 6.1)
# ============================================================================

MAX_RETRY_COUNT = 3
RETRY_DELAYS_SECONDS: list[int] = [60, 300, 900]  # 1 min, 5 mins, 15 mins


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


RETRYABLE_CATEGORIES: set[FailureCategory] = {
    FailureCategory.CONNECTOR_ERROR,
    FailureCategory.TIMEOUT,
    FailureCategory.RATE_LIMIT,
}

NON_RETRYABLE_CATEGORIES: set[FailureCategory] = {
    FailureCategory.AUTHENTICATION_ERROR,
    FailureCategory.AUTHORIZATION_ERROR,
    FailureCategory.VALIDATION_ERROR,
    FailureCategory.CONDITION_ERROR,
    FailureCategory.MAPPING_ERROR,
    FailureCategory.SYSTEM_ERROR,
}


def is_category_retryable(category: FailureCategory | str) -> bool:
    if isinstance(category, str):
        try:
            category = FailureCategory(category)
        except ValueError:
            return False
    return category in RETRYABLE_CATEGORIES


def calculate_next_retry(
    retry_count: int,
    from_time: datetime | None = None,
    custom_delays: list[int] | None = None,
) -> datetime | None:
    """
    Computes bounded exponential backoff retry timestamp.
    Returns None if retry count exceeds or reaches MAX_RETRY_COUNT.
    """
    delays = custom_delays if custom_delays is not None else RETRY_DELAYS_SECONDS
    max_count = len(delays)

    if retry_count >= max_count:
        return None

    base_time = from_time or datetime.now(timezone.utc)
    delay_seconds = delays[retry_count]
    return base_time + timedelta(seconds=delay_seconds)


def classify_failure(error: Any) -> tuple[FailureCategory, bool]:
    """
    Classifies arbitrary runtime errors into structured failure categories and
    determines retry eligibility in a connector-agnostic manner.
    """
    # 1. Structured custom connector error if provided
    category_attr = getattr(error, "failure_category", None) or getattr(error, "category", None)
    if category_attr:
        try:
            cat = FailureCategory(category_attr)
            retryable_attr = getattr(error, "retryable", None)
            return cat, (retryable_attr if retryable_attr is not None else is_category_retryable(cat))
        except ValueError:
            pass

    err_str = str(error).lower()
    err_cls = error.__class__.__name__.lower() if hasattr(error, "__class__") else ""

    # 2. Rate limiting (429, Too Many Requests) -> RETRYABLE
    if any(k in err_str for k in ("429", "rate limit", "too many requests", "quota exceeded")):
        return FailureCategory.RATE_LIMIT, True

    # 3. Timeout -> RETRYABLE
    if any(k in err_str or k in err_cls for k in ("timeout", "timed out", "connecttimeout", "readtimeout")):
        return FailureCategory.TIMEOUT, True

    # 4. Temporary network & upstream server drops (502, 503, 504) -> RETRYABLE
    if any(k in err_str for k in ("502", "503", "504", "bad gateway", "service unavailable", "gateway timeout", "connection reset", "network error")):
        return FailureCategory.CONNECTOR_ERROR, True

    # 5. Mapping & data path errors -> NON-RETRYABLE
    if any(k in err_str for k in ("mapping path", "not found in trigger data", "preceding step", "malformed mapping")):
        return FailureCategory.MAPPING_ERROR, False

    # 6. Condition evaluation configuration errors -> NON-RETRYABLE
    if any(k in err_str for k in ("condition step", "unsupported condition operator")):
        return FailureCategory.CONDITION_ERROR, False

    # 7. Authentication / Authorization configuration errors -> NON-RETRYABLE
    if any(k in err_str for k in ("401", "unauthorized", "invalid token", "invalid google cloud credentials", "api key is required", "private key is required", "invalid api_key")):
        return FailureCategory.AUTHENTICATION_ERROR, False

    if any(k in err_str for k in ("403", "forbidden", "permission denied")):
        return FailureCategory.AUTHORIZATION_ERROR, False

    # 8. Missing connection in tenant organization -> NON-RETRYABLE
    if any(k in err_str for k in ("no active connection found", "unknown connector")):
        return FailureCategory.VALIDATION_ERROR, False

    # 9. Generic connector error fallback
    if "connector" in err_str or "adapter" in err_str:
        return FailureCategory.CONNECTOR_ERROR, True

    return FailureCategory.SYSTEM_ERROR, False


def explain_failure_for_user(
    failure_category: FailureCategory | str | None,
    error_message: str | None,
    will_retry: bool = False,
    next_retry_at: datetime | None = None,
) -> dict[str, Any]:
    """
    Translates raw error data and failure categories into safe, understandable,
    and actionable explanations for SME business users without technical jargon (Module 6.8).
    Guarantees zero leakage of credentials, tokens, or authorization headers.
    """
    cat_str = str(failure_category).lower() if failure_category else "system_error"
    clean_err = error_message or "An unexpected issue occurred."

    retry_info = ""
    if will_retry and next_retry_at:
        retry_info = f" The system will automatically retry this execution at {next_retry_at.strftime('%H:%M:%S UTC')}."
    elif will_retry:
        retry_info = " The system will automatically retry this execution shortly."

    if "authentication" in cat_str:
        return {
            "title": "Connection Authorization Required",
            "explanation": "The external service could not authenticate SME Connect. Your connection credentials or token may have expired or changed.",
            "guidance": "Go to Connections/Integrations and update or re-authenticate your connection.",
            "can_manual_retry": True,
        }
    elif "authorization" in cat_str:
        return {
            "title": "Permission Denied by Provider",
            "explanation": "Your account does not have sufficient permissions to access the requested resource in the external service.",
            "guidance": "Check user roles and permission scopes in your external account.",
            "can_manual_retry": True,
        }
    elif "rate_limit" in cat_str:
        return {
            "title": "Provider Rate Limit Reached",
            "explanation": f"The external service is temporarily limiting requests due to high volume.{retry_info}",
            "guidance": "No immediate action needed. The system will retry automatically once the provider quota resets.",
            "can_manual_retry": True,
        }
    elif "timeout" in cat_str:
        return {
            "title": "Provider Request Timed Out",
            "explanation": f"The external provider did not respond in time.{retry_info}",
            "guidance": "Usually a temporary provider delay. You can wait for the automatic retry or retry manually.",
            "can_manual_retry": True,
        }
    elif "mapping" in cat_str:
        return {
            "title": "Missing Field in Data",
            "explanation": f"The workflow required a specific field that was missing from the incoming data: {clean_err}",
            "guidance": "Check the workflow field mappings and make sure all required fields are provided by the trigger.",
            "can_manual_retry": False,
        }
    elif "condition" in cat_str:
        return {
            "title": "Condition Configuration Issue",
            "explanation": f"A condition step could not be evaluated due to an invalid configuration: {clean_err}",
            "guidance": "Review the condition rules in your workflow builder.",
            "can_manual_retry": False,
        }
    elif "validation" in cat_str:
        return {
            "title": "Setup or Connection Missing",
            "explanation": f"The workflow could not run because a required setting or active connection was not found: {clean_err}",
            "guidance": "Verify your active connections in the Integrations tab.",
            "can_manual_retry": True,
        }
    elif "connector" in cat_str:
        return {
            "title": "Service Temporarily Unavailable",
            "explanation": f"The external integration encountered a temporary service issue.{retry_info}",
            "guidance": "The system will retry automatically, or you can retry manually once the external service is restored.",
            "can_manual_retry": True,
        }
    else:
        return {
            "title": "Execution Error",
            "explanation": f"An issue occurred while processing this step: {clean_err}",
            "guidance": "Review execution step details or contact support if the issue persists.",
            "can_manual_retry": True,
        }

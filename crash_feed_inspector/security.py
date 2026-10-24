"""Best-effort redaction of common credential fields before local logging."""
from __future__ import annotations

import json
import re
from typing import Any

SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|set-cookie|access[_-]?token|refresh[_-]?token|"
    r"token|jwt|bearer|credential|password|passwd|secret|api[_-]?key|csrf|session[_-]?id|signed[_-]?url)",
    re.IGNORECASE,
)
TEXT_SECRET = re.compile(
    r"(?i)(authorization|cookie|set-cookie|access[_-]?token|refresh[_-]?token|"
    r"token|jwt|bearer|credential|password|passwd|secret|api[_-]?key|csrf|session[_-]?id|signed[_-]?url)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s&,;]+)"
)


def _redact_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else _redact_object(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, str):
        return TEXT_SECRET.sub(r"\1\2[REDACTED]", value)
    return value


def sanitize_message(raw: str) -> str:
    """Redact common secret-shaped fields in JSON or text messages.

    This is defense in depth, not a guarantee against every proprietary token
    format. Do not capture messages if the source may expose credentials that
    cannot safely be retained.
    """
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return TEXT_SECRET.sub(r"\1\2[REDACTED]", str(raw))
    return json.dumps(_redact_object(payload), ensure_ascii=False, separators=(",", ":"))

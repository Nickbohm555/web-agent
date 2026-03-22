from __future__ import annotations

SUPPORTED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


def is_supported_content_type(content_type: str) -> bool:
    return any(content_type.startswith(value) for value in SUPPORTED_CONTENT_TYPES)

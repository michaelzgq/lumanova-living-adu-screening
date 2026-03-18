from __future__ import annotations

from collections.abc import Mapping


def _clean_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def explicit_source_context(query_params: Mapping[str, object] | None) -> dict[str, str]:
    query_params = query_params or {}
    source_tag = _clean_value(query_params.get("source"))
    utm_source = _clean_value(query_params.get("utm_source"))
    utm_medium = _clean_value(query_params.get("utm_medium"))
    utm_campaign = _clean_value(query_params.get("utm_campaign"))

    if source_tag and not utm_source:
        utm_source = source_tag

    return {
        "source_tag": source_tag,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
    }


def _normalized_headers(headers: Mapping[str, object] | None) -> dict[str, str]:
    if not headers:
        return {}
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        normalized[str(key).strip().lower()] = _clean_value(value).lower()
    return normalized


def inferred_source_context(headers: Mapping[str, object] | None) -> dict[str, str]:
    normalized = _normalized_headers(headers)
    user_agent = normalized.get("user-agent", "")
    referer = normalized.get("referer", "")
    origin = normalized.get("origin", "")
    combined = " ".join(part for part in (user_agent, referer, origin) if part)

    if any(token in combined for token in ("micromessenger", "wechat", "weixin")):
        return {
            "source_tag": "wechat",
            "utm_source": "wechat",
            "utm_medium": "social",
            "utm_campaign": "auto_detect",
        }

    if any(token in combined for token in ("xiaohongshu", "xhslink", "rednote")):
        return {
            "source_tag": "xiaohongshu",
            "utm_source": "xiaohongshu",
            "utm_medium": "social",
            "utm_campaign": "auto_detect",
        }

    return {
        "source_tag": "direct_or_unknown",
        "utm_source": "direct_or_unknown",
        "utm_medium": "direct",
        "utm_campaign": "auto_detect",
    }


def resolve_source_context(
    query_params: Mapping[str, object] | None,
    headers: Mapping[str, object] | None,
) -> dict[str, str]:
    explicit = explicit_source_context(query_params)
    if any(explicit.values()):
        return explicit
    return inferred_source_context(headers)

from __future__ import annotations

import os
from typing import Any


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st

        direct_value: Any = st.secrets.get(name)
        if direct_value not in (None, ""):
            return str(direct_value).strip()

        env_block = st.secrets.get("env")
        if env_block and hasattr(env_block, "get"):
            nested_value = env_block.get(name)
            if nested_value not in (None, ""):
                return str(nested_value).strip()
    except Exception:  # noqa: BLE001
        return default
    return default


def get_bool_setting(name: str, default: bool = False) -> bool:
    value = get_setting(name, "")
    if not value:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def debug_setting_state(name: str) -> dict[str, Any]:
    env_value = os.getenv(name, "")
    env_present = bool(str(env_value).strip())
    direct_present = False
    nested_present = False
    secrets_available = False
    try:
        import streamlit as st

        secrets_available = True
        direct_value: Any = st.secrets.get(name)
        direct_present = direct_value not in (None, "")

        env_block = st.secrets.get("env")
        if env_block and hasattr(env_block, "get"):
            nested_value = env_block.get(name)
            nested_present = nested_value not in (None, "")
    except Exception:  # noqa: BLE001
        secrets_available = False

    effective_value = get_setting(name, "")
    return {
        "name": name,
        "effective_present": bool(effective_value),
        "env_present": env_present,
        "direct_secret_present": direct_present,
        "nested_secret_present": nested_present,
        "secrets_available": secrets_available,
        "effective_value": effective_value,
    }

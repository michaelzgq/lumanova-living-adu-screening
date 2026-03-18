from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload


def load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_playbook_rows(path: Path) -> list[dict[str, Any]]:
    payload = load_yaml(path)
    return payload.get("jurisdictions", [])


def match_policy_notes(path: Path, knowledge_ids: list[str], limit: int = 5) -> list[dict[str, Any]]:
    payload = load_yaml(path)
    entries = payload.get("entries", [])
    scored: list[tuple[int, dict[str, Any]]] = []
    id_set = set(knowledge_ids)

    for entry in entries:
        tags = set(entry.get("tags", []))
        score = len(tags.intersection(id_set))
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: (-item[0], item[1].get("title", "")))
    return [entry for _, entry in scored[:limit]]


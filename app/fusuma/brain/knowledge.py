"""知識カード(出典つき)。反証役には search_result ブロック(Citations)として、便りには出典名つきの本文として渡す。"""
from __future__ import annotations

import json
from functools import lru_cache

from .. import config


@lru_cache
def cards() -> list[dict]:
    return json.loads(config.KNOWLEDGE.read_text())


def by_kind(*kinds: str) -> list[dict]:
    return [c for c in cards() if c["kind"] in kinds]


def card(cid: str) -> dict | None:
    return next((c for c in cards() if c["id"] == cid), None)


def as_search_results(cs: list[dict]) -> list[dict]:
    return [{
        "type": "search_result",
        "source": c["source_url"],
        "title": f"{c['title']}({c['source_name']}、{c['checked']} 確認)",
        "content": [{"type": "text", "text": c["text"]}],
        "citations": {"enabled": True},
    } for c in cs]


def as_text(cs: list[dict]) -> str:
    """listener のシステムプロンプト用の要約(id・タイトル・本文)。"""
    lines = ["## 知識カード(公的機関の出典つき。ここにない事実は使わない)"]
    for c in cs:
        lines.append(f"- [{c['id']}] {c['title']}: {c['text']}")
    return "\n".join(lines)

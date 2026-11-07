"""反証役(rebuttal): Sonnet 5.5。聞き役の結論は渡さない(独立文脈)。知識カードを search_result で渡し、引用つきで答える。"""
from __future__ import annotations

import re

from .. import config
from . import knowledge, llm

FIELDS = {"本物の可能性": "genuine_likelihood", "別の説明": "alternative", "本物らしい点": "for_genuine",
          "本物らしくない点": "against_genuine", "確かめ方": "how_to_verify"}
LEVEL = {"低": "low", "中": "medium", "高": "high"}


def review(lines: list[str], context_text: str) -> dict:
    cards = knowledge.by_kind("genuine", "technique", "rules")
    user_content = knowledge.as_search_results(cards) + [{
        "type": "text",
        "text": "家族の文脈(本人の予定・手続き・知り合い):\n" + context_text +
                "\n\n祖母の発話(時刻順。相手の声は聞いていない):\n" + "\n".join(lines) +
                "\n\nこの電話が本物・正当なものである可能性を検討し、指定の形式で答えてください。",
    }]
    text, resp = llm.call("rebuttal", config.MODEL_REBUTTAL, llm.system_blocks("principles", "rebuttal"),
                          [{"role": "user", "content": user_content}], max_tokens=2500, effort="medium", fallback=True)
    return parse(resp)


def parse(resp) -> dict:
    """1 行 1 項目のテキストを、引用(citations)ごと構造化する。"""
    out: dict = {"genuine_likelihood": "medium", "alternative": None, "for_genuine": [], "against_genuine": [],
                 "how_to_verify": "", "citations": [], "raw": ""}
    cur_field, cur_line, cur_cites = None, "", []

    def commit():
        nonlocal cur_line, cur_cites
        line = cur_line.strip()
        if line:
            m = re.match(r"^[・\-\s]*(本物の可能性|別の説明|本物らしい点|本物らしくない点|確かめ方)\s*[:：]\s*(.*)$", line)
            field = FIELDS[m.group(1)] if m else cur_field
            value = (m.group(2) if m else line.lstrip("・- ")).strip()
            if field:
                _put(out, field, value, cur_cites)
        cur_line, cur_cites = "", []

    for b in resp.content:
        if b.type != "text":
            continue
        out["raw"] += b.text
        cites = [{"source": c.source, "title": c.title, "cited_text": c.cited_text}
                 for c in (getattr(b, "citations", None) or []) if getattr(c, "type", "") == "search_result_location"]
        pieces = b.text.split("\n")
        for i, piece in enumerate(pieces):
            cur_line += piece
            cur_cites += cites
            if i < len(pieces) - 1:
                m = re.match(r"^[・\-\s]*(本物の可能性|別の説明|本物らしい点|本物らしくない点|確かめ方)", cur_line.strip())
                if m:
                    cur_field = FIELDS[m.group(1)]
                commit()
    commit()
    seen = set()
    for f in ("for_genuine", "against_genuine"):
        for item in out[f]:
            for c in item["cites"]:
                if c["source"] not in seen:
                    seen.add(c["source"])
                    out["citations"].append(c)
    return out


def _put(out: dict, field: str, value: str, cites: list[dict]) -> None:
    if not value or value in ("なし", "-"):
        return
    uniq = []
    for c in cites:
        if all(c["cited_text"] != u["cited_text"] for u in uniq):
            uniq.append(c)
    if field == "genuine_likelihood":
        out[field] = LEVEL.get(value[:1], out[field])
    elif field in ("for_genuine", "against_genuine"):
        out[field].append({"text": value, "cites": uniq})
    elif field == "how_to_verify":
        out[field] = (out[field] + " " + value).strip()
        out.setdefault("verify_cites", []).extend(uniq)
    else:
        out[field] = value

"""家族への便り(Messages API 版)。夕方の定期便は Managed Agents 版(managed.py)を使う。

今すぐの便りには採点役がいないので、言い切り(「詐欺です」「だまされた」など)が残っていないかを決まった規則でも確かめる。
残っていれば 1 回だけ書き直させ、それでも残るときは、決まった文の便りに差し替える(言い切りを家族に届けない)。
本人が「家族に伝えないで」と言った電話は、夕方の便りに入れない(今すぐの便り=安全に関わるときは別)。
"""
from __future__ import annotations

import json
import re

from .. import config
from ..store import Store
from . import knowledge, llm, schemas


# 言い切り(「詐欺です」「詐欺だ。」「詐欺に違いない」「詐欺と断定した」)と、本人をだまされた人として書く言葉だけを見る。
# 「詐欺と断定はできない」「詐欺だとは限らない」「もし詐欺でしたら」「だまされないように」は通す。
ASSERT = re.compile(r"(?<!「)詐欺(です|でした|だ)(?=[。!！」\s]|$|よ|ね)|詐欺に(違い|間違い)(ない|ありません)|詐欺と断定(する|します|した|しました)"
                    r"|(?<!「)(だまされ|騙され)(た|て(しまっ|い)|ました)")


def _strings(x) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _strings(v)]
    if isinstance(x, list):
        return [s for v in x for s in _strings(v)]
    return []


def violations(letter: dict) -> list[str]:
    """便りの中の言い切り・本人を責める言葉(原則 3・5)。文字列ごとに見る。出典の題は見ない。"""
    texts = _strings({k: v for k, v in letter.items() if k not in ("sources", "source_links", "_meta")})
    return sorted({m.group(0) for t in texts for m in ASSERT.finditer(t)})


def template(urgency: str, calls: list[dict]) -> dict:
    """決まった文の便り(書き直しても言い切りが残ったとき)。"""
    items = []
    for c in calls:
        head = (c.get("decision") or {}).get("headline") or ""
        items.append({"summary": head if head and not ASSERT.search(head) else "気になる電話がありました",
                      "risk": (c.get("karte") or {}).get("risk") or "medium", "why": "くわしいことは、本人に聞いてみてください。"})
    return {"urgency": urgency, "title": "電話のことで、一緒に確かめてほしいことがあります" if urgency == "immediate" else "今日の電話のこと",
            "daily": [], "calls": items, "suggested_talk": "さっき電話があったみたいだけど、どうだった?", "deadline": None,
            "consult": "消費者ホットライン 188。お金やカードの話なら、警察相談専用電話 #9110。",
            "sources": ["rules-hotline-188", "genuine-police-no-phone-investigation"], "closing": "",
            "_meta": {"template": True}}


def write(urgency: str, calls: list[dict], store: Store) -> dict:
    cards = knowledge.by_kind("rules", "technique", "genuine")
    if urgency != "immediate":
        calls = [c for c in calls if c.get("consent") != "no"]     # 本人が「伝えないで」と言った電話は、夕方の便りに入れない
    items = []
    for c in calls:
        items.append({"call_id": c["call_id"], "started": c["started"], "karte": c.get("karte"),
                      "headline": (c.get("decision") or {}).get("headline"), "why": (c.get("decision") or {}).get("why"),
                      "told_by_person": c.get("told_by_person"), "consent": c.get("consent")})
    user = "\n".join([
        f"便りの種類: {urgency}",
        "宛先: 息子の誠さん・孫の健太さん(家族のグループ)",
        "", "今日の暮らしのメモ:", store.memo_digest(),
        "", "電話(通話カルテ):", json.dumps(items, ensure_ascii=False, indent=1),
        "", "家族の文脈:", store.context_text(),
    ])
    system = llm.system_blocks("principles", "letter", extra=knowledge.as_text(cards))
    out, _ = llm.call("letter", config.MODEL_LETTER, system, [{"role": "user", "content": user}], max_tokens=2500,
                      schema=schemas.LETTER, effort="medium", fallback=True)
    bad = violations(out)
    if bad:
        note = f"\n\n(書き直し: 前の案に「{'」「'.join(bad)}」があった。断定や、本人をだまされた人として書く言葉は使わない)"
        try:
            out, _ = llm.call("letter", config.MODEL_LETTER, system, [{"role": "user", "content": user + note}], max_tokens=2500,
                              schema=schemas.LETTER, effort="medium", fallback=True)
        except Exception:
            out = template(urgency, calls)      # 書き直しに失敗しても、決まった文で届ける(今すぐの便りを落とさない)
        if violations(out):
            out = template(urgency, calls)
    out["sources"] = [s for s in out.get("sources", []) if knowledge.card(s)]
    out["source_links"] = [{"id": s, "title": knowledge.card(s)["title"], "url": knowledge.card(s)["source_url"]}
                           for s in out["sources"]]
    return out

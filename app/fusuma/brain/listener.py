"""聞き役(listener): Haiku 5.5 + 構造化出力。通話中に何度も呼ぶので、速く・安く・必ず JSON。"""
from __future__ import annotations

import json

from .. import config
from . import knowledge, llm, schemas


def _system() -> list[dict]:
    cards = knowledge.by_kind("technique", "rules")
    return llm.system_blocks("principles", "listener", extra=knowledge.as_text(cards))


def judge(lines: list[str], ma_line: str = "", prev: dict | None = None, final: bool = False) -> dict:
    head = "【通話が終わりました。最終判定】" if final else "【通話の途中経過】"
    parts = [head, "祖母の発話(時刻順):", *lines]
    if ma_line:
        parts += ["", ma_line]
    if prev:
        keep = {k: prev.get(k) for k in ("track", "stage", "score", "risk", "claimed_caller", "product", "notify_now")}
        parts += ["", "前回の判定: " + json.dumps(keep, ensure_ascii=False)]
    out, _ = llm.call("listener", config.MODEL_LISTENER, _system(),
                      [{"role": "user", "content": "\n".join(parts)}],
                      max_tokens=1500, schema=schemas.LISTENER, effort="low", thinking={"type": "disabled"})
    out["score"] = max(0.0, min(1.0, float(out.get("score", 0))))
    return normalize(out)


SCAM = ["接触", "信頼形成", "要求", "約束", "口止め"]
SOLICIT = ["案内", "強い勧め", "申込の約束", "支払い・定期購入の約束"]


def normalize(out: dict) -> dict:
    """段階名がトラックと食い違ったら、近い段階に寄せる(構造化出力でも意味の整合は保証されないため)。"""
    t, s = out.get("track"), out.get("stage")
    if t == "solicitation" and s not in SOLICIT:
        out["stage"] = "申込の約束" if s in ("約束", "口止め") and any(a["kind"] == "promise" for a in out.get("speech_acts", [])) else "案内"
    elif t == "scam" and s not in SCAM:
        out["stage"] = {"強い勧め": "要求", "申込の約束": "約束", "支払い・定期購入の約束": "約束"}.get(s, "接触")
    elif t == "normal":
        out["stage"] = "なし"
    return out

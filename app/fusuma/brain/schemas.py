"""構造化出力(JSON Schema)。handoff の schemas/ を構造化出力の制約(全項目 required・additionalProperties=false)に合わせたもの。"""
from __future__ import annotations

S = {"type": "string"}
B = {"type": "boolean"}
NUM = {"type": "number"}


def N(t: dict) -> dict:
    return {"anyOf": [t, {"type": "null"}]}


def obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "additionalProperties": False, "required": required or list(props), "properties": props}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


RISK = {"enum": ["low", "medium", "high"]}

STAGES = ["なし", "接触", "信頼形成", "要求", "約束", "口止め", "案内", "強い勧め", "申込の約束", "支払い・定期購入の約束"]

LISTENER = obj({
    "track": {"enum": ["scam", "solicitation", "normal", "unknown"]},
    "stage": {"enum": STAGES},
    "score": NUM,
    "risk": RISK,
    "speech_acts": arr(obj({"t": S, "kind": {"enum": ["disclosure", "promise", "repeat", "pushed_over", "refusal", "backchannel"]}, "text": S})),
    "evidence": arr(obj({"t": S, "note": S})),
    "claimed_caller": N(S),
    "product": N(S),
    "money": N(obj({"amount": N(NUM), "method": N(S)})),
    "subscription": B,
    "deadline": N(S),
    "visit": N(S),
    "secrecy": B,
    "disclosed": arr(S),
    "notify_now": B,
    "reason": S,
    "to_ask": arr(S),
})

KARTE = obj({
    "caller_claimed": S,
    "caller_normalized": S,
    "category": {"enum": ["scam", "solicitation", "acquaintance", "public_office", "unknown"]},
    "product": N(S),
    "amount": N(NUM),
    "subscription": N(B),
    "request": N(S),
    "deadline": N(S),
    "secrecy": B,
    "response": {"enum": ["refused", "promised", "disclosed", "undecided", "unknown"]},
    "stage_max": {"enum": STAGES},
    "risk": RISK,
    "risk_reason": S,
    "linked_calls": arr(S),
    "storyline": N(S),
    "life_link": N(S),
    "contract": N(obj({
        "type": {"enum": ["telephone_solicitation", "door_to_door", "purchase_visit", "mail_order", "other"]},
        "document_received": N(S),
        "cooling_off_note": S,
    })),
    "to_ask": arr(S),
})

DECISION = obj({
    "action": {"enum": ["silent", "evening", "immediate"]},
    "headline": S,
    "why": S,
    "restraint_note": S,
    "karte": KARTE,
    "postcall": obj({"ask": B, "opener": S, "share_consent_needed": B}),
})

POSTCALL_TURN = obj({
    "say": S,
    "intent": {"enum": ["ask_what", "ask_detail", "ask_consent", "reassure", "back_to_daily", "close"]},
    "done": B,
    "consent_to_share": {"enum": ["yes", "no", "unknown"]},
    "told": N(S),
    "diff": N(S),
})

LIFE_MEMO = obj({
    "items": arr(obj({"kind": {"enum": ["did", "want", "concern", "plan"]}, "text": S, "said": S, "secret": B})),
})

LETTER = obj({
    "urgency": {"enum": ["immediate", "evening", "weekly"]},
    "title": S,
    "daily": arr(S),
    "calls": arr(obj({"summary": S, "risk": RISK, "why": S})),
    "suggested_talk": S,
    "deadline": N(S),
    "consult": N(S),
    "sources": arr(S),
    "closing": S,
})

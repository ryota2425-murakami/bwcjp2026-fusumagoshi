"""まとめ役(family): 判断の統合・通話カルテ・電話のあとの会話・暮らしのメモ。"""
from __future__ import annotations

import json

from .. import config
from ..store import Store
from . import knowledge, llm, schemas


def _cards_text() -> str:
    return knowledge.as_text(knowledge.by_kind("rules", "technique", "genuine"))


def decide(call: dict, listener_out: dict, rebuttal_out: dict | None, store: Store) -> dict:
    """通話終了後: 動き(silent/evening/immediate)・カルテ・問いかけを決める。"""
    reb = "(反証役は呼ばなかった: 聞き役の判定で、怪しさが低かった)"
    if rebuttal_out:
        reb = json.dumps({k: rebuttal_out.get(k) for k in ("genuine_likelihood", "alternative", "how_to_verify")}, ensure_ascii=False)
        reb += "\n本物らしい点: " + " / ".join(x["text"] for x in rebuttal_out.get("for_genuine", []))
        reb += "\n本物らしくない点: " + " / ".join(x["text"] for x in rebuttal_out.get("against_genuine", []))
    user = "\n".join([
        f"通話 ID: {call['call_id']} / 開始 {call['started']} / {'着信' if call['direction'] == 'incoming' else '発信'} / {call['duration']} 秒",
        "", "祖母の発話(時刻順):", *call["lines"], "", call.get("ma_line", ""),
        "", "聞き役の最終判定: " + json.dumps(listener_out, ensure_ascii=False),
        "", "反証役の意見: " + reb,
        "", "過去の通話カルテ:", store.karte_digest(exclude=call["call_id"]),
        "", "暮らしのメモ:", store.memo_digest(),
        "", "家族の文脈:", store.context_text(),
    ])
    out, _ = llm.call("family", config.MODEL_FAMILY, llm.system_blocks("principles", "family", extra=_cards_text()),
                      [{"role": "user", "content": user}], max_tokens=3000, schema=schemas.DECISION, effort="medium",
                      fallback=True)
    return out


def postcall_turn(karte: dict, decision: dict, history: list[dict], store: Store) -> dict:
    """電話のあとの会話の次の一言。history: [{"who": "fusuma"|"grandma", "text": ...}]"""
    convo = "\n".join(f"{'ふすまごし' if h['who'] == 'fusuma' else '祖母'}「{h['text']}」" for h in history)
    n_turns = sum(1 for h in history if h["who"] == "fusuma")
    consent = decision.get("postcall", {}).get("share_consent_needed")
    sent = decision.get("action") == "immediate"          # 今すぐの便りは、もう家族に届いている
    plan = {
        1: "今回は 2 回目の発話: 祖母の答えを受け止め、カルテの to_ask から一番大事なことを 1 つだけ聞く(祖母がもう話したことは聞かない)。",
        2: ("今回は 3 回目の発話: 受け止めて、確かめ方を押しつけずに提案し(例: 届いたら一緒に書類を見ようか)、"
            + ("同意は聞かずに、家族にもう知らせたことを正直に伝える(例: 心配だったから、健太にはもう知らせたよ)。" if sent
               else "最後に家族に伝えてよいかを聞く(例: この話、健太にも話しておいていい?)。" if consent
               else "日常の話題に戻して done=true。")),
    }.get(n_turns, "今回が最後の発話: 祖母の答えを受け止め(同意してくれたらお礼)、暮らしのメモの話題に戻して done=true。")
    user = "\n".join([
        "通話カルテ: " + json.dumps(karte, ensure_ascii=False),
        f"まとめ役の動き: {decision.get('action')}" + ("(今すぐの便りを、もう家族に送った)" if sent else ""),
        f"家族に伝える同意の確認が必要か: {False if sent else decision.get('postcall', {}).get('share_consent_needed')}",
        "暮らしのメモ:", store.memo_digest(),
        "", "ここまでの会話:", convo,
        "", f"ふすまごしの発話はここまで {n_turns} 回。{plan}",
    ])
    out, _ = llm.call("postcall", config.MODEL_FAMILY, llm.system_blocks("principles", "postcall"),
                      [{"role": "user", "content": user}], max_tokens=800, schema=schemas.POSTCALL_TURN, effort="low",
                      fallback=True)
    return out


def extract_memo(utterances: list[str], context_text: str = "") -> list[dict]:
    """部屋での会話(祖母の発話)から暮らしのメモを拾う。"""
    user = (("家族の文脈:\n" + context_text + "\n\n" if context_text else "") +
            "祖母がふすまごしに話したこと(時刻順。音声認識なので人名がカタカナになることがある):\n" + "\n".join(utterances) +
            "\n\n暮らしのメモとして残す項目を抜き出す。kind: did=こんなことした / want=やってみたい / concern=気になってる / plan=予定。"
            "said は本人の言葉のまま。体のことは本人の言葉のまま扱い、診断めいたことは書かない。本人が内緒にしたい話は secret=true。")
    out, _ = llm.call("memo", config.MODEL_LISTENER, llm.system_blocks("principles"),
                      [{"role": "user", "content": user}], max_tokens=800, schema=schemas.LIFE_MEMO, effort="low",
                      thinking={"type": "disabled"})
    return out["items"]

"""音声スコア(JSON Lines)と、Claude に渡す 1 行 1 発話のテキスト。

Claude には音声を送らない。送るのはこのテキストだけ(プライバシー台帳で確認できる)。
"""
from __future__ import annotations


def pct(x: float | None) -> str:
    return f"{x*100:+.0f}%" if x is not None else "-"


def utt_line(u: dict, who: str = "祖母") -> str:
    if u.get("backchannel"):
        return f"{u['clock']} {who}「{u['text']}」(あいづち {u['dur']:.1f}s)"
    parts = [f"{u['clock']} {who}「{u['text']}」", f"間{u['pre_pause']:.1f}s"]
    if u.get("f0_rel") is not None:
        parts.append(f"声高{pct(u['f0_rel'])}")
    if u.get("db_rel") is not None:
        parts.append(f"声量{u['db_rel']:+.0f}dB")
    if u.get("rate_rel") is not None:
        parts.append(f"話速{pct(u['rate_rel'])}")
    if u.get("tv"):
        parts.append("(テレビの音の可能性)")
    return " ".join(parts)


def event_line(clock: str, kind: str) -> str:
    label = {"ring": "電話の呼出音", "pickup": "受話器を上げる音", "hangup": "受話器を置く音", "dial": "ダイヤル音(発信)",
             "doorbell": "玄関のチャイム"}.get(kind, kind)
    return f"{clock} [音] {label}"

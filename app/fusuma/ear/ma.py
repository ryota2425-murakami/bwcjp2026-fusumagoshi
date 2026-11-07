"""「間」の指標。片側の声しか聞かないので、祖母が黙っている時間 ≒ 相手が話している時間とみなす。

相手の言葉は再構成しない。わかるのは会話の「形」だけ:
  誰が場を握っているか(話していた時間の割合)、沈黙の長さ、あいづちの連続、断りの語が消えていくか。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

REFUSAL = re.compile(r"(結構です|けっこうです|いりません|要りません|いらない|考えておき|相談|聞いてみないと|かけ直し|掛け直し|やめておき|お断り|今はちょっと|失礼します)")
YES = re.compile(r"^(はい|ええ|うん)")


@dataclass
class MaTracker:
    call_start: float = 0.0
    utts: list[dict] = field(default_factory=list)

    def add(self, u: dict) -> None:
        self.utts.append(u)

    def summary(self, now: float) -> dict:
        if not self.utts:
            return {}
        elapsed = max(1e-6, now - self.call_start)
        talk = sum(u["dur"] for u in self.utts)
        gaps = [u["pre_pause"] for u in self.utts[1:]]
        half = len(self.utts) // 2 or 1
        ref_early = sum(1 for u in self.utts[:half] if REFUSAL.search(u["text"]))
        ref_late = sum(1 for u in self.utts[half:] if REFUSAL.search(u["text"]))
        streak = best = 0
        for u in self.utts:
            if u.get("backchannel") or YES.match(u["text"]):
                streak += 1
                best = max(best, streak)
            else:
                streak = 0
        dbs = [u["db_rel"] for u in self.utts if u.get("db_rel") is not None and not u.get("backchannel")]
        trend = round((sum(dbs[-3:]) / len(dbs[-3:])) - (sum(dbs[:3]) / len(dbs[:3])), 1) if len(dbs) >= 4 else None
        return {
            "elapsed": round(elapsed, 1),
            "self_ratio": round(talk / elapsed, 2),                 # 祖母が話していた割合
            "other_ratio_est": round(1 - talk / elapsed, 2),        # 相手が話していたと推定される割合
            "max_gap": round(max(gaps), 1) if gaps else 0.0,
            "long_gaps": sum(1 for g in gaps if g >= 5.0),
            "yes_streak": best,
            "refusal_early": ref_early,
            "refusal_late": ref_late,
            "volume_trend_db": trend,                               # 前半→後半の声量の変化
            "n_utts": len(self.utts),
        }


def summary_line(clock_str: str, s: dict) -> str:
    if not s:
        return ""
    parts = [f"[間の様子 {clock_str}]",
             f"祖母が話していた時間 {int(s['self_ratio']*100)}%",
             f"相手が話していたと推定される時間 {int(s['other_ratio_est']*100)}%",
             f"最長の沈黙 {s['max_gap']}s",
             f"5秒以上の沈黙 {s['long_gaps']}回",
             f"「はい」の連続 最大{s['yes_streak']}",
             f"断りの語 前半{s['refusal_early']}→後半{s['refusal_late']}"]
    if s.get("volume_trend_db") is not None:
        parts.append(f"声量の変化 {s['volume_trend_db']:+.1f}dB")
    return " / ".join(parts)

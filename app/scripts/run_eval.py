"""簡易評価: 全通話シナリオを 耳 → 脳 に流し、期待と比べる。キーワード検知(自作の比較対象)とも並べる。

- 耳の出力(Claude に渡すテキスト)はキャッシュする。プロンプトを変えたら脳だけを流し直せる(hooks から呼ぶ)。
- 統計的な主張はしない。「N 件中 M 件」で示す。
  python app/scripts/run_eval.py --tag v1            # 全件
  python app/scripts/run_eval.py --tag quick --ids S05 S13   # 一部
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fusuma import config  # noqa: E402
from fusuma.brain import family, listener, llm, rebuttal  # noqa: E402
from fusuma.ear.pipeline import Ear  # noqa: E402
from fusuma.orchestrator import needs_rebuttal  # noqa: E402
from fusuma.store import Store  # noqa: E402

EVAL = config.RUNS / "eval"
SCEN = [s for s in json.loads(config.SCENARIOS.read_text())["scenarios"] if s["kind"] == "call" and not s.get("demo_only")]   # P01 はデモ用(評価には入れない)
# 比較対象: 単純なキーワード検知(自作。既存サービスの実際の判定ロジックは非公開なので、これは一般的な作り方の例)
KEYWORDS = ["警察", "銀行", "信用金庫", "口座", "暗証番号", "キャッシュカード", "カード", "ATM", "還付", "振り込", "振込", "未納",
            "裁判", "今日中", "誰にも言わない", "通帳", "印鑑", "現金", "封筒", "取りに来る", "お金"]


def ear_lines(sc: dict, force: bool = False) -> dict:
    p = EVAL / f"ear_{sc['id']}.json"
    shipped = config.ROOT / "eval" / "ear_cache" / f"ear_{sc['id']}.json"   # 公開リポジトリに同梱したキャッシュ
    if not force:
        for q in (p, shipped):
            if q.exists():
                return json.loads(q.read_text())
    ended: list[dict] = []
    h, m = map(int, sc["time"].split(":"))
    start = (datetime.now() + timedelta(days=sc.get("day_offset", 0))).replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(seconds=10)
    ear = Ear(lambda e: ended.append(e) if e["type"] == "state" and e["state"] == "ended" else None, start_wall=start)
    ear.run_file(config.SCENARIO_AUDIO / f"{sc['id']}_16k.wav")
    ev = ended[-1]
    out = {"call_id": ev["call_id"], "started": ev["started"], "direction": ev["direction"], "duration": ev["duration"],
           "lines": ev["lines"], "ma": ev["ma"], "ma_line": ev["ma_line"]}
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def keyword_alert(lines: list[str]) -> list[str]:
    text = " ".join(re.findall(r"祖母「(.*?)」", " ".join(lines)))
    return [k for k in KEYWORDS if k in text]


def brain(sc: dict, call: dict, store: Store) -> dict:
    t0 = time.time()
    lo = listener.judge(call["lines"], call["ma_line"], final=True)
    reb = rebuttal.review([l for l in call["lines"] if "祖母「" in l], store.context_text()) if needs_rebuttal(lo) else None
    dec = family.decide(call, lo, reb, store)
    return {"listener": lo, "rebuttal": reb, "decision": dec, "sec": round(time.time() - t0, 1)}


def score(sc: dict, r: dict, kw: list[str]) -> dict:
    exp = sc["expected"]
    lo, dec = r["listener"], r["decision"]
    act = dec["action"]
    genuine = exp["track"] == "normal"
    risky = exp["risk"] in ("medium", "high")
    return {
        "id": sc["id"], "title": sc["title"], "expected_risk": exp["risk"], "expected_notify": exp["notify_now"],
        "track": lo["track"], "risk": lo["risk"], "score": lo["score"], "action": act,
        "genuine_likelihood": (r["rebuttal"] or {}).get("genuine_likelihood"),
        "kw_hits": kw, "kw_alert": bool(kw),
        # 判定が合っているか(リスクの段階)
        "risk_ok": lo["risk"] == exp["risk"] or (exp["risk"] == "medium" and lo["risk"] in ("medium", "high") and act != "silent") ,
        # 動きが合っているか: 本物 → 黙る / 怪しい → 知らせる / 今すぐの要否
        "action_ok": (act == "silent") if genuine else ((act == "immediate") == exp["notify_now"] and act != "silent") if risky
                     else act in ("silent", "evening"),
        "false_alarm": genuine and act != "silent",
        "kw_false_alarm": genuine and bool(kw),
        "missed": risky and act == "silent",
        "kw_missed": risky and not kw,
        "headline": dec["headline"], "restraint_note": dec["restraint_note"], "sec": r["sec"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=datetime.now().strftime("%m%d-%H%M"))
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--force-ear", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    EVAL.mkdir(parents=True, exist_ok=True)
    scs = [s for s in SCEN if not args.ids or s["id"] in args.ids]
    for sc in scs:                                   # 耳は順に(whisper-server を共有するので)
        ear_lines(sc, force=args.force_ear)
    store = Store(EVAL / "eval.sqlite3")             # 評価用の空の記憶(家族の文脈だけ)
    store.reset()
    spent = {"usd": 0.0, "tokens": {}}

    def _count(rec: dict) -> None:            # この評価の呼び出しだけを数える(費用とトークン)
        spent["usd"] += rec.get("usd", 0.0)
        tk = spent["tokens"].setdefault(rec.get("model", "?"), {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0})
        for k in tk:
            tk[k] += rec.get(k, 0) or 0
    llm.on_call(_count)

    def one(sc):
        call = ear_lines(sc)
        r = brain(sc, call, store)
        row = score(sc, r, keyword_alert(call["lines"]))
        print(f"{sc['id']} 期待 {sc['expected']['risk']:6} → {row['risk']:6} {row['action']:9} | KW {'警報' if row['kw_alert'] else '-':3} "
              f"{'OK ' if row['action_ok'] else 'NG '} {sc['title']}", flush=True)
        return row, r

    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(one, scs))
    rows = [r for r, _ in results]
    genuine = [r for r in rows if r["expected_risk"] == "low" and r["id"] in ("S10", "S11", "S12", "S13", "S14")]
    risky = [r for r in rows if r["expected_risk"] in ("medium", "high")]
    summary = {
        "tag": args.tag, "n": len(rows), "action_ok": sum(r["action_ok"] for r in rows), "risk_ok": sum(r["risk_ok"] for r in rows),
        "genuine_n": len(genuine), "false_alarm": sum(r["false_alarm"] for r in genuine), "kw_false_alarm": sum(r["kw_false_alarm"] for r in genuine),
        "risky_n": len(risky), "missed": sum(r["missed"] for r in risky), "kw_missed": sum(r["kw_missed"] for r in risky),
        "usd": round(spent["usd"], 4), "tokens": spent["tokens"], "prompt_files": sorted(p.name for p in config.PROMPTS.glob("*.md")),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    out = EVAL / f"result_{args.tag}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows, "raw": [r for _, r in results]}, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"→ {out}")


if __name__ == "__main__":
    main()

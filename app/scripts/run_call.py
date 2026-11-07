"""シナリオ音声を、耳 → 脳(Claude)まで通しで処理する(オフライン・同期)。

python app/scripts/run_call.py S00 R01 S05      # 順に処理して記憶に積む
python app/scripts/run_call.py --reset S05      # 記憶を消してから
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fusuma import config  # noqa: E402
from fusuma.brain import family, llm  # noqa: E402
from fusuma.ear.pipeline import Ear  # noqa: E402
from fusuma.orchestrator import Fusuma  # noqa: E402
from fusuma.store import Store  # noqa: E402

SCEN = {s["id"]: s for s in json.loads(config.SCENARIOS.read_text())["scenarios"]}


def start_wall(sc: dict, base: datetime) -> datetime:
    h, m = map(int, sc["time"].split(":"))
    d = (base + timedelta(days=sc.get("day_offset", 0))).replace(hour=h, minute=m, second=0, microsecond=0)
    return d - timedelta(seconds=10)


def run_room(sid: str, store: Store, ear_events: list, base: datetime) -> list[dict]:
    sc = SCEN[sid]
    utts = []
    ear = Ear(lambda e: utts.append(e) if e["type"] == "room_utt" else None, start_wall=start_wall(sc, base))
    ear.open_room_listen(10_000, tag="chat")
    ear.run_file(config.SCENARIO_AUDIO / f"{sid}_16k.wav")
    lines = [f"{u['clock']} 祖母「{u['text']}」" for u in utts]
    items = family.extract_memo(lines, store.context_text())
    ts = start_wall(sc, base).isoformat(timespec="seconds")
    for it in items:
        store.add_memo(it["kind"], it["text"], it["said"], it["secret"], source=sid, ts=ts)
    return items


def run_one(sid: str, store: Store, base: datetime, verbose: bool = True) -> dict:
    sc = SCEN[sid]
    events: list[dict] = []
    if sc["kind"] == "room":
        items = run_room(sid, store, events, base)
        if verbose:
            for it in items:
                print(f"  暮らしのメモ [{it['kind']}] {it['text']}(「{it['said']}」){' 内緒' if it['secret'] else ''}")
        return {"id": sid, "memo": items}
    results: list[dict] = []
    fz = Fusuma(store, emit=lambda e: events.append(e), sync=True)
    fz.scenario_tag = sid
    fz.on_finalized = results.append
    ear = Ear(fz.on_ear, start_wall=start_wall(sc, base))
    fz.ear = ear
    t0 = time.time()
    ear.run_file(config.SCENARIO_AUDIO / f"{sid}_16k.wav")
    r = results[-1] if results else {}
    if verbose:
        for e in events:
            if e["type"] == "utt":
                print("  " + e["line"])
        lo, dec = r.get("listener") or {}, r.get("decision") or {}
        print(f"  聞き役: track={lo.get('track')} stage={lo.get('stage')} score={lo.get('score')} risk={lo.get('risk')} notify_now={lo.get('notify_now')}")
        if r.get("rebuttal"):
            rb = r["rebuttal"]
            print(f"  反証役: 本物の可能性={rb['genuine_likelihood']} 引用{len(rb['citations'])}件 確かめ方={rb['how_to_verify'][:60]}")
        print(f"  まとめ役: action={dec.get('action')} 「{dec.get('headline')}」")
        print(f"    抑制: {dec.get('restraint_note')}")
        k = r.get("karte") or {}
        print(f"    カルテ: {k.get('caller_normalized')} / {k.get('category')} / {k.get('product')} / 対応 {k.get('response')} / linked {k.get('linked_calls')}")
        if k.get("storyline"):
            print(f"    経緯: {k['storyline']}")
        if k.get("life_link"):
            print(f"    暮らしとの関連: {k['life_link']}")
        print(f"  ({time.time()-t0:.0f}s, 累計 ${llm.spent_usd():.3f})")
    return {"id": sid, **r}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    store = Store()
    if args.reset:
        for cid in store.pending_transcripts():   # 消す前に、残っている文字起こしを台帳からも伏せる(画面のログはサーバーが伏せる)
            store.purge_transcript(cid)
            llm.redact(cid)
        store.reset()
    base = datetime.now()
    out = []
    for sid in args.ids:
        print(f"== {sid} {SCEN[sid]['title']}")
        out.append(run_one(sid, store, base))
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()

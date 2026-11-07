"""記憶(端末側の正本): SQLite。通話カルテ・暮らしのメモ・家族の文脈・便り。

- 音声は保存しない。文字起こし(lines)は電話のあとの会話が終わるまでの一時保存で、終わったら消す。
  消すときは、聞き役の判定に入った発話の引用(speech_acts の text・evidence・disclosed など)と反証役の原文も除く。
- Managed Agents の記憶ストアへは、カルテと暮らしのメモ(要約)だけを同期する。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import config

_lock = threading.RLock()     # 1 本の接続を複数のスレッドで使うので、読むときも書くときも通す

# 聞き役の判定のうち、発話の原文や言い換えが入りうる項目(文字起こしと一緒に消す)
LISTENER_VERBATIM = ("evidence", "disclosed", "reason", "to_ask")


def slim_rebuttal(reb: dict | None) -> dict | None:
    """反証役の結果から、発話の引用が入る項目(本物らしい点・らしくない点・別の説明・確かめ方・原文)を除く。
    残すのは「本物らしさ」の見立てと、引いた知識カードの題だけ(まとめ役はもう読み終えている)。"""
    if not reb:
        return reb
    return {"genuine_likelihood": reb.get("genuine_likelihood"),
            "citations": [{"source": c.get("source"), "title": c.get("title")} for c in reb.get("citations") or []]}


def slim_listener(lo: dict | None) -> dict | None:
    """聞き役の判定から原文に近い項目を除き、段階・危険度・発話行為の種類だけを残す。"""
    if not lo:
        return lo
    out = {k: v for k, v in lo.items() if k not in LISTENER_VERBATIM and k != "speech_acts"}
    out["speech_acts"] = [{"t": a.get("t"), "kind": a.get("kind")} for a in lo.get("speech_acts") or []]
    return out

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  call_id TEXT PRIMARY KEY, started TEXT, direction TEXT, duration REAL,
  lines TEXT, ma TEXT, listener TEXT, rebuttal TEXT, decision TEXT, karte TEXT,
  action TEXT, risk TEXT, told_by_person TEXT, diff TEXT, consent TEXT,
  transcript_purged INTEGER DEFAULT 0, scenario TEXT, created TEXT
);
CREATE TABLE IF NOT EXISTS life_memo (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, text TEXT, said TEXT, secret INTEGER, source TEXT
);
CREATE TABLE IF NOT EXISTS family_context (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS letters (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, urgency TEXT, body TEXT, via TEXT, call_ids TEXT
);
"""

DEFAULT_CONTEXT = {
    "family": "孫の健太(関東在住・34歳)が便りをいちばんよく読み、電話をかける。息子の誠(関東在住)も同じ家族のグループで読む。",
    "schedule": "11月10日(月)10:00 みどり整形外科の予約(膝)。体操教室は毎週火曜日。",
    "deliveries": "通販の荷物は、ふだんはほとんど頼まない。",
    "procedures": "先週、みどり信用金庫の窓口で定期預金の手続きをした。先月、自転車の盗難届を警察署に出した。",
    "acquaintances": "友人のよし子さん(体操教室の仲間)。",
    "sharing_rule": "家族に伝える範囲は本人と決めてある: 暮らしの様子と、心配な電話。本人が内緒と言った話は伝えない。お金やカードが今日動くような安全に関わる話は、先に家族へ知らせ、そのことを電話のあとに本人へ正直に伝える。",
}


GONE = "(消去済み)"


def redact_event(ev: dict) -> dict:
    """1 つのイベントから、文字起こしにあたる中身を伏せる(種類・時刻・数値は残す)。"""
    before = json.dumps(ev, ensure_ascii=False, sort_keys=True, default=str)
    ev = dict(ev)
    t = ev.get("type")
    if t in ("utt", "room_utt"):
        for k in ("text", "line"):
            if k in ev:
                ev[k] = GONE
    elif t == "state" and "lines" in ev:
        ev["lines"] = []
    elif t == "listener":
        ev["out"] = slim_listener(ev.get("out"))
    elif t == "rebuttal":
        ev["out"] = slim_rebuttal(ev.get("out"))
    elif t == "dialog":
        ev["history"] = [{"who": h.get("who"), "text": GONE} for h in ev.get("history") or []]
        if ev.get("turn"):
            ev["turn"] = {k: ev["turn"].get(k) for k in ("done", "consent_to_share")}
    elif t == "speak":
        ev["text"] = GONE
    elif t == "claude":
        ev["payload_preview"] = GONE
    if json.dumps(ev, ensure_ascii=False, sort_keys=True, default=str) != before:
        ev["redacted"] = True                  # 中身を伏せたイベントだけ(判断・カルテのイベントはそのまま)
    return ev


class Store:
    def __init__(self, path: Path = config.DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        if not self.db.execute("SELECT 1 FROM family_context LIMIT 1").fetchone():
            for k, v in DEFAULT_CONTEXT.items():
                self.db.execute("INSERT INTO family_context VALUES (?,?)", (k, v))
            self.db.commit()

    # ---- calls ----
    def upsert_call(self, call_id: str, **fields) -> None:
        cols = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in fields.items()}
        with _lock:
            if self.db.execute("SELECT 1 FROM calls WHERE call_id=?", (call_id,)).fetchone():
                sets = ", ".join(f"{k}=?" for k in cols)
                self.db.execute(f"UPDATE calls SET {sets} WHERE call_id=?", (*cols.values(), call_id))
            else:
                cols["created"] = datetime.now().isoformat(timespec="seconds")
                names = ", ".join(["call_id", *cols])
                qs = ", ".join("?" * (len(cols) + 1))
                self.db.execute(f"INSERT INTO calls ({names}) VALUES ({qs})", (call_id, *cols.values()))
            self.db.commit()

    def call(self, call_id: str) -> dict | None:
        with _lock:
            r = self.db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
        return _row(r) if r else None

    def calls(self, limit: int = 50) -> list[dict]:
        with _lock:
            rows = self.db.execute("SELECT * FROM calls ORDER BY started DESC LIMIT ?", (limit,)).fetchall()
        return [_row(r) for r in rows]

    def pending_transcripts(self) -> list[str]:
        """文字起こしがまだ消されていない通話(起動し直したときに片づける)。"""
        with _lock:
            return [r["call_id"] for r in self.db.execute("SELECT call_id FROM calls WHERE transcript_purged=0 OR transcript_purged IS NULL")]

    def purge_transcript(self, call_id: str) -> None:
        """文字起こしを消す。残すのは通話カルテ(要約)・まとめ役の判断・聞き役の判定の要約だけ。"""
        with _lock:
            c = self.call(call_id) or {}
            reb = c.get("rebuttal")
            self.db.execute("UPDATE calls SET lines=NULL, listener=?, rebuttal=?, transcript_purged=1 WHERE call_id=?",
                            (json.dumps(slim_listener(c.get("listener")), ensure_ascii=False) if c.get("listener") else None,
                             json.dumps(slim_rebuttal(reb), ensure_ascii=False) if reb else None,
                             call_id))
            self.db.commit()

    def karte_digest(self, exclude: str | None = None, limit: int = 12) -> str:
        """過去の通話カルテの要約(まとめ役のプロンプト用)。"""
        out = []
        for c in self.calls(limit + 1):
            if c["call_id"] == exclude or not c.get("karte"):
                continue
            k = c["karte"]
            out.append(f"- [{c['call_id']}] {c['started']} 名乗り:{k.get('caller_normalized') or k.get('caller_claimed')} "
                       f"種類:{k.get('category')} 商品:{k.get('product')} 対応:{k.get('response')} 危険度:{k.get('risk')} "
                       f"理由:{k.get('risk_reason')}")
        return "\n".join(out[:limit]) or "(過去のカルテなし)"

    # ---- life memo ----
    def add_memo(self, kind: str, text: str, said: str, secret: bool, source: str, ts: str | None = None) -> None:
        with _lock:
            self.db.execute("INSERT INTO life_memo (ts, kind, text, said, secret, source) VALUES (?,?,?,?,?,?)",
                            (ts or datetime.now().isoformat(timespec="seconds"), kind, text, said, int(secret), source))
            self.db.commit()

    def memos(self, include_secret: bool = False) -> list[dict]:
        q = "SELECT * FROM life_memo" + ("" if include_secret else " WHERE secret=0") + " ORDER BY ts DESC LIMIT 50"
        with _lock:
            return [dict(r) for r in self.db.execute(q)]

    def memo_digest(self) -> str:
        label = {"did": "こんなことした", "want": "やってみたい", "concern": "気になってる", "plan": "予定"}
        ms = self.memos()
        return "\n".join(f"- {m['ts'][:16]} [{label.get(m['kind'], m['kind'])}] {m['text']}(本人「{m['said']}」)" for m in ms) or "(なし)"

    # ---- context ----
    def context(self) -> dict:
        with _lock:
            return {r["key"]: r["value"] for r in self.db.execute("SELECT * FROM family_context")}

    def context_text(self) -> str:
        return "\n".join(f"- {k}: {v}" for k, v in self.context().items())

    # ---- letters ----
    def add_letter(self, urgency: str, body: dict, via: str, call_ids: list[str]) -> int:
        with _lock:
            cur = self.db.execute("INSERT INTO letters (ts, urgency, body, via, call_ids) VALUES (?,?,?,?,?)",
                                  (datetime.now().isoformat(timespec="seconds"), urgency, json.dumps(body, ensure_ascii=False), via,
                                   json.dumps(call_ids)))
            self.db.commit()
            return cur.lastrowid

    def letters(self, limit: int = 20) -> list[dict]:
        with _lock:
            rows = self.db.execute("SELECT * FROM letters ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_row(r) for r in rows]

    def reset(self) -> None:
        with _lock:
            for t in ("calls", "life_memo", "letters"):
                self.db.execute(f"DELETE FROM {t}")
            self.db.commit()


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in ("lines", "ma", "listener", "rebuttal", "decision", "karte", "body", "call_ids"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d

"""MCP サーバー(stdio): ふすまごしの記憶(通話カルテ・暮らしのメモ・費用台帳)を、開発中の Claude Code から読み取り専用で引く。

使い道: 「S05 のカルテで、聞き役と反証役の意見が割れた理由を見て」「誤警報が出た通話を探して」など、
評価やプロンプト改善のときに、記憶の中身を Claude Code が直接確かめられるようにする。音声と文字起こしは返さない。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer  # mcp 2.x(1.x の FastMCP)

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))
from fusuma import config  # noqa: E402
from fusuma.store import slim_listener  # noqa: E402

mcp = MCPServer("fusuma-karte")


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _karte_row(r: sqlite3.Row) -> dict:
    d = {k: r[k] for k in ("call_id", "started", "direction", "duration", "action", "risk", "told_by_person", "consent")}
    for k in ("karte", "decision", "listener"):
        d[k] = json.loads(r[k]) if r[k] else None
    d["listener"] = slim_listener(d["listener"])     # 発話の引用(speech_acts の text・evidence など)は返さない
    return d


@mcp.tool()
def list_calls(limit: int = 20) -> list[dict]:
    """最近の通話(新しい順)。ID・日時・端末の判断(action)・危険度だけを返す。"""
    with _db() as db:
        rows = db.execute("SELECT call_id, started, action, risk, scenario FROM calls ORDER BY started DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


@mcp.tool()
def get_karte(call_id: str) -> dict:
    """1 通話のカルテ・まとめ役の判断・聞き役の最終判定。文字起こしは含めない。"""
    with _db() as db:
        r = db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
        return _karte_row(r) if r else {"error": "not found"}


@mcp.tool()
def search_kartes(query: str) -> list[dict]:
    """カルテの名乗り・商品・理由・経緯に query を含む通話を探す(例: 「健康」「警察」)。"""
    with _db() as db:
        rows = db.execute("SELECT * FROM calls WHERE karte LIKE ? ORDER BY started DESC LIMIT 20", (f"%{query}%",))
        return [_karte_row(r) for r in rows]


@mcp.tool()
def life_memos() -> list[dict]:
    """暮らしのメモ(祖母が話したこと)。本人が内緒と言った項目は返さない(Claude Code にも渡さない)。"""
    with _db() as db:
        return [dict(r) for r in db.execute("SELECT ts, kind, text, said FROM life_memo WHERE secret=0 ORDER BY ts DESC")]


@mcp.tool()
def api_spend() -> dict:
    """Claude API の利用額(費用台帳の合計と役割ごとの内訳)。"""
    p = config.RUNS / "ledger.jsonl"
    by: dict[str, float] = {}
    for line in (p.read_text().splitlines() if p.exists() else []):
        r = json.loads(line)
        by[r["role"]] = by.get(r["role"], 0) + r.get("usd", 0)
    return {"total_usd": round(sum(by.values()), 4), "by_role": {k: round(v, 4) for k, v in by.items()}, "budget_usd": config.BUDGET_USD}


if __name__ == "__main__":
    mcp.run()

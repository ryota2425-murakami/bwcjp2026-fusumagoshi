"""Claude 呼び出しの共通部: 認証・費用台帳(予算の上限)・プライバシー台帳(Claude に送った中身)。

- 認証は Anthropic SDK の既定(ANTHROPIC_API_KEY か `ant auth login` のプロファイル)。
- Claude に送るのはテキストだけ。音声のバイト列やファイルを送る経路はない(auditor と hooks で検査)。
- 送った中身は通話ごとの印(REF)をつけて台帳に残し、その通話の文字起こしを消すときに redact() で中身を伏せる
  (役割・モデル・時刻・文字数は残す)。
"""
from __future__ import annotations

import contextvars
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from .. import config

_client: anthropic.Anthropic | None = None
_lock = threading.Lock()
LEDGER = config.RUNS / "ledger.jsonl"          # 費用
PRIVACY = config.RUNS / "privacy_ledger.jsonl"  # 送った中身(テキストのみ)
_listeners: list = []                           # UI へ流すフック
REF: contextvars.ContextVar[str | None] = contextvars.ContextVar("fusuma_ref", default=None)  # どの通話のために送ったか
_purged: set[str] = set()                       # 文字起こしを消した通話(あとから届いた記録も中身を伏せる)


def _append(path: Path, line: str) -> None:
    """1 行足す。前の行が途中で切れていたら(改行がなければ)、改行してから書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab+") as f:
        f.seek(0, 2)
        if f.tell() > 0:
            f.seek(-1, 2)
            if f.read(1) != b"\n":
                f.write(b"\n")
        f.write((line + "\n").encode("utf-8"))


class BudgetExceeded(RuntimeError):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=3, timeout=120)
    return _client


def on_call(fn) -> None:
    """呼び出しのたびに UI へ通知するフックを登録する。"""
    _listeners.append(fn)


def spent_usd() -> float:
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text().splitlines():
        try:
            total += json.loads(line)["usd"]
        except Exception:
            pass
    return total


def _cost(model: str, usage) -> float:
    pin, pout, pcache = config.PRICES.get(model, (4.0, 20.0, 0.2))
    inp = (usage.input_tokens or 0) + 1.25 * (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (inp * pin + cached * pcache + (usage.output_tokens or 0) * pout) / 1_000_000


def _text_of(messages: list[dict], system: Any) -> str:
    def flat(c):
        if isinstance(c, str):
            return c
        out = []
        for b in c:
            if b.get("type") == "text":
                out.append(b["text"])
            elif b.get("type") == "search_result":
                out.append(f"[検索結果:{b['title']}] " + " ".join(x["text"] for x in b["content"]))
            else:
                raise ValueError(f"テキスト以外のブロックは送らない: {b.get('type')}")
        return "\n".join(out)
    sys_text = system if isinstance(system, str) else "\n".join(b["text"] for b in (system or []))
    return "SYSTEM:\n" + sys_text[:400] + "…\n\n" + "\n\n".join(f"{m['role'].upper()}:\n{flat(m['content'])}" for m in messages)


def call(role: str, model: str, system: Any, messages: list[dict], *, max_tokens: int = 2000,
         schema: dict | None = None, effort: str | None = None, thinking: dict | None = None,
         tools: list | None = None, fallback: bool = False) -> tuple[Any, Any]:
    """Claude を呼ぶ。schema を渡すと構造化出力(JSON)を返す。戻り値は (parsed or text, response)。"""
    spent = spent_usd()
    if spent >= config.BUDGET_USD:
        raise BudgetExceeded(f"予算 ${config.BUDGET_USD} に達しました(使用 ${spent:.2f})")
    payload_text = _text_of(messages, system)   # 音声などテキスト以外が混ざっていればここで止まる
    kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages,
                              "cache_control": {"type": "ephemeral"}}
    oc: dict[str, Any] = {}
    if effort:
        oc["effort"] = effort
    if schema:
        oc["format"] = {"type": "json_schema", "schema": schema}
    if oc:
        kwargs["output_config"] = oc
    if thinking:
        kwargs["thinking"] = thinking
    if tools:
        kwargs["tools"] = tools
    t0 = time.time()
    if fallback and model in ("claude-sonnet-5-5", "claude-opus-5-5"):
        resp = client().beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    else:
        resp = client().messages.create(**kwargs)
    dt = time.time() - t0
    usd = _cost(resp.model if resp.model in config.PRICES else model, resp.usage)
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "role": role, "model": model,
           "served_model": resp.model, "sec": round(dt, 2),          # server-side fallbacks で別のモデルが答えたら分かるように
           "in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
           "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
           "cache_write": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
           "usd": round(usd, 6), "stop": resp.stop_reason, "ref": REF.get()}
    with _lock:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        late = rec["ref"] in _purged           # 消したあとに戻ってきた呼び出し(中身は残さない)
        # audio_bytes は常に 0: _text_of が text / search_result 以外のブロックを送信前に拒否する
        _append(PRIVACY, json.dumps({"ts": rec["ts"], "role": role, "model": model, "to": "messages", "audio_bytes": 0,
                                     "chars": len(payload_text), "text": "" if late else payload_text, "ref": rec["ref"],
                                     **({"purged": True} if late else {})}, ensure_ascii=False))
    for fn in _listeners:
        try:
            fn({**rec, "payload_preview": payload_text[-1600:], "chars": len(payload_text), "audio_bytes": 0, "spent": round(spent + usd, 4)})
        except Exception:
            pass
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"{role}: refusal ({getattr(resp, 'stop_details', None)})")
    if schema:
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text), resp
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, resp


def load_prompt(name: str) -> str:
    return (config.PROMPTS / f"{name}.md").read_text()


def system_blocks(*names: str, extra: str | None = None) -> list[dict]:
    """原則+役割のプロンプト(安定部分)をキャッシュ対象のブロックにする。"""
    text = "\n\n".join(load_prompt(n) for n in names)
    blocks = [{"type": "text", "text": text}]
    if extra:
        blocks.append({"type": "text", "text": extra})
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def record_sent(role: str, text: str, to: str, ref: str | None = None) -> None:
    """Messages API 以外(Managed Agents の記憶ストアなど)へ送った中身も、同じ台帳に残す。"""
    with _lock:
        _append(PRIVACY, json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "role": role, "to": to, "audio_bytes": 0,
                                     "chars": len(text), "text": text, "ref": ref}, ensure_ascii=False))


def redact(ref: str) -> int:
    """その通話のために送った中身を台帳から伏せる(役割・時刻・文字数は残す)。伏せた件数を返す。"""
    with _lock:
        _purged.add(ref)
        if not PRIVACY.exists():
            return 0
        rows, n = [], 0
        for line in PRIVACY.read_text(errors="replace").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)          # 壊れた行があっても、ほかの行は伏せ続ける
                continue
            if r.get("ref") == ref and r.get("text"):
                r["text"], r["purged"] = "", True
                n += 1
            rows.append(json.dumps(r, ensure_ascii=False))
        tmp = PRIVACY.with_suffix(".tmp")
        tmp.write_text("".join(x + "\n" for x in rows))
        tmp.replace(PRIVACY)
    return n

"""耳のイベントを受けて、脳(Claude)を呼び、記憶に残し、電話のあとに話しかける。

    通話中   : 発話を貯め、10 発話 or 60 秒ごとに聞き役(Haiku)で途中経過。端末は光らない・話さない。
    通話終了 : 聞き役の最終判定 → (怪しければ)反証役(Sonnet・独立文脈・出典つき) → まとめ役(Sonnet)
               → 通話カルテ → 必要なら「今すぐの便り」。
    少しあと : 電話のあとの問いかけ(問いかけが必要なときだけ)→ 祖母の答え → カルテに反映 → 文字起こしを消す。

文字起こしは、どの終わり方(聞き取りが終わった・祖母が答えない・別の電話が来た・途中で失敗した)でも消す。
消すときは、Claude に送った中身の台帳(その通話の分)と、画面・イベントログの原文も伏せる(_purge)。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable

from . import config
from .brain import family, letters, listener, llm, rebuttal
from .store import Store


class SilenceViolation(RuntimeError):
    """通話中に話そうとした(設計上起きてはいけない)。"""


def needs_rebuttal(lo: dict) -> bool:
    """反証役(本物の可能性を独立に考える役)を呼ぶか。種類が分からない電話でも、怪しさがあれば呼ぶ。"""
    return lo.get("track") in ("scam", "solicitation", "unknown") and (lo.get("risk") != "low" or lo.get("score", 0) >= 0.3)


class Fusuma:
    def __init__(self, store: Store, emit: Callable[[dict], None], speak: Callable[[str], float] | None = None,
                 ear=None, sync: bool = False, postcall_delay: float = config.POST_CALL_DELAY_SEC):
        self.store = store
        self.emit = emit
        self._speak = speak
        self.ear = ear
        self.sync = sync
        self.postcall_delay = postcall_delay
        self.live: dict[str, dict] = {}
        self.dialog: dict | None = None
        self.scenario_tag: str | None = None
        self.on_finalized: Callable[[dict], None] | None = None
        self.on_spoken: Callable[[str], None] | None = None
        self._answer_buf: list[str] = []
        self._answer_timer: threading.Timer | None = None
        self._answer_t0 = 0.0
        self._answer_q = -1
        self._buf_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self.on_purge: list[Callable[[str], None]] = []     # 文字起こしを消すとき、画面・ログ側も伏せるフック
        self._say_lock = threading.Lock()                    # 声が 2 つ重ならないように
        self._latest_cid: str | None = None                  # いちばん新しく終わった電話
        self._closed: tuple[str, float] | None = None        # 直前に閉じた会話(通話 ID と時刻)

    # ---------- 端末が話す(唯一の出口) ----------
    def may_speak(self) -> bool:
        """いま声を出してよいか。電話が鳴っている・通話中なら出さない。
        耳がない(通話中かどうか分からない)のに音を出す設定なら、話さない側に倒す。"""
        if self.ear is None:
            return self._speak is None             # 音を出さない(文字だけの)シミュレーションだけ許す
        return self.ear.state not in ("ringing", "dialing", "in_call")

    def say(self, text: str, ref: str | None = None) -> float:
        """端末が声を出す唯一の経路。通話中は例外で止める(割り込まない設計の担保)。
        声の合成中や再生中に電話が鳴ったときも、再生の直前と再生中に確かめて、その場でやめる。"""
        with self._say_lock:
            return self._say(text, ref)

    def _say(self, text: str, ref: str | None) -> float:
        if not self.may_speak():
            raise SilenceViolation("通話中は話さない")

        def before_play(dur: float) -> None:
            self.emit({"type": "speak", "text": text, "dur": round(dur, 2), "call_id": ref,
                       "ts": datetime.now().isoformat(timespec="seconds")})
            if self.ear is not None:
                self.ear.mute_for(dur + 0.4)       # 自分の声は聞かない(半二重)

        if self._speak:
            dur = self._speak(text, before_play, self.may_speak)
            if dur is None:
                if self.ear is not None:
                    self.ear.mute_for(0.0)      # 途中でやめたので、すぐに聞く側へ戻る(電話の第一声を聞き逃さない)
                self.emit({"type": "speak_stopped", "call_id": ref})
                raise SilenceViolation("話している途中で電話が鳴ったので、やめた")
        else:
            before_play(0.0)
            dur = 0.0
        if self.on_spoken:
            self.on_spoken(text)
        return dur

    @staticmethod
    def _later(sec: float, fn, *args) -> None:
        t = threading.Timer(sec, fn, args=args)
        t.daemon = True                     # 終了を待たせない
        t.start()

    def _bg(self, fn, *args) -> None:
        if self.sync:
            fn(*args)
        else:
            threading.Thread(target=fn, args=args, daemon=True).start()

    # ---------- 耳から ----------
    def on_ear(self, ev: dict) -> None:
        t = ev["type"]
        if t == "level":
            self.emit(ev)
            return
        if t == "room_utt":
            if self.dialog is not None:
                ev = {**ev, "call_id": self.dialog["call_id"]}     # 電話のあとの答えも、その通話の文字起こしとして扱う
            elif self._closed and time.time() - self._closed[1] < 20:
                ev = {**ev, "call_id": self._closed[0]}            # 会話を閉じた直後に文字になった声も同じ(消すときに伏せる)
        self.emit(ev)
        if t == "state" and ev["state"] in ("ringing", "dialing", "in_call"):
            cid = ev.get("call_id")
            if cid and cid not in self.live:
                self.live[cid] = {"utts": [], "listener": None, "last_judge_n": 0, "last_judge_t": time.time(), "busy": False}
        elif t == "utt" and ev.get("call_id") in self.live:
            st = self.live[ev["call_id"]]
            st["utts"].append(ev)
            n_new = len(st["utts"]) - st["last_judge_n"]
            if not st["busy"] and (n_new >= config.LISTENER_EVERY_UTTS or
                                   (n_new >= 3 and time.time() - st["last_judge_t"] >= config.LISTENER_EVERY_SEC)):
                st["busy"] = True
                self._bg(self._interim, ev["call_id"])
        elif t == "state" and ev["state"] == "ended":
            self._bg(self.finalize, ev)
        elif t == "room_utt" and self.dialog is not None:
            self._buffer_answer(ev["text"])

    # 祖母の答えは、話し終わるまで溜めて 1 回にまとめる。応答は 1 つずつ。
    # 「話し終わった」= 最後の断片から 1.3 秒たち、耳がもう話し声を聞いていない(文字にしている途中でもない)。
    # 文の切れ目で間が空いても、2 つ目の文を言い終わるまで待つ(最初の断片から最大 12 秒)。
    def _buffer_answer(self, text: str) -> None:
        if self.sync:
            self._dialog_answer(text)
            return
        with self._buf_lock:
            if not self._answer_buf:
                self._answer_t0 = time.time()
                self._answer_q = len(self.dialog["history"]) if self.dialog else -1   # どの問いへの答えか
            self._answer_buf.append(text)
            if self._answer_timer:
                self._answer_timer.cancel()
            self._answer_timer = threading.Timer(1.3, self._flush_answer)
            self._answer_timer.daemon = True
            self._answer_timer.start()

    def _flush_answer(self) -> None:
        with self._buf_lock:
            hearing = self.ear is not None and hasattr(self.ear, "hearing") and self.ear.hearing()
            if hearing and time.time() - self._answer_t0 < 12.0:
                self._answer_timer = threading.Timer(0.4, self._flush_answer)     # まだ話している。言い終わるまで待つ
                self._answer_timer.daemon = True
                self._answer_timer.start()
                return
            text = "".join(self._answer_buf)
            q = self._answer_q
            self._answer_buf = []
            self._answer_timer = None
        if text:
            with self._turn_lock:
                d = self.dialog
                if d is not None and q != len(d["history"]):     # 次の問いを始めたあとに届いた、前の問いへの続き
                    self.emit({"type": "answer_dropped", "call_id": d["call_id"]})
                    return
                self._dialog_answer(text)

    def _interim(self, cid: str) -> None:
        st = self.live.get(cid)
        if not st:
            return
        tok = llm.REF.set(cid)
        try:
            lines = [u["line"] for u in st["utts"]]
            ma = st["utts"][-1].get("ma") if st["utts"] else None
            from .ear.ma import summary_line
            out = listener.judge(lines, summary_line(st["utts"][-1]["clock"], ma) if ma else "", prev=st["listener"])
            st["listener"] = out
            st["last_judge_n"] = len(st["utts"])
            st["last_judge_t"] = time.time()
            self.emit({"type": "listener", "call_id": cid, "final": False, "out": out})
        except Exception as e:
            self.emit({"type": "error", "where": "listener", "message": str(e)})
        finally:
            st["busy"] = False
            llm.REF.reset(tok)

    # ---------- 通話終了 ----------
    def finalize(self, ev: dict) -> dict:
        tok = llm.REF.set(ev["call_id"])
        try:
            return self._finalize(ev)
        finally:
            llm.REF.reset(tok)

    def _finalize(self, ev: dict) -> dict:
        cid = ev["call_id"]
        self._latest_cid = cid
        st = self.live.pop(cid, {"listener": None})
        lines = [l for l in ev["lines"] if "祖母「" in l]
        call = {"call_id": cid, "started": ev["started"], "direction": ev["direction"], "duration": ev["duration"],
                "lines": ev["lines"], "ma_line": ev.get("ma_line", "")}
        self.store.upsert_call(cid, started=ev["started"], direction=ev["direction"], duration=ev["duration"],
                               lines=ev["lines"], ma=ev.get("ma"), scenario=self.scenario_tag)
        result: dict = {"call_id": cid}
        if not lines:
            self.emit({"type": "decision", "call_id": cid, "decision": {"action": "silent", "headline": "発話なし"}})
            self._purge(cid)
            return result
        try:
            lo = listener.judge(ev["lines"], ev.get("ma_line", ""), prev=st.get("listener"), final=True)
            self.emit({"type": "listener", "call_id": cid, "final": True, "out": lo})
            reb = None
            if needs_rebuttal(lo):
                self.emit({"type": "thinking", "call_id": cid, "who": "rebuttal"})
                reb = rebuttal.review(lines, self.store.context_text())
                self.emit({"type": "rebuttal", "call_id": cid, "out": {k: v for k, v in reb.items() if k != "raw"}})
            self.emit({"type": "thinking", "call_id": cid, "who": "family"})
            dec = family.decide(call, lo, reb, self.store)
            karte = {**dec["karte"], "call_id": cid, "datetime": ev["started"], "direction": ev["direction"]}
            self.store.upsert_call(cid, listener=lo, rebuttal=reb, decision=dec, karte=karte, action=dec["action"],
                                   risk=karte.get("risk"))
            self.emit({"type": "decision", "call_id": cid, "decision": dec, "karte": karte})
            result.update({"listener": lo, "rebuttal": reb, "decision": dec, "karte": karte})
            if dec["action"] == "immediate":
                try:
                    letter = letters.write("immediate", [self.store.call(cid)], self.store)
                    lid = self.store.add_letter("immediate", letter, "messages-api", [cid])
                    self.emit({"type": "letter", "id": lid, "letter": letter})
                    result["letter"] = letter
                except Exception as e:        # 便りが書けなくても、電話のあとの声かけは続ける
                    self.emit({"type": "error", "where": "immediate_letter", "message": f"{type(e).__name__}: {e}"})
            ask = bool(dec.get("postcall", {}).get("ask")) and dec["action"] != "silent"   # 普通の電話には問いかけない
            if ask and not self.sync:
                result["postcall"] = dec["postcall"]
                self._later(self.postcall_delay, self.start_dialog, cid)
            else:
                if ask:
                    result["postcall"] = dec["postcall"]   # 同期モード(評価・下準備)では会話をしないので、ここで消す
                self._purge(cid)
        except Exception as e:
            self.emit({"type": "error", "where": "finalize", "message": f"{type(e).__name__}: {e}"})
            result["error"] = str(e)
            self._purge(cid)                       # 失敗しても文字起こしは残さない(安全側)
        if self.on_finalized:
            self.on_finalized(result)
        return result

    # ---------- 文字起こしを消す ----------
    def _purge(self, cid: str) -> None:
        """文字起こしを消す。残すのは通話カルテ(要約)と判断だけ。台帳と画面・ログの原文も伏せる。"""
        self.store.purge_transcript(cid)
        n = llm.redact(cid)
        for fn in self.on_purge:
            try:
                fn(cid)
            except Exception as e:
                self.emit({"type": "error", "where": "purge", "message": str(e)})
        self.emit({"type": "purged", "call_id": cid, "ledger_redacted": n})

    # ---------- 電話のあとの会話 ----------
    def start_dialog(self, cid: str, tries: int = 0) -> None:
        c = self.store.call(cid)
        if not c or not c.get("decision") or c.get("transcript_purged"):
            return
        if self._latest_cid and cid != self._latest_cid:
            # あとから別の電話があった。「さっきの電話」がどれか分からなくなるので、古い方は聞かない(カルテと夕方の便りには残る)
            self.emit({"type": "dialog_skipped", "call_id": cid, "reason": "newer_call"})
            self._purge(cid)
            return
        quiet = self.ear is None or not hasattr(self.ear, "quiet_for") or self.ear.quiet_for(config.QUIET_BEFORE_OPENER_SEC)
        if not self.may_speak() or self.dialog is not None or not quiet:
            # 電話の最中・別の会話の最中・誰かが話している(耳が気づかなかった電話かもしれない)なら、待ってから話しかける。
            # 待ちきれなければ聞かずに消す
            if tries < 20 and not self.sync:
                self._later(self.postcall_delay, self.start_dialog, cid, tries + 1)
            else:
                self.emit({"type": "dialog_skipped", "call_id": cid, "reason": "never_quiet"})
                self._purge(cid)
            return
        opener = config.POSTCALL_OPENER    # 聞き取った中身を先に言わない
        self.dialog = {"call_id": cid, "history": [{"who": "fusuma", "text": opener}], "told": [], "consent": "unknown"}
        self.emit({"type": "dialog", "call_id": cid, "history": self.dialog["history"]})
        try:
            self.say(opener, ref=cid)
        except SilenceViolation:
            self._end_dialog(cid, reason="call")    # 話しかける前後に電話が鳴った: いったん閉じて、あとで聞き直す
            if not self.sync:
                self._later(self.postcall_delay, self.start_dialog, cid, tries + 1)
            return
        except Exception as e:                       # 声が出せない(TTS が落ちた など): 会話を閉じて消す
            self.emit({"type": "error", "where": "say", "message": f"{type(e).__name__}: {e}"})
            self._end_dialog(cid, reason="error")
            self._purge(cid)
            self.emit({"type": "dialog_done", "call_id": cid, "consent": "unknown", "reason": "error"})
            return
        self._await_answer(cid)

    def _await_answer(self, cid: str) -> None:
        """話し終えてから 14 秒のあいだに話し始めた声だけを文字にする。答えがなければ会話を閉じて文字起こしを消す。"""
        if self.ear is not None:
            self.ear.open_room_listen(14.0)
        if self.sync or self.dialog is None:
            return
        n = len(self.dialog["history"])

        def check(extra: float = 0.0) -> None:
            d = self.dialog
            if d is None or d["call_id"] != cid or len(d["history"]) != n or self._answer_buf or self._turn_lock.locked():
                return
            if self.ear is not None and hasattr(self.ear, "hearing") and self.ear.hearing() and extra < 12:
                self._later(2.0, check, extra + 2.0)       # まだ話している(か、文字にしている途中)。少し待つ
                return
            self._end_dialog(cid, reason="no_answer")
            self._purge(cid)
            self.emit({"type": "dialog_done", "call_id": cid, "consent": d["consent"], "reason": "no_answer"})

        self._later(config.DIALOG_IDLE_SEC, check)

    def _end_dialog(self, cid: str, reason: str) -> None:
        if self.dialog is not None and self.dialog["call_id"] == cid:
            self.dialog = None
        self._closed = (cid, time.time())
        if self.ear is not None:
            self.ear.open_room_listen(0.0)          # 部屋の声を聞く窓を閉じる
        self.emit({"type": "dialog_closed", "call_id": cid, "reason": reason})

    def _dialog_answer(self, text: str) -> None:
        d = self.dialog
        if d is None:
            return
        tok = llm.REF.set(d["call_id"])
        try:
            self._dialog_turn(d, text)
        finally:
            llm.REF.reset(tok)

    def _dialog_turn(self, d: dict, text: str) -> None:
        cid = d["call_id"]
        if self.ear is not None:
            self.ear.open_room_listen(0.0)        # 考えて話すあいだは聞く窓を閉じる。話し終えたら _await_answer で開け直す
        d["history"].append({"who": "grandma", "text": text})
        self.emit({"type": "dialog", "call_id": cid, "history": d["history"]})
        try:
            c = self.store.call(cid)
            turn = family.postcall_turn(c["karte"], c["decision"], d["history"], self.store)
        except Exception as e:
            self.emit({"type": "error", "where": "postcall", "message": f"{type(e).__name__}: {e}"})
            self._end_dialog(cid, reason="error")
            self._purge(cid)
            self.emit({"type": "dialog_done", "call_id": cid, "consent": d["consent"], "reason": "error"})
            return
        if letters.violations({"say": turn.get("say", "")}):
            turn["say"] = "そうだったんだね。教えてくれてありがとう。"   # 言い切り・責める言葉は口にしない
        if turn.get("told"):
            d["told"] = [turn["told"]]          # told はそこまでの会話全体の要約なので、最新だけを残す
        if turn.get("consent_to_share") != "unknown":
            d["consent"] = turn["consent_to_share"]
        d["history"].append({"who": "fusuma", "text": turn["say"]})
        self.emit({"type": "dialog", "call_id": cid, "history": d["history"], "turn": turn})
        self.store.upsert_call(cid, told_by_person=" / ".join(d["told"]), diff=turn.get("diff"), consent=d["consent"])
        done = bool(turn.get("done"))
        if done and self.ear is not None:
            self.ear.open_room_listen(0.0)         # 会話はおしまい。ここからの部屋の声は文字にしない
        reason = None
        try:
            self.say(turn["say"], ref=cid)
        except SilenceViolation:
            self._end_dialog(cid, reason="call")    # 話す途中で電話が鳴った: 聞けたところまでがカルテに残っている
            done, reason = True, "call"
        except Exception as e:
            self.emit({"type": "error", "where": "say", "message": f"{type(e).__name__}: {e}"})
            self._end_dialog(cid, reason="error")
            done, reason = True, "error"
        if done:
            if self.dialog is d:                    # 最後の一言を言い終えてから閉じる(次の電話の会話と重ならない)
                self.dialog = None
                self._closed = (cid, time.time())
            self._purge(cid)          # 聞き取りが終わったら文字起こしは消す
            self.emit({"type": "dialog_done", "call_id": cid, "consent": d["consent"], **({"reason": reason} if reason else {})})
        else:
            self._await_answer(cid)

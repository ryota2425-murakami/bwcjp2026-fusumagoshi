"""原則のテスト。Claude API は使わない。待ち時間を実際に待つテストがあるので、20 秒ほどかかる。

    cd app && ../.venv/bin/python tests/test_principles.py

音声モデル: 耳を組み立てる 2 件(test_call_end_waits_for_last_words と test_server_redacts_event_log_and_late_events)は、
YAMNet(呼出音などの音)と Silero VAD(声の区切り)をこの Mac の中で読み込む。
文字起こし(whisper)と声の合成(TTS)は呼ばない(使う場面は差し替える)。

確かめること:
  - 通話中は話さない。声の合成中・再生中に電話が鳴っても、その場でやめる
  - 耳がない(通話中か分からない)のに音を出す設定なら、話さない
  - 電話のあと、別の電話の最中なら待ってから話しかける。答えがなければ会話を閉じる(答えている途中なら待つ)
  - 祖母の答えが文の切れ目で 2 つに割れても、言い終わるまで待って 1 回だけ応える。前の問いへの遅れた答えは捨てる
  - 声が出せない(TTS が落ちた)ときも、会話を閉じて文字起こしを消す。部屋で誰かが話していたら話しかけない
  - あとから別の電話があったら、古い電話のことは聞かない。着信で声を途中でやめたら、すぐ聞く側に戻る
  - 受話器を置く直前の発話も、文字にし終えてから「通話が終わった」を出す(最後の言葉が判断から漏れない)
  - 便りや電話のあとの声かけに言い切り(「詐欺です」など)が残ったら、決まった文に差し替える(ぼかした言い方は通す)。
    採点に合格しなかった夕方の便りは届けない
  - 文字起こしを消すとき、カルテ以外の原文(聞き役の引用・反証役の原文・台帳・画面とログ)も伏せる。
    判断の途中で失敗しても、黙って記録にした(問いかけない)電話でも消す
  - 原則の番人フック(PreToolUse)が、実在しうる電話番号・通話中に話す経路・脳から音声を送る書き方・内緒のメモの持ち出しを止める
  - Pi(ふすまの中の画面)へは気分の名前・秒数・口の開きだけを送り、文字は送らない。家族の机の Pi には便りの合図だけ
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from fusuma import config  # noqa: E402
from fusuma.brain import family, llm  # noqa: E402
from fusuma.devices import Speaker  # noqa: E402
from fusuma.orchestrator import Fusuma, SilenceViolation  # noqa: E402
from fusuma.store import GONE, Store, redact_event  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="fusuma-test-"))
llm.PRIVACY = TMP / "privacy_ledger.jsonl"       # 本物の台帳には触らない


class FakeEar:
    def __init__(self, state: str = "idle"):
        self.state = state
        self.room: list[float] = []
        self.hearing_until = 0.0
        self.quiet = True
        self.mutes: list[float] = []

    def hearing(self) -> bool:
        return time.monotonic() < self.hearing_until

    def quiet_for(self, seconds: float) -> bool:
        return self.quiet

    def open_room_listen(self, seconds: float, tag: str = "postcall") -> None:
        self.room.append(seconds)

    def mute_for(self, seconds: float) -> None:
        self.mutes.append(seconds)


def quiet_speak(text, before_play=None, may_speak=None):
    if before_play:
        before_play(0.05)
    return 0.05


def new_fz(ear=None, speak=quiet_speak, delay=0.15):
    store = Store(TMP / f"t{time.time_ns()}.sqlite3")
    events: list[dict] = []
    return Fusuma(store, emit=events.append, speak=speak, ear=ear, postcall_delay=delay), store, events


def seed_call(store: Store, cid: str = "C1") -> None:
    store.upsert_call(cid, started="2026-11-05T14:01:00", direction="incoming", duration=120.0,
                      lines=["14:02:01 祖母「今日中なら、半額なんですか」"],
                      listener={"track": "solicitation", "stage": "強い勧め", "risk": "medium", "score": 0.6,
                                "speech_acts": [{"t": "14:02:01", "kind": "repeat", "text": "今日中なら、半額なんですか"}],
                                "evidence": [{"t": "14:02:01", "note": "「今日中」と期限を復唱"}],
                                "disclosed": ["住所(みどり町の二の五)"], "reason": "期限を復唱", "to_ask": ["何を頼んだか"]},
                      rebuttal={"genuine_likelihood": "low", "raw": "祖母は「今日中なら」と…",
                                "against_genuine": [{"text": "「今日中なら半額」(14:01:33)と繰り返している", "cites": []}],
                                "for_genuine": [{"text": "「息子に聞いてみないと」(14:01:50)", "cites": []}],
                                "citations": [{"source": "card-x", "title": "電話勧誘販売", "cited_text": "…"}]},
                      decision={"action": "evening", "headline": "健康食品の定期購入", "postcall": {"ask": True}},
                      karte={"risk": "medium", "product": "膝のサプリ"})


# ---------------------------------------------------------------- 話さない
def test_say_refuses_during_call():
    called = []
    fz, _, _ = new_fz(FakeEar("in_call"), speak=lambda *a: called.append(1))
    try:
        fz.say("こんにちは")
        raise AssertionError("通話中に話した")
    except SilenceViolation:
        pass
    assert not called, "通話中に TTS を呼んだ"


def test_say_refuses_without_ear_when_audible():
    fz, _, _ = new_fz(ear=None)
    try:
        fz.say("こんにちは")
        raise AssertionError("耳がないのに話した")
    except SilenceViolation:
        pass


def test_speaker_stops_when_phone_rings_mid_speech():
    ear = FakeEar("idle")
    sp = Speaker(audible=False, out_dir=TMP / "speech")
    sp.synth = lambda text, persona="fusuma": (__import__("numpy").zeros(24000 * 2, dtype="float32"), 24000)  # 2 秒の声
    fz, _, events = new_fz(ear, speak=sp.say)
    threading.Timer(0.3, lambda: setattr(ear, "state", "ringing")).start()
    t0 = time.monotonic()
    try:
        fz.say("そういえば、さっきの電話、なんだったの?")
        raise AssertionError("電話が鳴ったのに最後まで話した")
    except SilenceViolation:
        pass
    assert time.monotonic() - t0 < 0.8, "止まるのが遅い"
    assert any(e["type"] == "speak_stopped" for e in events)
    assert not (TMP / "speech" / "speech_log.jsonl").exists(), "save=False なのに声を残した"


def test_speaker_does_not_start_if_call_began_during_synthesis():
    ear = FakeEar("idle")
    sp = Speaker(audible=False, out_dir=TMP / "speech2")

    def slow_synth(text, persona="fusuma"):
        ear.state = "ringing"            # 合成しているあいだに電話が鳴った
        return __import__("numpy").zeros(2400, dtype="float32"), 24000

    sp.synth = slow_synth
    fz, _, events = new_fz(ear, speak=sp.say)
    try:
        fz.say("こんにちは")
        raise AssertionError("鳴っているのに話し始めた")
    except SilenceViolation:
        pass
    assert not any(e["type"] == "speak" for e in events), "再生を始めた"


# ---------------------------------------------------------------- 電話のあとの会話
def test_dialog_waits_until_other_call_ends():
    ear = FakeEar("in_call")
    fz, store, events = new_fz(ear)
    seed_call(store)
    fz.start_dialog("C1")
    assert not any(e["type"] == "dialog" for e in events), "通話中に話しかけた"
    ear.state = "idle"
    time.sleep(0.4)
    assert any(e["type"] == "dialog" for e in events), "通話が終わっても話しかけない"
    fz.dialog = None


def test_dialog_closes_and_purges_when_no_answer():
    config.DIALOG_IDLE_SEC = 0.3
    ear = FakeEar("idle")
    fz, store, events = new_fz(ear)
    seed_call(store)
    fz.start_dialog("C1")
    time.sleep(0.7)
    assert fz.dialog is None, "答えがないのに会話が開いたまま"
    assert store.call("C1")["transcript_purged"] == 1, "文字起こしが残っている"
    assert any(e["type"] == "dialog_done" and e.get("reason") == "no_answer" for e in events)
    assert ear.room[-1] == 0.0, "部屋の声を聞く窓が開いたまま"


def test_dialog_answer_then_done_purges():
    ear = FakeEar("idle")
    fz, store, events = new_fz(ear)
    seed_call(store)
    family_turn = family.postcall_turn
    family.postcall_turn = lambda *a, **k: {"say": "そうだったんだね。", "told": "膝のサプリを頼んだ", "consent_to_share": "yes",
                                            "done": True, "diff": None}
    try:
        fz.start_dialog("C1")
        fz._dialog_answer("膝のサプリですって")
    finally:
        family.postcall_turn = family_turn
    c = store.call("C1")
    assert c["transcript_purged"] == 1 and c["told_by_person"] == "膝のサプリを頼んだ"
    assert any(e["type"] == "dialog_done" for e in events)
    assert ear.room[-1] == 0.0, "会話が終わっても部屋の声を聞く窓が開いている"


def test_answer_split_by_pause_is_one_turn():
    ear = FakeEar("idle")
    fz, store, _ = new_fz(ear)
    got: list[str] = []
    fz._dialog_answer = got.append
    t0 = time.monotonic()
    ear.hearing_until = t0 + 2.2          # 1 文目のあと、2 文目を話している(と文字にしている)あいだ
    fz._buffer_answer("膝のサプリですって。")
    time.sleep(2.0)
    fz._buffer_answer("今日だけ半額だっていうから、つい頼んじゃったのよ。")
    time.sleep(2.0)
    assert got == ["膝のサプリですって。今日だけ半額だっていうから、つい頼んじゃったのよ。"], got


def test_tts_failure_closes_dialog_and_purges():
    def broken(text, before_play=None, may_speak=None):
        raise ConnectionError("TTS server down")
    ear = FakeEar("idle")
    fz, store, events = new_fz(ear, speak=broken)
    seed_call(store)
    fz.start_dialog("C1")
    assert fz.dialog is None and store.call("C1")["transcript_purged"] == 1
    assert any(e["type"] == "dialog_done" and e.get("reason") == "error" for e in events)


def test_tts_failure_mid_dialog_closes_and_purges():
    ear = FakeEar("idle")
    calls = {"n": 0}

    def flaky(text, before_play=None, may_speak=None):
        calls["n"] += 1
        if calls["n"] > 1:
            raise ConnectionError("TTS server down")
        return 0.05
    fz, store, events = new_fz(ear, speak=flaky)
    seed_call(store)
    turn = family.postcall_turn
    family.postcall_turn = lambda *a, **k: {"say": "そうだったんだね。", "told": "", "consent_to_share": "unknown", "done": False, "diff": None}
    try:
        fz.start_dialog("C1")
        fz._dialog_answer("膝のサプリですって")
    finally:
        family.postcall_turn = turn
    assert fz.dialog is None and store.call("C1")["transcript_purged"] == 1


def test_opener_waits_while_someone_is_talking():
    ear = FakeEar("idle")
    ear.quiet = False                       # 部屋で誰かが話している(耳が気づかなかった電話かもしれない)
    fz, store, events = new_fz(ear)
    seed_call(store)
    fz.start_dialog("C1")
    assert not any(e["type"] == "dialog" for e in events), "話している人に話しかけた"
    ear.quiet = True
    time.sleep(0.4)
    assert any(e["type"] == "dialog" for e in events)
    fz.dialog = None


def test_older_call_is_not_asked_about():
    fz, store, events = new_fz(FakeEar("idle"))
    seed_call(store, "C1")
    fz._latest_cid = "C2"                   # C1 のあとに別の電話があった
    fz.start_dialog("C1")
    assert not any(e["type"] == "dialog" for e in events)
    assert store.call("C1")["transcript_purged"] == 1


def test_ring_cut_unmutes_ear_at_once():
    ear = FakeEar("idle")
    sp = Speaker(audible=False, out_dir=TMP / "speech3")
    sp.synth = lambda text, persona="fusuma": (__import__("numpy").zeros(24000 * 2, dtype="float32"), 24000)
    fz, _, _ = new_fz(ear, speak=sp.say)
    threading.Timer(0.3, lambda: setattr(ear, "state", "ringing")).start()
    try:
        fz.say("こんにちは")
    except SilenceViolation:
        pass
    assert ear.mutes[-1] == 0.0, f"途中でやめたのに耳が黙ったまま: {ear.mutes}"


def test_call_end_waits_for_last_words():
    """耳(Ear)を組み立てるので、YAMNet と Silero VAD を読み込む。文字起こしと声の測定は差し替える。"""
    from fusuma.ear import asr, prosody
    from fusuma.ear import pipeline
    from fusuma.ear.ma import MaTracker
    from fusuma.ear.vad import Segment
    import numpy as np
    got: list[dict] = []
    ear = pipeline.Ear(got.append, realtime=True)
    tr, ms = asr.transcribe, prosody.measure
    asr.transcribe = lambda a: (time.sleep(0.5), "じゃあ、お願いします。")[1]      # 文字にするのに 0.5 秒かかる
    prosody.measure = lambda a: {"dur": 1.0, "f0": 140.0, "db": -22.0}
    try:
        ear.state = "in_call"
        ear.call = {"call_id": "T1", "direction": "incoming", "start_t": 0.0, "ring_t": 0.0, "lines": []}
        ear.ma = MaTracker(call_start=0.0)
        ear.t = 10.0
        ear._segment(Segment(8.0, 9.0, np.zeros(16000, dtype=np.float32)))
        ear._end_call(10.0, reason="hangup")       # 文字にし終わる前に受話器を置いた
        ear.pool.shutdown(wait=True)
    finally:
        asr.transcribe, prosody.measure = tr, ms
    ended = [e for e in got if e.get("type") == "state" and e.get("state") == "ended"]
    assert ended and any("じゃあ、お願いします" in l for l in ended[0]["lines"]), ended


# ---------------------------------------------------------------- 便り
def test_letter_with_assertion_is_replaced():
    from fusuma.brain import letters
    seq = iter([{"urgency": "immediate", "title": "詐欺です", "daily": [], "calls": [], "suggested_talk": "", "sources": [], "closing": ""}] * 2)
    real = llm.call
    llm.call = lambda *a, **k: (next(seq), None)
    try:
        out = letters.write("immediate", [{"call_id": "C1", "started": "", "karte": {"risk": "high"},
                                           "decision": {"headline": "カードを渡す約束"}}], Store(TMP / "l.sqlite3"))
    finally:
        llm.call = real
    assert out["_meta"]["template"] and not letters.violations(out), out


def test_evening_letter_delivered_only_if_grader_passed():
    from fusuma.brain import managed
    body = {"urgency": "evening", "title": "今日の便り", "daily": ["畑の大根"], "calls": [], "suggested_talk": "", "sources": [], "closing": ""}
    ok = managed.gate(body, [{"iteration": 0, "result": "needs_revision"}, {"iteration": 1, "result": "satisfied"}])
    held = managed.gate(body, [{"iteration": 0, "result": "needs_revision"}, {"iteration": 2, "result": "max_iterations_reached"}])
    assert ok["title"] == "今日の便り" and ok["_meta"]["grade"] == "satisfied"
    assert held["_meta"]["held"] and "畑の大根" not in json.dumps(held, ensure_ascii=False)


def test_finalize_error_still_purges():
    from fusuma.brain import listener
    fz, store, events = new_fz(FakeEar("idle"))
    real = listener.judge
    listener.judge = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("API down"))
    try:
        fz.finalize({"call_id": "E1", "started": "2026-11-05T14:00:00", "direction": "incoming", "duration": 30.0,
                     "lines": ["14:00:05 祖母「はい、もしもし」"], "ma_line": ""})
    finally:
        listener.judge = real
    assert store.call("E1")["transcript_purged"] == 1, "失敗したのに文字起こしが残った"


def test_never_quiet_room_purges_without_asking():
    ear = FakeEar("idle")
    ear.quiet = False
    fz, store, events = new_fz(ear, delay=0.01)
    seed_call(store)
    fz.start_dialog("C1")
    time.sleep(0.6)                          # 20 回待っても静かにならない
    assert not any(e["type"] == "dialog" for e in events)
    assert store.call("C1")["transcript_purged"] == 1


def test_late_answer_to_previous_question_is_dropped():
    fz, store, events = new_fz(FakeEar("idle"))
    got: list[str] = []
    fz._dialog_answer = got.append
    fz.dialog = {"call_id": "C1", "history": [{"who": "fusuma", "text": "?"}], "told": [], "consent": "unknown"}
    fz._buffer_answer("膝のサプリですって。")          # 1 つ目の問いへの答え
    fz.dialog["history"] += [{"who": "grandma", "text": "…"}, {"who": "fusuma", "text": "次の問い"}]   # もう次の問いに進んだ
    time.sleep(1.6)
    assert got == [] and any(e["type"] == "answer_dropped" for e in events)
    fz.dialog = None


def test_no_answer_check_waits_while_she_is_speaking():
    config.DIALOG_IDLE_SEC = 0.3
    ear = FakeEar("idle")
    fz, store, events = new_fz(ear)
    seed_call(store)
    ear.hearing_until = time.monotonic() + 2.5          # 答え始めているが、まだ言い終わっていない
    fz.start_dialog("C1")
    time.sleep(1.0)
    assert fz.dialog is not None, "話している途中で会話を閉じた"
    time.sleep(4.5)                                       # 話し終えてから、次の見直し(2 秒ごと)で閉じる
    assert fz.dialog is None and store.call("C1")["transcript_purged"] == 1


def test_spoken_reply_with_assertion_is_replaced():
    said: list[str] = []

    def speak(text, before_play=None, may_speak=None):
        said.append(text)
        return 0.05
    fz, store, _ = new_fz(FakeEar("idle"), speak=speak)
    seed_call(store)
    turn = family.postcall_turn
    family.postcall_turn = lambda *a, **k: {"say": "それは詐欺です。", "told": "", "consent_to_share": "unknown", "done": True, "diff": None}
    try:
        fz.start_dialog("C1")
        fz._dialog_answer("膝のサプリですって")
    finally:
        family.postcall_turn = turn
    assert "詐欺です" not in said[-1], said


def test_silent_call_gets_no_postcall_question():
    from fusuma.brain import listener
    fz, store, events = new_fz(FakeEar("idle"))
    real_j, real_d = listener.judge, family.decide
    listener.judge = lambda *a, **k: {"track": "normal", "stage": "-", "risk": "low", "score": 0.1, "speech_acts": []}
    family.decide = lambda *a, **k: {"action": "silent", "headline": "普通の電話", "restraint_note": "", "karte": {"risk": "low"},
                                     "postcall": {"ask": True}}
    try:
        fz.finalize({"call_id": "N1", "started": "2026-11-05T14:00:00", "direction": "incoming", "duration": 30.0,
                     "lines": ["14:00:05 祖母「はい、もしもし」"], "ma_line": ""})
    finally:
        listener.judge, family.decide = real_j, real_d
    time.sleep(0.4)
    assert not any(e["type"] == "dialog" for e in events) and store.call("N1")["transcript_purged"] == 1


def test_assertion_rule_ignores_hedged_wording():
    from fusuma.brain import letters
    ok = ["詐欺と断定はできませんが、確かめてください", "詐欺だとは限りません", "もし詐欺でしたら188に", "だまされないように", "オレオレ詐欺の手口に似ています"]
    ng = ["これは詐欺です。", "詐欺だ。", "詐欺に違いない", "おばあちゃんはだまされた"]
    assert not [x for x in ok if letters.violations({"t": x})]
    assert all(letters.violations({"t": x}) for x in ng)


def test_server_redacts_event_log_and_late_events():
    """サーバーの Hub が、画面の履歴と runs/events.jsonl の原文を伏せる(本物の runs/ には触らない)。
    サーバーを読み込むと耳も作られるので、YAMNet と Silero VAD を読み込む(音は流さない)。"""
    code = """
import json, sys
sys.path.insert(0, %r)
from fusuma import server as srv
h = srv.hub
h.emit({"type": "utt", "call_id": "Z1", "text": "今日中なら", "line": "祖母「今日中なら」"})
h.emit({"type": "claude", "ref": "Z1", "payload_preview": "祖母「今日中なら」"})
h.emit({"type": "utt", "call_id": "Z2", "text": "別の電話"})
h.redact("Z1")
h.emit({"type": "room_utt", "call_id": "Z1", "text": "あとから届いた答え"})
rows = [json.loads(l) for l in srv.EVENTS.read_text().splitlines()]
bad = [r for r in rows if r.get("call_id") == "Z1" or r.get("ref") == "Z1"]
assert all("今日中" not in json.dumps(r, ensure_ascii=False) and "あとから" not in json.dumps(r, ensure_ascii=False) for r in bad), bad
assert any(r.get("text") == "別の電話" for r in rows)
assert all("今日中" not in json.dumps(e, ensure_ascii=False) for e in h.recent if e.get("call_id") == "Z1" or e.get("ref") == "Z1")
print("ok")
""" % str(APP)
    import os
    env = {**os.environ, "FUSUMA_RUNS": str(TMP / "runs_srv"), "FUSUMA_AUDIBLE": "0", "FUSUMA_MANAGED": "0"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-800:]


# ---------------------------------------------------------------- 文字起こしを消す
def test_purge_removes_quotes_ledger_and_logs():
    fz, store, events = new_fz(FakeEar("idle"))
    seed_call(store)
    llm.PRIVACY.write_text(json.dumps({"role": "listener", "text": "祖母「今日中なら」", "chars": 9, "ref": "C1"}, ensure_ascii=False) + "\n" +
                           json.dumps({"role": "memo", "text": "夕方の話", "chars": 4, "ref": None}, ensure_ascii=False) + "\n")
    hooked = []
    fz.on_purge.append(hooked.append)
    fz._purge("C1")
    c = store.call("C1")
    assert c["lines"] is None
    lo = c["listener"]
    assert all("text" not in a for a in lo["speech_acts"]) and "evidence" not in lo and "disclosed" not in lo
    assert lo["risk"] == "medium" and lo["stage"] == "強い勧め", "要約まで消えた"
    assert set(c["rebuttal"]) == {"genuine_likelihood", "citations"}, c["rebuttal"]     # 引用の入る項目は残さない
    assert c["rebuttal"]["citations"] == [{"source": "card-x", "title": "電話勧誘販売"}]
    assert c["karte"]["product"] == "膝のサプリ", "カルテまで消えた"
    rows = [json.loads(x) for x in llm.PRIVACY.read_text().splitlines()]
    assert rows[0]["text"] == "" and rows[0]["purged"] and rows[0]["chars"] == 9
    assert rows[1]["text"] == "夕方の話", "別の記録まで伏せた"
    assert hooked == ["C1"] and any(e["type"] == "purged" for e in events)


def test_redact_event():
    assert redact_event({"type": "utt", "text": "はい", "line": "祖母「はい」", "db": -20})["text"] == GONE
    d = redact_event({"type": "dialog", "history": [{"who": "grandma", "text": "膝のサプリ"}], "turn": {"say": "…", "done": False}})
    assert d["history"][0]["text"] == GONE and "say" not in d["turn"]
    assert redact_event({"type": "claude", "payload_preview": "祖母「…」", "chars": 10})["payload_preview"] == GONE
    assert redact_event({"type": "state", "state": "ended", "lines": ["祖母「…」"], "ma_line": "間 8.8秒"})["lines"] == []


# ---------------------------------------------------------------- 原則の番人フック
def _hook(path: str, text: str) -> int:
    inp = json.dumps({"tool_input": {"file_path": path, "content": text}}, ensure_ascii=False)
    return subprocess.run([sys.executable, str(APP / "scripts" / "hooks" / "guard_principles.py")], input=inp,
                          capture_output=True, text=True).returncode


def test_guard_hook():
    assert _hook("/x/app/scripts/synth_scenarios.py", 'sfx_dial("0120312312")') == 2
    assert _hook("/x/app/scenarios/s.json", "お電話は03-1234-5678まで") == 2
    assert _hook("/x/a.md", "０９０ー１２３４ー５６７８") == 2
    assert _hook("/x/a.py", 'FAKE_DIAL = "0000271828"') == 0
    assert _hook("/x/app/fusuma/orchestrator.py", "speaker.say(text)") == 2
    assert _hook("/x/app/fusuma/server.py", "fz = Fusuma(store, speak=speaker.say)") == 0
    assert _hook("/x/app/fusuma/brain/llm.py", '{"type": "input_audio"}') == 2
    assert _hook("/x/app/fusuma/brain/managed.py", "store.memos(include_secret=True)") == 2


def test_lantern_bridge_sends_no_text():
    """Pi(ふすまの中の画面)へは、気分の名前・秒数・口の開きだけ。話した文や文字起こし・便りの本文は一文字も送らない"""
    from fusuma.lantern_bridge import Lantern
    secret = ["はるかぜ健康", "今日だけ半額", "膝のこと気になってたものね", "健太へ。今日のおばあちゃん"]
    L = Lantern()
    evs = [{"type": "state", "state": "ringing", "call_id": "c1"}, {"type": "utt", "text": secret[1], "call_id": "c1"},
           {"type": "state", "state": "in_call", "call_id": "c1"}, {"type": "state", "state": "ended", "call_id": "c1"},
           {"type": "listener", "out": {"quote": secret[0]}}, {"type": "dialog", "call_id": "c1", "history": [secret[2]]},
           {"type": "speak", "text": secret[2], "dur": 2.9, "call_id": "c1"}, {"type": "room_utt", "text": secret[1], "call_id": "c1"},
           {"type": "dialog_done", "call_id": "c1"}, {"type": "letter", "id": 3, "letter": secret[3]},
           {"type": "hello", "recent": [{"type": "speak", "text": secret[2], "dur": 1.0}]}]
    out = [m for e in evs for m in L.on_event(e)]
    blob = __import__("json").dumps(out, ensure_ascii=False)
    for w in secret:
        assert w not in blob, w
    allowed = {"type", "mood", "since", "server_time", "upstream", "dur", "hz", "env", "then", "gaze"}
    assert all(set(m) <= allowed for m in out), [set(m) - allowed for m in out]
    assert [m["mood"] for m in out if m["type"] == "mood"][:3] == ["call", "watch", "after"]


def test_lantern_family_gets_letters_only():
    """家族の机の上の Pi には、電話中かどうか・話しているかどうかを送らない(便りが届いたことだけ)"""
    from fusuma.lantern_bridge import Lantern, for_role
    L = Lantern()
    evs = [{"type": "state", "state": "in_call"}, {"type": "state", "state": "ended"}, {"type": "dialog"},
           {"type": "speak", "text": "x", "dur": 1.0}, {"type": "room_utt", "text": "y"}, {"type": "sound", "event": "doorbell"},
           {"type": "letter", "letter": "z"}]
    fam = [for_role(m, "family") for e in evs for m in L.on_event(e)]
    fam = [m for m in fam if m]
    assert {m["type"] for m in fam} <= {"mood", "letter"}, fam
    assert all(m.get("mood") in (None, "watch", "letter") for m in fam), fam
    assert any(m["type"] == "letter" for m in fam)


if __name__ == "__main__":
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok    {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

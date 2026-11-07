"""動画 v2(13 場面)のタイムライン(場面・音声・字幕)を組み立てて src/data/timeline_v2.json に書く。

素材の時刻と数字は、すべて実際の記録から取る:
  - 画面録画のイベント時刻(rec/<名前>/timing.json の _ts)
  - 祖母の発話の時刻(lab/data/scenarios/S05.truth.json)と、友だちとの電話(S11.truth.json)
  - ふすまごしの声(lab/runs/speech/speech_log.jsonl と wav)
  - ナレーションの長さ(public/narration/narration_meta.json)

python video/script/build_timeline_v2.py [--call call_S05_v3] [--letter letter_v2]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

V = Path(__file__).resolve().parents[1]
P = V / "project" / "public"
LAB = V.parent / "lab" if (V.parent / "lab" / "app").exists() else V.parent
OUT = V / "project" / "src" / "data" / "timeline_v2.json"
REPO_URL = ""          # 公開するリポジトリの URL が決まったら入れる(例: "github.com/<アカウント>/fusumagoshi")

ap = argparse.ArgumentParser()
ap.add_argument("--call", default="call_S05_v4")
ap.add_argument("--letter", default="letter_v4")
ap.add_argument("--max", type=float, default=180.0)
args = ap.parse_args()

NAR = json.loads((P / "narration" / "narration_meta.json").read_text())
NJ = json.loads((V / "script" / "narration.json").read_text())
NTXT = {x["id"]: x["text"] for x in NJ["lines"] + NJ["dialog"]}
TRUTH = json.loads((LAB / "data" / "scenarios" / "S05.truth.json").read_text())
S11 = json.loads((LAB / "data" / "scenarios" / "S11.truth.json").read_text())
R02 = json.loads((LAB / "data" / "scenarios" / "R02.truth.json").read_text())
U = TRUTH["utterances"]
EV = {e["type"]: e["t"] for e in TRUTH["events"]}

scenes: list[dict] = []
CHAR: dict = {}                      # HyperFrames のキャラの場面へ渡す時刻(assets/tracks.js)
audio: list[dict] = []
caps: list[dict] = []
marks: dict[str, float] = {}


def r2(x: float) -> float:
    return round(float(x), 2)


# 台本は読み上げのためにかなで書いた所がある。字幕は表示用の書き方に戻す
CAPTION_FIX = {"夕方ろくじに": "夕方 6 時に", "よんひゃく字以内": "400 字以内", "にふんほど": "2 分ほど", "むっつの観点": "6 つの観点",
               "八十件": "80 件", "おかねは": "お金は", "クロードに届くのは": "Claude に届くのは", "ゼロバイト": "0 バイト",
               "聞き役のハイクが": "聞き役の Haiku が", "もう一人のソネットは": "もう一人の Sonnet は", "マネージド・エージェンツ": "Managed Agents",
               "クロードコードと": "Claude Code と", "二秒ほど": "2 秒ほど", "九秒ちかく": "9 秒ちかく", "あんどん": "行灯"}


def captext(t: str) -> str:
    for k, v in CAPTION_FIX.items():
        t = t.replace(k, v)
    return t


def nar(nid: str, at: float, who: str = "narr", vol: float = 1.0, cap: bool = True, text: str | None = None) -> float:
    d = NAR[nid]["dur"]
    audio.append({"src": f"narration/{nid}.wav", "start": r2(at), "dur": d, "volume": vol})
    if cap:
        caps.append({"start": r2(at + 0.12), "end": r2(at + d - 0.18), "text": captext(text or NTXT[nid]), "who": who})
    return at + d


def scene(kind: str, start: float, dur: float, **kw) -> float:
    scenes.append({"kind": kind, "start": r2(start), "dur": r2(dur), **kw})
    return start + dur


def clip(src: str, at: float, dur: float, frm: float = 0.0, vol: float = 1.0, fi: float = 0.0, fo: float = 0.0, rate: float = 1.0) -> None:
    audio.append({"src": src, "start": r2(at), "dur": r2(dur), "from": r2(frm), "volume": vol, "fadeIn": fi, "fadeOut": fo, "rate": rate})


def sfx(name: str, at: float, vol: float = 0.5, dur: float | None = None, fo: float = 0.0, frm: float = 0.0) -> None:
    d = dur if dur is not None else wav_dur(P / "sfx" / f"{name}.wav")
    clip(f"sfx/{name}.wav", at, d, frm=frm, vol=vol, fo=fo)


def wav_dur(p: Path) -> float:
    info = sf.info(str(p))
    return info.frames / info.samplerate


# ---------------------------------------------------------------- 素材をそろえる(新しい祖母の声・録画・ふすまごしの声)
(P / "audio").mkdir(exist_ok=True)
a, sr = sf.read(LAB / "data" / "scenarios" / "S05.wav", dtype="float32")
# 押し切られた「…じゃあ、お願いします。」は、わざと弱い声で作ってある(システムはその弱さも聞いている)。
# 動画ではその一言が聞こえるよう、その区間だけ持ち上げる
for (a0, a1), g in {(U[13]["start"] - 0.3, U[13]["end"] + 0.4): 3.0, (U[7]["start"] - 0.3, U[7]["end"] + 0.4): 2.0}.items():
    a[int(a0 * sr):int(a1 * sr)] *= 10 ** (g / 20)
sf.write(P / "audio" / "S05_v2.wav", np.clip(a, -1, 1), sr)
for k in (1, 2, 3):
    shutil.copy(LAB / "data" / "scenarios" / f"R02_a{k}.wav", P / "audio" / f"R02v2_a{k}.wav")
for name in (args.call, args.letter):
    src = V / "assets" / "rec" / name
    dst = P / "rec" / name
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("screen.mp4", "timing.json"):
        if not (dst / f).exists() or (dst / f).stat().st_mtime < (src / f).stat().st_mtime:
            shutil.copy(src / f, dst / f)


def rec(name: str) -> dict:
    m = json.loads((P / "rec" / name / "timing.json").read_text())
    t0 = m["t_page"]
    ev = [dict(e, rt=e["_ts"] - t0) for e in m["events"]]
    return {"t0": t0, "ev": ev, "dur": m["t_end"] - t0, "name": name}


CALL = rec(args.call)
cev = CALL["ev"]
demo_rt = next(e for e in cev if e["type"] == "demo")["rt"]          # S05.wav が流れ始めた録画内の時刻
utts = [e for e in cev if e["type"] == "utt"]
ended = next(e for e in cev if e["type"] == "state" and e.get("state") == "ended")
listeners = [e for e in cev if e["type"] == "listener"]
final_lo = [e for e in listeners if e.get("final")][-1]["out"]
reb = next(e for e in cev if e["type"] == "rebuttal")["out"]
dec_ev = next(e for e in cev if e["type"] == "decision")
dec = dec_ev["decision"]
speaks = [e for e in cev if e["type"] == "speak"]
injects = [e for e in cev if e["type"] == "inject"]
purged_rt = next(e for e in cev if e["type"] == "purged")["rt"]

# ふすまごしの声(speech_log の ts を録画の時刻に直し、話した順に speak と対応させる)
slog = [json.loads(x) for x in (LAB / "runs" / "speech" / "speech_log.jsonl").read_text().splitlines() if x.strip()]
for s in slog:
    s["rt"] = datetime.fromisoformat(s["ts"]).timestamp() - CALL["t0"]
voice = []
for sp in speaks:
    s = min(slog, key=lambda x: abs(x["rt"] - sp["rt"]))
    assert abs(s["rt"] - sp["rt"]) < 3, (s, sp["rt"])
    (P / "audio" / "speech_v2").mkdir(exist_ok=True)
    shutil.copy(LAB / "runs" / "speech" / s["file"], P / "audio" / "speech_v2" / s["file"])
    voice.append({**s, "src": f"audio/speech_v2/{s['file']}", "rt": sp["rt"]})


# ---------------------------------------------------------------- 文の切れ目(声の wav の中の、文と文のあいだの無音)
from spans import sentence_spans  # noqa: E402  (make_lamp_v3 と同じ切り方)


# ---------------------------------------------------------------- 録画の画面(倍率と寄り)
PAGE = [1.45, 520, 588]          # 下端 ≈ 960: 通話途中の集計の行(録画の y 970〜)は映さない          # 左のページ(聞き書き)いっぱい。右上に消えた行灯が少し入る
RIGHT = [1.5, 1430, 330]         # 右のページ(行灯・ことば・お返事)


def rec_scene(name: str, at: float, dur: float, rt0: float, rate: float = 1.0, z0=None, z1=None, badge: str | None = None, overlays=None, layer: int = 0) -> float:
    return scene("rec", at, dur, src=f"rec/{name}/screen.mp4", **{"from": r2(rt0)}, rate=rate, z0=z0 or PAGE, z1=z1 or z0 or PAGE,
                 badge=badge, overlays=overlays or [], layer=layer)


# ================================================================ s01 けはい(黒味 → 少し開いたふすま)
t = 0.0
sfx("clock_tick", 0.0, vol=0.22, dur=12.0, fo=2.5)
clip("narration/g10.wav", 0.25, NAR["g10"]["dur"], vol=1.35)
caps.append({"start": 0.4, "end": r2(0.25 + NAR["g10"]["dur"] - 0.1), "text": "(ふすまの向こうから)あら、そうなの。ふふっ。", "who": "grandma"})
scene("black", 0.0, 1.4)
e = nar("a01", 1.25)
a2 = e + 0.15
e = nar("a02", a2)
scene("photo", 1.2, a2 + 0.3 - 1.2, src="img/fusuma_ajar.jpg", grade="dusk", z0=1.06, z1=1.12, y0=40, y1=20, fromBlack=1.2, vignette=0.6)
t = scene("photo", a2 + 0.3, e + 0.2 - (a2 + 0.3), src="img/getty_family_meal.jpg", grade="sepia(.45) saturate(.78) brightness(.93) contrast(.95)", z0=1.05, z1=1.11,
          vignette=0.62, notes=[{"t0": 0.4, "text": "イメージ", "side": "right"}])
clip("music/mixkit_22_piano_reflections.mp3", 3.2, 60.0, vol=0.13, fi=3.0)
marks["s01"] = t

# ================================================================ s02 あの日(鳴る電話 → 鳴りやんだ電話)
t2 = t
clip("audio/ring.wav", t2 + 0.05, 1.75, vol=0.42, fo=0.2)
scene("video", t2, 2.0, src="video/phone_ringing.mp4", **{"from": 0.3}, grade="pale", z0=1.03, z1=1.06)
e = nar("n01", t2 + 1.5)
e = nar("n02", e + 0.12)
t = scene("photo", t2 + 2.0, e + 0.15 - (t2 + 2.0), src="img/phone_still.jpg", grade="pale", z0=1.05, z1=1.18,
          notes=[{"t0": 0.1, "t1": 3.6, "text": "作者の祖母に、実際にあったこと", "side": "left"},
                 {"t0": e - (t2 + 2.0) - 5.4, "text": "契約当事者が65歳以上の消費生活相談 33万497件(2025年度・国民生活センター)", "side": "right"}])
marks["s02"] = t

# ================================================================ s03 便り(夜の都会の電話 → 誰もいない実家)
t3 = t
scene("video", t3, 2.2, src="video/apartment_night.mp4", **{"from": 1.0}, grade="night", z0=1.02, z1=1.06)
clip("narration/g11.wav", t3 + 0.25, NAR["g11"]["dur"], vol=0.95)
caps.append({"start": r2(t3 + 0.35), "end": r2(t3 + 0.25 + NAR["g11"]["dur"] - 0.1), "text": NTXT["g11"], "who": "grandma"})
scene("video", t3 + 2.2, 2.3, src="video/phone_hands.mp4", **{"from": 2.5}, grade="night", z0=1.02, z1=1.05, callEnd={"t0": 0.1})
e = nar("a03", t3 + 2.3)
e2 = nar("a04", e + 0.18)
scene("photo", t3 + 4.5, e + 0.18 + 0.2 - (t3 + 4.5), src="img/washitsu_dusk.jpg", grade="dusk", z0=1.04, z1=1.08)
t = scene("photo", e + 0.38, e2 + 0.1 - (e + 0.38), src="img/getty_hands_table.jpg", grade="dusk", z0=1.03, z1=1.09,
          notes=[{"t0": 0.3, "text": "65歳以上の一人暮らし 815万3千人(令和7年国勢調査)", "side": "right"}])
marks["s03"] = t

# ================================================================ s04 行灯(ふすまの「トン」で題 → 墨の図)
t4 = t
sfx("fusuma_ton", t4, vol=0.55)
b1 = t4 + 1.1
e = nar("b01", b1)
b2 = e + 0.1
e = nar("b02", b2)
b3 = e + 0.1
S04_TAIL = 1.0                              # v17: 1.45 → 1.2(実機デモを入れるぶん)
T4 = {"lamp": r2(b1 - t4 + 0.2), "mic": r2(b2 - t4 + 0.5), "phone": r2(b2 - t4 + 1.7), "only": r2(b2 - t4 + 2.9), "off": r2(b3 - t4)}
t = scene("andon", t4, b3 + S04_TAIL - t4, T=T4)
# 図(AndonDiagram)は T を受け取らず、部品の既定の時刻で描く(灯る 1.9 / マイク 3.0 / 電話 4.6 / 「聞くのは」6.4 / 「通話中は」7.6)。
# キャラはその実際の時刻に合わせ、ナレーション(b02 の「部屋のマイクで、祖母の声だけを聞きます」)の位置も渡す。
CHAR["s04"] = {"start": r2(t4), "dur": r2(b3 + S04_TAIL - t4), "T": {"lamp": 1.9, "mic": 3.0, "phone": 4.6, "only": 6.4, "off": 7.6},
               "b02": [r2(b2 - t4), r2(b3 - 0.1 - t4)]}
if (P / "char" / "s04_andon.mov").exists():      # Claude のキャラ(HyperFrames で書き出した透過の映像)
    scene("char", t4, b3 + S04_TAIL - t4, src="char/s04_andon.mov", layer=1, fadeIn=0.01, fadeOut=0.2)
sfx("lamp_on", t4 + T4["lamp"] + 0.3, vol=0.25)
# 音楽は、行灯が消える瞬間にすっと引く
audio[[i for i, c in enumerate(audio) if c["src"].startswith("music/mixkit_22")][0]].update({"dur": r2(t4 + T4["off"] + 0.6 - 3.2), "fadeOut": 1.0})
marks["s04"] = t

# ================================================================ s05 通話(実際の画面。祖母の声だけ。沈黙は実時間で数える)
t5 = t
scene("video", t5, 0.6, src="video/phone_ringing.mp4", **{"from": 0.6}, grade="day", z0=1.06, z1=1.08)
clip("audio/ring.wav", t5, 0.6, vol=0.4, fo=0.12)


def ucap(i: int, at: float, w0: float) -> None:
    u = U[i]
    caps.append({"start": r2(at + u["start"] - w0), "end": r2(at + u["end"] - w0 + 0.45), "text": u["text"].replace("はるかぜ", "春風"), "who": "grandma"})


def seg(w0: float, w1: float, at: float, rate: float = 1.0, z0=None, z1=None, badge=None, sound=True, overlays=None, cap_ids=()) -> float:
    dur = (w1 - w0) / rate
    rec_scene(CALL["name"], at, dur, demo_rt + w0, rate=rate, z0=z0, z1=z1, badge=badge, overlays=overlays)
    if sound:
        clip("audio/S05_v2.wav", at, dur, frm=w0, vol=1.4, fi=0.08, fo=0.12, rate=rate)
    for i in cap_ids:
        ucap(i, at, w0)
    if rate > 1.5:
        sfx("clock_tick", at, vol=0.18, dur=dur, frm=0.0)
    return at + dur


tc = t5 + 0.6
wA0 = EV["pickup"] - 0.2
wB0 = U[2]["start"] - 0.2
# A ×4: 「はい、もしもし」「先週も…」と、相手の時間
nar("b04", tc + 0.05)
tc = seg(wA0, wB0, tc, rate=round((wB0 - wA0) / (NAR["b04"]["dur"] + 0.05 - 0.0), 2), badge=None, sound=False, z0=[1.95, 440, 407], z1=[1.95, 440, 430],
         overlays=[{"kind": "note", "t0": 0.2, "t1": 3.6, "x": 1150, "y": 640, "w": 600, "size": 30, "text": "呼出音を聞き分けて(YAMNet)、ここからは黙って聞く"},
                   {"kind": "note", "t0": 0.5, "t1": 3.7, "x": 1150, "y": 150, "w": 640, "size": 28, "color": "#fbf7ec", "rot": 1, "text": "この帳面は、祖母の台所の画面。家族に届くのは、夕方の便りだけ。"}])
scenes[-1]["badge"] = f"×{scenes[-1]['rate']:.0f} 早送り"
# B 実時間: 「ええ、膝がね、最近ちょっと痛くて。」
wB1 = U[2]["end"] + 0.2
tc = seg(wB0, wB1, tc, cap_ids=[2], z0=[1.95, 440, 430], z1=[1.9, 450, 450])
# C ×10
wD0 = U[4]["start"] - 0.3
tc = seg(wB1, wD0, tc, rate=24, badge="×24 早送り", sound=False, z0=[1.9, 450, 450], z1=PAGE)
# D 実時間: 「今日中なら、半額なんですか。」「はい。」(あいづち)
wD1 = U[4]["end"] + 0.25
tc = seg(wD0, wD1, tc, cap_ids=[4])
# E ×10: あいづちの「はい。」2 つ(同意に数えない)
wF0 = U[6]["end"] + 0.05
tc = seg(wD1, wF0, tc, rate=30, badge="×30 早送り", sound=False)
# F 実時間: いちばん長い沈黙。相手が話している時間を、実時間で数える(最後の 0.5 秒は時計も止める)
wF1 = U[7]["start"] - 0.05
gmax = max(u.get("pre_pause", 0) for u in utts)
tF = tc
tc = seg(wF0, wF1, tc, z0=PAGE, z1=[1.5, 540, 600], badge="実時間", sound=True,
         overlays=[{"kind": "timer", "t0": 0.0, "t1": wF1 - wF0, "max": gmax, "x": 1250, "y": 560, "line": "この沈黙のあいだ、話しているのは、たぶん電話の相手。"}])
sfx("clock_tick", tF, vol=0.3, dur=(wF1 - wF0) - 0.55, frm=0.0)
# G 実時間: 「でも、息子に聞いてみないと…」
wG1 = U[7]["end"] + 0.2
tc = seg(wF1, wG1, tc, cap_ids=[7])
# H 早送り: 声がだんだん小さくなる(ナレーション 2 行目)
wI0 = U[13]["start"] - 0.25
rateH = round((wI0 - wG1) / (NAR["b05"]["dur"] + 0.2), 1)
nar("b05", tc + 0.1)
tc = seg(wG1, wI0, tc, rate=rateH, badge=f"×{rateH:g} 早送り", sound=False,
         overlays=[{"kind": "stamp", "t0": 0.25, "x": 800, "y": 450, "text": "断りの言葉", "size": 38}])
# I 実時間: 「…じゃあ、お願いします。」(いちばん小さな声)
pu = min((u for u in utts if not u.get("backchannel")), key=lambda u: abs(u["rt"] - (demo_rt + U[13]["end"] + 2.0)))
wI1 = U[13]["end"] + 0.25
tc = seg(wI0, wI1, tc, cap_ids=[13], z0=PAGE, z1=[1.5, 540, 600],
         overlays=[{"kind": "stamp", "t0": 0.4, "x": 760, "y": 850, "text": f"いつもの声より {pu['db_rel']:+.0f} dB", "size": 36}])
# J ×30: 受話器を置く → 集計
wJ1 = ended["rt"] - demo_rt + 0.6
tc = seg(wI1, wJ1, tc, rate=60, badge="×60 早送り", sound=False)
sfx("katan", tc - 0.4, vol=0.35)
tc = rec_scene(CALL["name"], tc, 0.8, ended["rt"] + 0.8, z0=[1.35, 560, 860], z1=[1.38, 560, 870],
               overlays=[{"kind": "note", "t0": 0.15, "x": 1130, "y": 120, "w": 520, "size": 28, "text": "行灯は、最後まで消えたまま"},
                         {"kind": "stamp", "t0": 0.3, "x": 880, "y": 430, "text": "断りの言葉 前半1 → 後半0", "size": 28, "rot": 3}])
t = tc
marks["s05"] = t

# ================================================================ s06 ふすまの裏側(早送りで。墨の図)
t6 = t
ma_final = utts[-1]["ma"] if utts and utts[-1].get("ma") else ended.get("ma")
ear11 = json.loads((LAB / "runs" / "eval" / "ear_S11.json").read_text())["ma"]
pick = EV["pickup"]
s05segs = [[r2(u["start"] - pick), r2(u["end"] - pick)] for u in U]
s11segs = [[r2(u["start"] - S11["events"][1]["t"]), r2(u["end"] - S11["events"][1]["t"])] for u in S11["utterances"]]
asr13 = U[13]["asr"].replace("じゃあ、", "じゃあ")      # 収録の耳の表記(画面と同じ)
line = f"{pu['clock']} 祖母「{asr13}」 間{pu['pre_pause']:.1f}s 声高{pu['f0_rel'] * 100:+.0f}% 声量{pu['db_rel']:+.0f}dB 話速{pu['rate_rel'] * 100:+.0f}%"
sfx("fusuma_slide", t6 + 0.15, vol=0.45)
clip("music/wood_rhythm.wav", t6 + 0.7, 40.0, vol=0.11, fi=0.6)
c2 = t6 + 0.6                               # v17: c01「ふすまの裏側を、早送りで。」は外した
e = nar("c02", c2)
c3 = e + 0.1
e = nar("c03", c3)
d6 = e + 0.15 - t6
scene("ura", t6, d6, s05=s05segs, s05Total=r2(EV["hangup"] - pick), s11=s11segs, s11Total=r2(S11["events"][2]["t"] - S11["events"][1]["t"]), line=line,
      m={"gMax": gmax, "fMax": ear11["max_gap"], "gSelf": round(ma_final["self_ratio"] * 100), "fSelf": round(ear11["self_ratio"] * 100),
         "gOther": round(ma_final["other_ratio_est"] * 100), "fOther": round(ear11["other_ratio_est"] * 100), "dB": int(round(pu["db_rel"]))},
      warp=[[0, 0], [r2(c2 - t6 - 0.1), 2.1], [r2(c3 - t6 - 0.1), 7.5]], postTime=pu["clock"][:5])
scene("video", t6 - 0.35, 1.3, src="video/getty_doors.mp4", **{"from": 2.0}, rate=2.0, grade="warm", z0=1.25, z1=1.42, x=160, layer=1)
t = t6 + d6
marks["s06"] = t

# ================================================================ s07 ふすまの向こうの家族会議(3 つの Claude)
t7 = t
k4 = t7 + 0.15
e = nar("c04", k4)
k5 = e + 0.08
e = nar("c05", k5)
k6 = e + 0.08
e = nar("c06", k6)
d7 = e + 0.4 - t7
# 出典は、この電話(健康食品の電話勧誘・定期購入・先週断った相手からの再度の電話)に関わるものを選ぶ
def _rel(c: dict) -> int:
    t = c.get("title", "")
    return sum(k in t for k in ("定期", "健康", "サプリ", "再勧誘", "電話勧誘", "クーリング")) - 3 * ("光回線" in t or "海産物" in t)
cite = max(reb.get("citations", []) or [{"title": ""}], key=_rel).get("title", "")
dec_clock = (datetime.strptime(ended["clock"], "%H:%M:%S") + __import__("datetime").timedelta(seconds=dec_ev["rt"] - ended["rt"])).strftime("%H:%M")
scene("kaigi", t7, d7, score=final_lo.get("score", 0.85), genuine={"low": "低", "medium": "中", "high": "高"}[reb["genuine_likelihood"]],
      restraint=dec["restraint_note"], cite=cite.split("(")[0], postTime=dec_clock,
      warp=[[0, 0], [r2(k5 - t7 - 0.15), 2.9], [r2(k6 - t7 - 0.15), 7.5]])
scene("slide", t7 + d7 - 0.75, 0.75, src="drawn", mode="close", at=0.0, len=0.55, layer=2)
sfx("fusuma_ton", t7 + d7 - 0.2, vol=0.5)
audio[[i for i, c in enumerate(audio) if c["src"] == "music/wood_rhythm.wav"][0]].update({"dur": r2(t7 + d7 - 0.2 - (t6 + 0.7)), "fadeOut": 0.3})
t = t7 + d7
marks["s07"] = t

# ================================================================ s08 電話のあと(実際の画面。行灯が初めて灯る)
t8 = t
clip("music/mixkit_22_piano_reflections.mp3", t8 + 0.6, 30.0, frm=40.0, vol=0.08, fi=2.0)
first_say = voice[0]
# 0〜0.7 秒: 「部屋が 8 秒静かになってから」(待ち時間を早回し)
tc = rec_scene(CALL["name"], t8, 0.5, first_say["rt"] - 2.0, rate=4.0, z0=RIGHT, z1=RIGHT,
               overlays=[{"kind": "count", "t0": 0.0, "t1": 0.3, "hold": 0.2, "from": 0, "to": 8, "x": 1200, "y": 820, "label": "部屋が静かになってから"},
                         {"kind": "corner", "t0": 0.0, "text": "会話は一部を詰めています", "side": "right"}], layer=0)
sfx("lamp_on", tc - 0.1, vol=0.3)


# 行灯(キャラ)の声: いまの声(AivisSpeech「まお」おちつき)で、文ごとに録画のときの長さへ合わせて読み直したもの(make_lamp_v3.py)
LAMP_SPEECH: list[dict] = []         # 動画のキャラの口の動きに使う(行灯が話した区間)
V3 = LAB / "runs" / "speech_v3"
V3_INDEX = json.loads((V3 / "index.json").read_text())["files"] if (V3 / "index.json").exists() else {}


def say(v: dict, at: float, part: str | None = None, tag: str | None = None) -> float:
    """ふすまごしの声(文の一部だけを使うときは part に文)。画面は話し始めの所から"""
    path = LAB / "runs" / "speech" / v["file"]
    spans = sentence_spans(path, v["text"])
    k = None
    if part:
        sp = [s for s in spans if s[2].startswith(part[:6])]
        assert sp, (part, spans)
        s0, s1, txt = sp[0]
        k = spans.index(sp[0])
    else:
        s0, s1, txt = spans[0][0], spans[-1][1], v["text"]
        k = 0 if len(spans) == 1 else None
    d = s1 - s0
    ov = [{"kind": "note", "t0": 0.15, "x": 120, "y": 740, "w": 560, "size": 30, "text": tag, "color": "#fff7d6"}] if tag else []
    rec_scene(CALL["name"], at, d + 0.25, v["rt"] + 0.15 + s0, z0=RIGHT, z1=[1.52, 1430, 340], overlays=ov)
    rows = V3_INDEX.get(v["file"])
    if rows and k is not None and k < len(rows):
        row = rows[k]
        (P / "audio" / "speech_v3").mkdir(exist_ok=True)
        shutil.copy(V3 / row["wav"], P / "audio" / "speech_v3" / row["wav"])
        clip(f"audio/speech_v3/{row['wav']}", at, d + 0.12, frm=0.0, vol=0.84, fi=0.02, fo=0.08)   # 祖母の答えより大きくならないよう少し下げる
        LAMP_SPEECH.append({"start": r2(at), "dur": r2(d), "wav": f"audio/speech_v3/{row['wav']}", "text": txt.strip()})
    else:
        clip(v["src"], at, d + 0.12, frm=s0, vol=1.0, fi=0.03, fo=0.08)
        LAMP_SPEECH.append({"start": r2(at), "dur": r2(d), "wav": v["src"], "from": r2(s0), "text": txt.strip()})
    caps.append({"start": r2(at), "end": r2(at + d), "text": txt.strip(), "who": "fusuma"})
    return at + d + 0.08


def answer(k: int, at: float, part: str | None = None, tag: str | None = None) -> float:
    inj = injects[k - 1]
    path = P / "audio" / f"R02v2_a{k}.wav"
    text = R02["utterances"][k - 1]["text"]
    spans = sentence_spans(path, text)
    if part:
        sp = [s for s in spans if s[2].startswith(part[:6])]
        assert sp, (part, spans)
        s0, s1, txt = sp[0]
    else:
        s0, s1, txt = spans[0][0], spans[-1][1], text
    d = s1 - s0
    ov = [{"kind": "note", "t0": 0.15, "x": 120, "y": 740, "w": 560, "size": 30, "text": tag, "color": "#fff7d6"}] if tag else []
    rec_scene(CALL["name"], at, d + 0.25, inj["rt"] + 0.3 + s0, z0=[1.52, 1430, 340], z1=[1.54, 1430, 350], overlays=ov)
    clip(f"audio/R02v2_a{k}.wav", at, d + 0.12, frm=s0, vol=1.0, fi=0.03, fo=0.08)
    caps.append({"start": r2(at), "end": r2(at + d), "text": txt.strip(), "who": "grandma"})
    return at + d + 0.08


tc = say(voice[0], tc, tag="質問は、一度にひとつ")
tc = answer(1, tc, part="今日だけ半額")
# v17: say(voice[1], part="そうだったんだ", tag="責めない") は外した(実機デモを入れるぶん)
tc = say(voice[2], tc, part="この話、", tag="家族に伝える前に、本人に聞く")
tc = answer(3, tc)

t = tc
marks["s08"] = t


def pi_pip(meta_name: str, rec_name: str, t_from: float, t_to: float, x: int, y: int, w: int, label: str, sub: str = "", cut: float | None = None,
           card_bottom: int | None = None, note: str = "") -> None:
    """Pi の画面(実機の録画。録画のときのイベントを流し直して撮った)を、同じ時刻の画面の録画にあわせて小窓で重ねる。"""
    mp = P / "char" / f"{meta_name}.json"
    if not mp.exists():
        return
    cap = json.loads(mp.read_text())
    segs = [x_ for x_ in scenes if x_["kind"] == "rec" and x_["src"] == f"rec/{rec_name}/screen.mp4" and t_from <= x_["start"] < t_to]
    segs.sort(key=lambda x_: x_["start"])
    for i, sc in enumerate(segs):
        off = sc["from"] - cap["rec_from"]
        rate = sc.get("rate", 1.0)
        d = sc["dur"] if cut is None else min(sc["dur"], cut - sc["start"])
        if d <= 0 or off < 0 or off + d * rate > cap["dur"] + 0.05:
            continue
        last = i == len(segs) - 1 or cut is not None
        # 下の録画は切れ目でふわっと重なるので、小窓も次の切れ目まで 0.15 秒のばし、次の窓を上からふわっと出す
        scene("char", sc["start"], d + (0.0 if last else 0.15), src=cap["src"], **{"from": r2(off)}, rate=rate, panel=True, x=x, y=y, w=w,
              label=label, sub=sub, layer=1, fadeIn=0.3 if i == 0 else 0.15, rise=i == 0, fadeOut=0.3 if last else 0.0,
              **({"cardBottom": card_bottom} if card_bottom else {}), **({"note": note} if note else {}))


# 台所の Pi: 同じ合図で、Claude のキャラが話して・聞いて・うなずく(録画の左上の小窓)
# 帳面の左上(通話の見出しと前の電話の切れ端。どちらも s05 で見せた)を、半端にのぞかないよう台紙で隠しきる
pi_pip("pi_after", CALL["name"], t8, marks["s08"], x=46, y=62, w=440, label="Pi の画面(実機)", sub="同じ合図で、話す・聞く・うなずく",
       card_bottom=478, note="Pi に送るのは、気分の名前と秒数と口の開きだけ。文字は一文字も送らない")

# ================================================================ s09 「つい」(文字起こしが消える → 14:05 から 18:00 へ)
t9 = t
lines9 = ["そういえば、さっきの電話、なんだったの?", R02["utterances"][0]["text"], "そうだったんだ、膝のこと気になってたものね。", "この話、健太にも話しておいていい?", R02["utterances"][2]["text"]]
e = nar("d01", t9 + 0.35)
end_clock = (datetime.strptime(ended["clock"], "%H:%M:%S") + __import__("datetime").timedelta(seconds=purged_rt - ended["rt"])).strftime("%H:%M")
t = scene("tsui", t9, e + 0.15 - t9, lines=lines9, fromClock=end_clock, video="video/getty_room_light.mp4", **{"from": 4.0})
sfx("clock_tick", t9 + 1.0, vol=0.16, dur=(e - t9) - 0.6, fo=0.8)
marks["s09"] = t

# ================================================================ s10 夕方の便り(郵便受けの「コトン」→ 家族のスマホ → 便りができるまで)
t10 = t
LET = rec(args.letter)
lev = LET["ev"]
letter_ev = next(e for e in lev if e["type"] == "letter")
grades = [e for e in lev if e["type"] == "managed" and e.get("stage") == "grade"]
done_ev = [e for e in lev if e["type"] == "managed" and e.get("stage") == "done"]
if done_ev and done_ev[-1].get("evaluations"):
    grades = done_ev[-1]["evaluations"]
IN10 = 1.6                                  # 最初の 1.6 秒は、健太の夕飯どき(イメージ)
scene("video", t10, IN10 + 0.1, src="video/getty_teishoku.mp4", **{"from": 2.0}, grade="warm", z0=1.03, z1=1.06,
      notes=[{"t0": 0.2, "text": "18:00 健太の夕飯どき(イメージ)", "side": "left"}], layer=1)
sfx("mailbox_koton", t10 + IN10 + 0.05, vol=0.55)
clip("music/wood_rhythm.wav", t10 + 4.5, 20.0, frm=8.0, vol=0.09, fi=1.0)
e = nar("d02", t10 + 0.25)
f3 = e + 0.08
e = nar("d03", f3)
f4 = e + 0.08
e = nar("d04", f4)
d10 = e + 0.1 - t10
PHONE0 = [1.55, 1525, 380]
PHONE1 = [1.55, 1525, 700]
def gist(e: dict) -> str:
    """採点役の説明(英語の前置き + 日本語の本文)から、決め手の一文だけを拾う(家族の画面と同じ規則)"""
    body = re.sub(r"^[\s\S]*?\((?:partially |not )?met\):\s*", "", e.get("explanation") or "")
    sents = [x.strip() for x in re.split(r"(?<=。)", body) if x.strip()]
    if e.get("result") == "satisfied":
        pick = next((x for x in sents if re.search(r"\d+\s*字", x) and "以内" in x), None) or (sents[0] if sents else "")
    else:
        tot = next((x for x in sents if "合計" in x and re.search(r"\d+\s*字", x)), None)
        over = next((x for x in sents if "超え" in x and x is not tot), None)
        if tot and over:
            pick = "…" + tot[tot.index("合計"):] + over         # 記録の文のまま(合計の所から)
        else:
            pick = over or tot or (sents[0] if sents else "")
    pick = re.sub(r"^([(（]\d+[)）]\s*|\d+\.\s*|ただし、?|また、?|なお、?)", "", pick)
    return pick if len(pick) <= 48 else pick[:47] + "…"


evals = [{"ok": g.get("result") == "satisfied", "text": gist(g)} for g in grades]
tools = [e for e in lev if e["type"] == "managed" and e.get("stage") == "tool" and e.get("target")]
tool_line = next((f"{e.get('name', 'read')} {e['target']}" for e in tools if "/karte/" in e.get("target", "")), "read /mnt/memory/fusuma-memory/karte/…")
rec_scene(LET["name"], t10 + IN10, d10 - IN10, letter_ev["rt"] - 0.1, z0=PHONE0, z1=PHONE1,
          overlays=[{"kind": "letterflow", "t0": f4 - (t10 + IN10) - 0.4, "evals": evals, "tool": tool_line[:96]}])
if grades:
    sfx("bell", t10 + (f4 - t10) + 4.4, vol=0.22)
t = t10 + d10
for c in audio:
    if c["src"] == "music/wood_rhythm.wav" and c["start"] > t10:
        c.update({"dur": r2(d10 - 4.5 + 0.3), "fadeOut": 0.4})
pi_pip("pi_letter", LET["name"], t10, t10 + d10 + 0.01, x=52, y=62, w=420, label="家族の机の Pi(実機)",
       sub="届くのは「便りが来た」ことだけ", cut=t10 + IN10 + 7.2)
marks["s10"] = t

# ================================================================ s11 試験と、Claude Code での作り方
t11 = t
sfx("fusuma_slide", t11, vol=0.4)
clip("music/wood_rhythm.wav", t11 + 0.3, 20.0, frm=20.0, vol=0.1, fi=0.4)
g5 = t11 + 0.45
e = nar("d05", g5)
g6 = e + 0.12
e = nar("d06", g6)
d11 = e + 0.15 - t11
hook = "ふすまごしの原則チェックで止めました: 脳(Claude 側)に音声を送る記述があります。"
scene("proof", t11, d11, hook=hook, warp=[[0, 0], [r2(g6 - t11 - 0.25), 7.0]])
scene("slide", t11, 0.95, src="drawn", mode="open", at=0.0, len=0.7, layer=2)
sfx("typing", g6 + 0.3, vol=0.25, dur=2.6)
for c in audio:
    if c["src"] == "music/wood_rhythm.wav" and c["start"] > t11:
        c.update({"dur": r2(d11 - 0.6), "fadeOut": 0.5})
t = t11 + d11
marks["s11"] = t

# ================================================================ s11b 実機: 本物そっくりの詐欺電話でも(P01)
# 相手の声は、警視庁 YouTube「スマホ防犯教室 架空料金請求詐欺編」の再現ドラマ(犯人役)。祖母の声は合成。
# Pi の画面は、P01 を本番の流れ(耳 → 聞き役 → 反論役 → まとめ役 → 電話のあとの会話)に流したときの実機の録画。
PD = V / "assets" / "rec" / "call_P01_v1"
if (PD / "pi_live.json").exists():
    pm = json.loads((PD / "pi_live.json").read_text())
    pev = json.loads((PD / "timing.json").read_text())["events"]
    to_v = lambda ts: ts + pm["clock_offset_pi_minus_mac"] - pm["pi_rec_t0_pi_clock"]       # Mac の時刻 → Pi の録画の秒
    demo_v = to_v(next(e for e in pev if e["type"] == "demo")["_ts"])
    say3 = [e for e in pev if e["type"] == "speak"][2]                                       # 「…行く前にケンタと一緒に確かめてみない?」
    inj3 = [e for e in pev if e["type"] == "inject"][2]                                      # 祖母「えっ…そうなの? じゃあ…やめておくわ。…」
    say3_wav = LAB / "runs" / "speech" / (datetime.fromisoformat(say3["ts"]).strftime("%Y%m%d-%H%M%S") + "_fusuma.wav")
    for src, dst in ((PD / "pi_live.mp4", P / "char" / "pi_p01.mp4"), (LAB / "data" / "scenarios" / "P01.wav", P / "audio" / "P01.wav"),
                     (say3_wav, P / "audio" / "p01_say3.wav"), (LAB / "data" / "scenarios" / "P02_a3.wav", P / "audio" / "P02_a3.wav")):
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy(src, dst)
    p01u = json.loads((LAB / "data" / "scenarios" / "P01.truth.json").read_text())["utterances"]
    u5 = next(u for u in p01u if u["text"].startswith("えっ……よんまん"))
    t11b = t
    sfx("fusuma_slide", t11b, vol=0.3)
    NOTE = "実機の Pi ・ 架空料金請求の電話(相手の声: 警視庁の再現ドラマ)"
    # A 通話中: 「えっ……4万円も、するんですか。」 — 画面は沈んだまま、薄目で電話のほうをのぞく
    a0, a1 = u5["start"] + 0.07, u5["end"]
    dA = a1 - a0
    tA = t11b + 0.02
    scene("video", tA, dA + 0.1, src="char/pi_p01.mp4", **{"from": r2(demo_v + a0)}, grade="none", z0=1.0, z1=1.03,
          notes=[{"t0": 0.05, "text": NOTE, "side": "left"}, {"t0": 0.2, "text": "通話中: 光らない・話さない。でも、のぞく", "side": "right"}])
    clip("audio/P01.wav", tA, dA + 0.05, frm=r2(a0), vol=1.3, fi=0.04, fo=0.08)
    caps.append({"start": r2(tA), "end": r2(tA + dA), "text": "えっ……4万円も、するんですか。", "who": "grandma"})
    # B 電話のあと: 「行く前に、ケンタと一緒に確かめてみない?」
    b_s0, b_s1 = 6.88, 9.80
    tB = tA + dA + 0.06
    dB = b_s1 - b_s0
    scene("video", tB, dB + 0.06, src="char/pi_p01.mp4", **{"from": r2(to_v(say3["_ts"]) + 0.1 + b_s0)}, grade="none", z0=1.03, z1=1.06,
          notes=[{"t0": 0.05, "text": NOTE, "side": "left"}, {"t0": 0.1, "text": "電話のあと: 本人に聞く", "side": "right"}])
    clip("audio/p01_say3.wav", tB, dB + 0.1, frm=b_s0, vol=0.95, fi=0.02, fo=0.08)
    caps.append({"start": r2(tB), "end": r2(tB + dB), "text": "行く前に、ケンタと一緒に、確かめてみない?", "who": "fusuma"})
    # C 祖母: 「じゃあ……やめておくわ。孫に、電話してみるね。」
    c_s0, c_s1 = 2.04, 5.86
    tCc = tB + dB + 0.06
    dC = c_s1 - c_s0
    scene("video", tCc, dC + 0.12, src="char/pi_p01.mp4", **{"from": r2(to_v(inj3["_ts"]) + c_s0)}, grade="none", z0=1.06, z1=1.08,
          notes=[{"t0": 0.05, "text": NOTE, "side": "left"}])
    clip("audio/P02_a3.wav", tCc, dC + 0.1, frm=c_s0, vol=1.2, fi=0.02, fo=0.1)
    caps.append({"start": r2(tCc), "end": r2(tCc + dC), "text": "じゃあ……やめておくわ。孫に、電話してみるね。", "who": "grandma"})
    t = tCc + dC + 0.12
    marks["s11b"] = t

# ================================================================ s12 健太(同じ膝の話。こんどは、家族から)
t12 = t
clip("music/mixkit_22_piano_reflections.mp3", t12, 30.0, frm=96.0, vol=0.12, fi=1.0)
e = nar("e01", t12 + 0.3)
rec_scene(LET["name"], t12, 1.4, LET["dur"] - 1.6, z0=[1.7, 1525, 900], z1=[1.72, 1525, 905], overlays=[{"kind": "tap", "t0": 0.65, "x": 1248, "y": 939}])
sfx("stamp_kon", t12 + 1.0, vol=0.25)
scene("video", t12 + 1.4, 1.5, src="video/phone_ringing.mp4", **{"from": 0.2}, grade="dusk", z0=1.03, z1=1.06)
clip("audio/ring.wav", t12 + 1.45, 1.4, vol=0.35, fo=0.2)
ks = max(e + 0.1, t12 + 2.9)
kh = ks + 2.4
scene("video", t12 + 2.9, kh - (t12 + 2.9), src="video/phone_hands.mp4", **{"from": 5.0}, grade="sepia(.2) saturate(1.05) brightness(1.35) contrast(1.05)", z0=1.02, z1=1.05)
scene("photo", kh, ks + NAR["k01"]["dur"] + 0.2 - kh, src="img/getty_hands_table.jpg", grade="warm", z0=1.08, z1=1.14, notes=[{"t0": 0.3, "text": "イメージ", "side": "right"}])
e = nar("k01", ks, who="kenta", vol=1.5)
gs = e + 0.15
ph0 = e + 0.1
e = nar("g01", gs, who="grandma", vol=1.2)
t = scene("photo", ph0, e + 0.55 - ph0, src="img/oldroom_light.jpg", grade="dusk", z0=1.04, z1=1.08)
scene("ghost", e + 0.05, 1.3, t0=0.0, t1=1.3, text=U[2]["text"], layer=1)
marks["s12"] = t

# ================================================================ s13 結び(ふすまが閉まりきってから、祖母の声。静けさのあとに標語)
t13 = t
CLOSE_AT, CLOSE_LEN = 0.2, 1.2
sfx("fusuma_slide", t13 + CLOSE_AT, vol=0.3)
sfx("fusuma_ton", t13 + CLOSE_AT + CLOSE_LEN - 0.05, vol=0.35)
g12_at = t13 + CLOSE_AT + CLOSE_LEN + 0.45
clip("narration/g12.wav", g12_at, NAR["g12"]["dur"], vol=1.35)
caps.append({"start": r2(g12_at + 0.1), "end": r2(g12_at + NAR["g12"]["dur"]), "text": "(ふすまの向こうで)それがね、今日ね、", "who": "grandma"})
e = nar("e02", g12_at + NAR["g12"]["dur"] + 0.4)
tag_at = e + 0.75 - t13                    # 1 秒ほど、音のない間
nar("e03", t13 + tag_at, cap=False)        # 標語はふすまの紙の上に書くので、字幕は出さない
title_at = tag_at + NAR["e03"]["dur"] + 0.85
nar("e04", t13 + title_at, cap=False)
d13 = title_at + 2.0                       # 題名は 2 秒見せる(v17)
for c in audio:
    if c["src"].startswith("music/mixkit_22") and c["start"] >= t12:
        c.update({"dur": r2(t13 + tag_at - c["start"] + 0.6), "fadeOut": 1.5})
t = scene("end", t13, d13, bg="img/oldroom_light.jpg", closeAt=CLOSE_AT, closeLen=CLOSE_LEN, tagAt=r2(tag_at), titleAt=r2(title_at), repo=REPO_URL)
marks["s13"] = t

duration = round(t, 2)

# ---------------------------------------------------------------- 字幕の改行(句読点で折り返す)
BOX = 1560 - 60
LABEL = 5 * 26 + 18


def _split(text: str, n: int) -> list[str] | None:
    cands = [i + 1 for i, ch in enumerate(text[:-1]) if ch in "、。？！?」"]
    cuts: list[int] = []
    for k in range(1, n):
        ok = [c for c in cands if c > (cuts[-1] if cuts else 0) + 3 and c < len(text) - 3]
        if not ok:
            return None
        cuts.append(min(ok, key=lambda c: abs(c - len(text) * k / n)))
    return [text[a:b] for a, b in zip([0] + cuts, cuts + [len(text)])]


def layout_caption(c: dict) -> None:
    text = c["text"]
    first = BOX - (LABEL if c.get("who") not in (None, "narr") else 0)
    for size, max_lines in ((42, 2), (38, 2), (40, 3)):
        if len(text) * size * 1.04 <= first:
            c["size"] = size
            return
        for n in range(2, max_lines + 1):
            parts = _split(text, n)
            if parts and len(parts[0]) * size * 1.04 <= first and all(len(x) * size * 1.04 <= BOX for x in parts[1:]):
                c["text"], c["size"] = "\n".join(parts), size
                return
    c["size"] = 40


for c in caps:
    layout_caption(c)

# ---------------------------------------------------------------- HyperFrames(Claude のキャラ)へ時刻を渡す
HF = V / "hyperframes" / "lantern" / "assets"
if HF.exists():
    RIG = LAB / "app" / "web" / "lantern" / "rig.js"      # キャラは 1 つのファイル: Pi のキオスクと同じ rig.js を使う
    if RIG.exists():
        shutil.copy(RIG, HF / "rig.js")
    (HF / "tracks.js").write_text("// build_timeline_v2.py が書き出す(手で直さない)\nwindow.TRACKS = " +
                                  json.dumps(CHAR, ensure_ascii=False, indent=1) + ";\n")
OUT.write_text(json.dumps({"duration": duration, "scenes": scenes, "audio": audio, "captions": caps, "marks": marks, "lamp": LAMP_SPEECH}, ensure_ascii=False, indent=1))
prev = 0.0
print(f"duration {duration:.1f}s  scenes {len(scenes)}  audio {len(audio)}  captions {len(caps)}")
for k, v in marks.items():
    print(f"  {k}: {prev:6.1f} → {v:6.1f}  ({v - prev:4.1f}s)")
    prev = v

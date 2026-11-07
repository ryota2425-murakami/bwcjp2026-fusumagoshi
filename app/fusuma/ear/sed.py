"""音イベント検出(YAMNet / ONNX)と登録音の照合。

- YAMNet: AudioSet 521 クラス、0.96 秒窓・0.48 秒ホップ。スコアは確率として扱わない。
- 登録音: 家の電話の呼出音・受話器の音などを数秒登録し、YAMNet の 1024 次元埋め込みの平均を
  テンプレートにして、入力とのコサイン類似度で判定する(汎用クラスだけに頼らない)。
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf

from .. import config

HOP = 0.48
WIN = 0.96
IDX = {
    "speech": 0, "telephone": 383, "bell": 384, "ringtone": 385, "dtmf": 386, "dial_tone": 387,
    "doorbell": 349, "ding_dong": 350, "beep": 475, "click": 485, "television": 518, "music": 132,
}


@dataclass
class Frame:
    t: float                      # 窓の開始(秒)
    scores: np.ndarray            # (521,)
    emb: np.ndarray               # (1024,)
    rms_db: float

    def top(self, labels: list[str], k: int = 3) -> list[tuple[str, float]]:
        idx = np.argsort(self.scores)[::-1][:k]
        return [(labels[i], float(self.scores[i])) for i in idx]


class SoundEvents:
    def __init__(self, onnx_path: Path = config.YAMNET_ONNX, enroll_dir: Path = config.ENROLL_DIR):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.sess = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
        with open(config.YAMNET_CLASSES, newline="") as f:
            self.labels = [row[2] for row in list(csv.reader(f))[1:]]
        self.templates: dict[str, np.ndarray] = {}
        for name in ("ring", "pickup", "hangup", "dial"):
            p = enroll_dir / f"{name}_16k.wav"
            if p.exists():
                self.enroll(name, sf.read(p, dtype="float32")[0])

    # ---- 推論 ----
    def run(self, wav16: np.ndarray, t0: float = 0.0) -> list[Frame]:
        if len(wav16) < int(WIN * config.SR):
            wav16 = np.pad(wav16, (0, int(WIN * config.SR) - len(wav16)))
        scores, emb, _ = self.sess.run(None, {"waveform": wav16.astype(np.float32)})
        frames = []
        for i in range(scores.shape[0]):
            s = int((i * HOP) * config.SR)
            seg = wav16[s:s + int(WIN * config.SR)]
            rms = float(np.sqrt(np.mean(seg ** 2) + 1e-12))
            frames.append(Frame(t=t0 + i * HOP, scores=scores[i], emb=emb[i], rms_db=20 * np.log10(rms + 1e-12)))
        return frames

    # ---- 登録音 ----
    def enroll(self, name: str, wav16: np.ndarray) -> None:
        frames = self.run(wav16)
        loud = [f for f in frames if f.rms_db > -50] or frames
        m = np.mean([f.emb for f in loud], axis=0)
        self.templates[name] = m / (np.linalg.norm(m) + 1e-9)

    def match(self, frame: Frame) -> dict[str, float]:
        v = frame.emb / (np.linalg.norm(frame.emb) + 1e-9)
        return {k: float(np.dot(v, t)) for k, t in self.templates.items()}

    # ---- 判定 ----
    def classify(self, frame: Frame, thr: float = 0.8) -> dict:
        """1 フレームを判定。登録音の類似度(閾値 thr は実機で調整)と、汎用クラスのスコアを併用。"""
        sims = self.match(frame) if self.templates else {}
        s = frame.scores
        phone_cls = max(s[IDX["bell"]], s[IDX["ringtone"]], s[IDX["telephone"]])
        out = {
            "t": round(frame.t, 2),
            "sims": {k: round(v, 3) for k, v in sims.items()},
            "phone": float(phone_cls), "speech": float(s[IDX["speech"]]), "tv": float(max(s[IDX["television"]], s[IDX["music"]])),
            "doorbell": float(max(s[IDX["doorbell"]], s[IDX["ding_dong"]])), "dtmf": float(s[IDX["dtmf"]]),
            "rms_db": round(frame.rms_db, 1), "top": frame.top(self.labels),
        }
        event = None
        if frame.rms_db > -45:
            if sims.get("ring", 0) >= thr or phone_cls > 0.35:
                event = "ring"
            elif sims.get("dial", 0) >= thr or s[IDX["dtmf"]] > 0.3:
                event = "dial"
            elif out["doorbell"] > 0.4:
                event = "doorbell"
            elif max(sims.get("pickup", 0), sims.get("hangup", 0)) >= thr and s[IDX["speech"]] < 0.5:
                event = "handset"   # 受話器の上げ下げ(どちらかは状態機械が文脈で決める)
        out["event"] = event
        return out

"""韻律(声の様子): parselmouth(Praat)で F0・強度、かなから話速、あいづち判定。

値は「その人のいつもの声」(ベースライン)に対する相対値で出す。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import parselmouth
import pykakasi

from .. import config

_kks = pykakasi.kakasi()
_SMALL = set("ゃゅょぁぃぅぇぉゎ")


def morae(text: str) -> int:
    hira = "".join(i["hira"] for i in _kks.convert(text))
    n = 0
    for ch in hira:
        if "ぁ" <= ch <= "ゖ" or ch == "ー":
            if ch not in _SMALL:
                n += 1
        elif ch.isdigit():
            n += 2
    return n


def measure(audio16: np.ndarray) -> dict:
    snd = parselmouth.Sound(audio16.astype(np.float64), sampling_frequency=config.SR)
    pitch = snd.to_pitch_ac(time_step=0.01, pitch_floor=75, pitch_ceiling=500)
    f0 = pitch.selected_array["frequency"]
    voiced = f0[f0 > 0]
    frame = int(0.02 * config.SR)
    rms = np.array([np.sqrt(np.mean(audio16[i:i + frame] ** 2) + 1e-12) for i in range(0, max(1, len(audio16) - frame), frame)])
    db = 20 * np.log10(rms + 1e-12)
    loud = db[db > db.max() - 25] if len(db) else db
    return {
        "dur": round(len(audio16) / config.SR, 2),
        "f0": round(float(np.median(voiced)), 1) if len(voiced) else None,
        "db": round(float(np.mean(loud)), 1) if len(loud) else None,
        "voiced_ratio": round(len(voiced) / max(1, len(f0)), 2),
    }


@dataclass
class Baseline:
    """いつもの声。普段の会話(本物の電話・夕方のおしゃべり)から更新する。"""
    f0: float = 160.0
    db: float = -24.0
    rate: float = 7.0       # モーラ/秒
    n: int = 0

    def update(self, f0: float | None, db: float | None, rate: float | None, w: float = 0.15) -> None:
        if self.n == 0:
            self.f0, self.db, self.rate = f0 or self.f0, db or self.db, rate or self.rate
        else:
            if f0: self.f0 = (1 - w) * self.f0 + w * f0
            if db: self.db = (1 - w) * self.db + w * db
            if rate: self.rate = (1 - w) * self.rate + w * rate
        self.n += 1

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> "Baseline":
        if path.exists():
            return cls(**json.loads(path.read_text()))
        return cls()


def is_backchannel(text: str, dur: float) -> bool:
    t = text.strip("、。！？!?…「」 ")
    if dur >= config.BACKCHANNEL_MAX_SEC + 0.15:   # VAD の前後パディング分を許容
        return False
    return len(t) <= 4 and any(t.startswith(w) for w in config.BACKCHANNEL_WORDS)


def relative(feat: dict, text: str, base: Baseline) -> dict:
    m = morae(text)
    rate = m / feat["dur"] if feat["dur"] > 0.3 and m >= 3 else None
    return {
        "morae": m,
        "rate": round(rate, 2) if rate else None,
        "f0_rel": round(feat["f0"] / base.f0 - 1, 3) if feat["f0"] else None,
        "db_rel": round(feat["db"] - base.db, 1) if feat["db"] is not None else None,
        "rate_rel": round(rate / base.rate - 1, 3) if rate else None,
    }

"""Silero VAD による発話区間の切り出し(ストリーミング)。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch
from silero_vad import load_silero_vad

from .. import config

CHUNK = 512  # 16kHz で 32ms


@dataclass
class Segment:
    start: float
    end: float
    audio: np.ndarray = field(repr=False)

    @property
    def dur(self) -> float:
        return self.end - self.start


class StreamSegmenter:
    """32ms ずつ受け取り、発話区間が閉じたら Segment を返す。"""

    def __init__(self, threshold: float = config.VAD_THRESHOLD, min_silence_ms: int = config.VAD_MIN_SILENCE_MS,
                 min_speech_ms: int = config.VAD_MIN_SPEECH_MS, pad_ms: int = config.VAD_PAD_MS):
        torch.set_num_threads(1)
        self.model = load_silero_vad()
        self.thr_on, self.thr_off = threshold, threshold - 0.15
        self.min_sil = int(min_silence_ms / 32)
        self.min_speech = min_speech_ms / 1000
        self.pad = int(pad_ms / 1000 * config.SR)
        self.reset()

    def reset(self) -> None:
        self.model.reset_states()
        self.t = 0.0                   # 受け取った音声の累積時間
        self.buf: list[np.ndarray] = []
        self.history = np.zeros(0, dtype=np.float32)
        self.in_speech = False
        self.silence_run = 0
        self.seg_start = 0.0
        self.muted_until = -1.0

    def mute_until(self, t: float) -> None:
        """端末自身が話している間は聞かない(半二重)。"""
        self.muted_until = t

    def prob(self, chunk: np.ndarray) -> float:
        with torch.no_grad():
            return float(self.model(torch.from_numpy(chunk), config.SR).item())

    def feed(self, chunk: np.ndarray) -> list[Segment]:
        assert len(chunk) == CHUNK
        out: list[Segment] = []
        p = self.prob(chunk) if self.t >= self.muted_until else 0.0
        self.history = np.concatenate([self.history, chunk])[-self.pad - CHUNK:]
        if not self.in_speech:
            if p >= self.thr_on:
                self.in_speech = True
                self.silence_run = 0
                self.seg_start = max(0.0, self.t - self.pad / config.SR)
                self.buf = [self.history.copy()]
        else:
            self.buf.append(chunk)
            if p < self.thr_off:
                self.silence_run += 1
                if self.silence_run >= self.min_sil:
                    audio = np.concatenate(self.buf)
                    trim = (self.silence_run - 2) * CHUNK
                    if trim > 0:
                        audio = audio[:-trim]
                    end = self.seg_start + len(audio) / config.SR
                    if end - self.seg_start >= self.min_speech:
                        out.append(Segment(self.seg_start, end, audio))
                    self.in_speech = False
                    self.buf = []
            else:
                self.silence_run = 0
        self.t += CHUNK / config.SR
        return out

    def flush(self) -> list[Segment]:
        if self.in_speech and self.buf:
            audio = np.concatenate(self.buf)
            self.in_speech = False
            return [Segment(self.seg_start, self.seg_start + len(audio) / config.SR, audio)]
        return []

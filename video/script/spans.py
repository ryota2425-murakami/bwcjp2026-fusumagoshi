"""声の wav の中の、文と文のあいだの無音から、文ごとの区間を決める(build_timeline_v2 と make_lamp_v3 で共用)。"""
import re
from pathlib import Path

import numpy as np
import soundfile as sf


def sentence_spans(path: Path, text: str) -> list[tuple[float, float, str]]:
    sents = [x for x in re.split(r"(?<=[。？?！!])\s*", text) if x.strip()]
    x, srr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = int(0.01 * srr)
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2) + 1e-12) for i in range(0, len(x) - hop, hop)])
    db = 20 * np.log10(rms + 1e-9)
    loud = db > (db.max() - 32)
    idx = np.where(loud)[0]
    s0, s1 = idx[0] * 0.01, (idx[-1] + 1) * 0.01
    runs, i = [], idx[0]
    while i < idx[-1]:
        if not loud[i]:
            j = i
            while j < len(loud) and not loud[j]:
                j += 1
            if (j - i) * 0.01 >= 0.12:
                runs.append((i * 0.01, j * 0.01))
            i = j
        else:
            i += 1
    total = sum(len(s) for s in sents)
    out, prev, cum, used = [], s0, 0, set()
    for k, s in enumerate(sents):
        cum += len(s)
        if k == len(sents) - 1:
            out.append((prev, s1, s))
            break
        guess = s0 + (s1 - s0) * cum / total
        cand = [r for r in runs if r[0] > prev + 0.3 and r not in used]
        best = min(cand, key=lambda r: abs((r[0] + r[1]) / 2 - guess) - 0.8 * (r[1] - r[0])) if cand else (guess, guess)
        used.add(best)
        out.append((prev, best[0] + 0.05, s))
        prev = best[1] - 0.05
    return out

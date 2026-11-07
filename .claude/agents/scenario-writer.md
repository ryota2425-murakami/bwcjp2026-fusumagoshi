---
name: scenario-writer
description: 評価・デモ用のシナリオ(祖母の発話だけの台本)を書く。相手側の台詞は書かない。新しい手口や本物の電話のパターンを足すときに使う。
tools: Read, Write, Edit
---

`app/scenarios/scenarios.json` の形式に従う。各行は `[直前の沈黙(秒), 話し方, 祖母の発話]`。

- 相手の台詞は書かない。相手が話している時間は「直前の沈黙」で表す(長い勧誘は 6〜9 秒)。
- 話し方: n 普通 / p 丁寧 / c 明るい / l 笑い / w 不安 / h ためらい / u 押されて小声 / b あいづち / f はっきり断る。
- 企業名・地名・番号は架空にする。0 から始まる 10〜11 桁の番号は、書き込む前に PreToolUse フック(`app/scripts/hooks/guard_principles.py`)が止める(先頭が 0000 の番号だけ通す)。企業名・地名が実在と重なっていないかはフックでは見ない(auditor が確かめる)。
- `expected` に track・risk・notify_now を付ける。本物の電話は、キーワード(警察・銀行・口座など)があっても low にする。
- 書いたら `.venv/bin/python app/scripts/synth_scenarios.py <ID>` で合成し、ASR の一致(sim)が低い行は言い回しを直す。

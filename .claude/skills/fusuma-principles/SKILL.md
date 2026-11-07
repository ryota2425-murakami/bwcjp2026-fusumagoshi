---
name: fusuma-principles
description: ふすまごしの設計原則(割り込まない・祖母の声だけ・断定しない・抑制・責めない・事実を作らない・プライバシー)と、それをコードのどこで担保しているか。ふすまごしのコード・プロンプト・UI・README を変えるときは最初に読む。
---

# ふすまごしの原則と、その担保

| 原則 | どこで担保しているか |
|---|---|
| 通話中は何もしない(光らない・話さない) | `app/fusuma/orchestrator.py` の `Fusuma.say()` が唯一の発話経路で、通話中は `SilenceViolation`。耳がない(通話中か分からない)のに音を出す設定なら話さない。`devices.Speaker.say()` は再生の直前と再生中(0.1 秒ごと)に `may_speak()` を確かめ、鳴ったら自分の出力ストリームを `out.abort()` で止める(部屋の音の再生は止めない)。電話のあとの問いかけは、別の電話の最中と、部屋で誰かが話しているあいだは待つ。画面は通話中、行灯の灯りを `--glow` 0.05 まで落とし、右の欄の地も沈める(`app/web/js/app.js` の `GLOW`、`body.incall`)。フック `guard_principles.py` が他の発話経路の追加を止める |
| 聞くのは祖母の声だけ・音声は外に出さない | 耳(`app/fusuma/ear/`)が音声を処理し、脳にはテキストだけ(発話と声・間の数値、家族の文脈、カルテ、暮らしのメモ)。`app/fusuma/brain/llm.py` はテキスト以外のブロックを送らない。台帳 `runs/privacy_ledger.jsonl` に送った中身を残す(Managed Agents の記憶ストアへ送った要約も `llm.record_sent()` で同じ台帳に)。フック `guard_principles.py` が、脳(`app/fusuma/brain/`)に音声を送る書き方を止める |
| ASR は必要なときだけ | `Ear._segment()`: 通話中と、ふすまごしが話しかけた直後(`open_room_listen`。話し始めで判定)以外は文字にしない。例外はデモの下準備 `app/scripts/run_call.py`(夕方のおしゃべり R01 を、話しかけたあとの会話として文字にする) |
| 断定しない・責めない | プロンプト `app/fusuma/brain/prompts/principles.md`(3・5)。Messages API で書く便り(今すぐの便り)は、`letters.violations()` が言い切りや本人をだまされた人として書く言葉を見つけたら 1 回書き直させ、それでも残れば決まった文に差し替える。電話のあとの声かけも同じ規則で差し替える(`orchestrator.py`)。夕方の便りは Managed Agents の Outcomes ルーブリックで採点し、合格した便りだけを届ける(`managed.gate()`) |
| 相手の台詞を作らない | `principles.md` の 2(Messages API の各役に入る)と、listener / family / letter のプロンプト・便り係の `agent.md`。カルテは祖母の発話から言えることだけ(`family.md`)。夕方の便りはルーブリックでも採点 |
| 抑制(誤警報を出さない) | まとめ役の `action`(silent / evening / immediate)と `restraint_note`。黙って記録(silent)にした電話には、電話のあとも問いかけない(`orchestrator.py`)。評価で本物の電話 5 件の誤警報数を見る |
| 事実を作らない | 知識カード(公的機関などの出典つき)を、反証役には search_result で渡し Citations で引用させる。聞き役・まとめ役・Messages API の便りにはカードを本文で渡し、カードにない数字や制度は使わせない(`principles.md` の 6)。夕方の便り係は、期限・制度・数字をスキル fusuma-letter の `cards.md` にあるものだけで書く(`agent.md`。ルーブリックでも採点) |
| 文字起こしを残さない | `Fusuma._purge()`: どの終わり方(聞き取り完了・答えがない `DIALOG_IDLE_SEC`・別の電話・問いかけない電話・失敗)でも、`Store.purge_transcript()`(聞き役の引用・反証役の原文も除く)、`llm.redact()`(台帳のその通話の分を伏せる)、`Hub.redact()`(画面の履歴と `runs/events.jsonl`)。送るたびに `llm.REF` で通話 ID の印をつけている。サーバーを起動し直したときも、残っていた分を消す。画面は `purged` を受けて言葉だけを灰色の帯に替え、間・声の長さ・声量・注記・照合した記録は残す(`app/web/js/app.js`) |
| 住所・番号を書きとめない | 画面は、住所・番地・口座・暗証番号などの語を含む発話を頭の数文字だけ書いて「(住所・番号は書きとめません)」と添え、耳から Claude に渡したさいごの一行も「」の中を伏せて出す(`app/web/js/app.js` の `PRIVATE`)。伏せるのは画面の上だけで、Claude の各役(聞き役・反証役・まとめ役)には文字起こしのまま渡る。家族への便りには住所・番号を書かない(`principles.md` の 7・便り係の `agent.md`。夕方の便りはルーブリックでも採点) |
| 内緒と判定したメモは広げない | 判定のために暮らしの話は一度 Claude に送る(`family.extract_memo`。台帳に残る)。内緒と判定したメモは、記憶ストア(`managed.sync_memory()` は `include_secret=False`)・便り・以後のプロンプト(`Store.memo_digest()`)に出さない。画面(`/api/state`)と MCP `fusuma-karte` にも返さない。フックが `include_secret=True` を止める |
| 声を複製しない | TTS の声見本は、文章の説明から VoiceDesign で作った合成音声。読み上げはその合成の声見本を参照する(`app/tts_server/tts_engine.py`。`app/tts_server/voices/*_ref.json` に説明文・seed・モデル) |

変更を入れたら `.venv/bin/python app/tests/test_principles.py`(Claude API を使わない原則のテスト)と、`.venv/bin/python app/scripts/run_eval.py --tag <名前>`(Claude API を使う)で誤警報と見逃しを確かめる。判定に効くファイル(プロンプト・知識カード・`schemas.py`)を Write / Edit で変えると、PostToolUse フック(`app/scripts/hooks/after_edit.sh`)が知らせる。4 シナリオ(S05・S13・S03・S11)の小さな評価をその場で回すのは `FUSUMA_AUTO_EVAL=1` のときだけ。

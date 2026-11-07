# CLAUDE.md — ふすまごし

一人で暮らす祖母の電話を、祖母の声だけ黙って聞き、電話のあとに家族のように声をかけ、離れた家族に便りを届ける行灯。
README.md が全体像。技術資料は `docs/tech/`(入り口は `how-it-works.md`)、設計の判断は `docs/design.md`。原則とその担保場所は `.claude/skills/fusuma-principles/SKILL.md`。

## 守ること(破る変更は入れない)

1. 通話中は何もしない。端末が声を出す経路は `Fusuma.say()` だけ(通話中は `SilenceViolation`。合成中・再生中に電話が鳴ってもやめる。部屋で誰かが話していたら話しかけない)。画面も通話中は行灯の灯りを落とす(`app/web/js/app.js` の `GLOW`、通話中 0.05)。
2. 聞くのは祖母の声だけ。Claude に音声を送らない(`fusuma/brain/llm.py` はテキスト以外を拒否)。
3. 断定しない・相手の台詞を作らない・責めない。手口や数字は `app/knowledge/cards.json`(出典つき)だけ。
4. 抑制する。本物の電話で誤警報を出さない(評価で確かめる)。
5. 声を複製しない。実在の人の名前・会社・住所・電話番号を使わない(電話番号の形はフックが止める。名前・会社・住所は `auditor` で確かめる)。
6. 文字起こしは聞き取りが終わったら消す(台帳・ログ・判定の引用も伏せる。画面からも言葉だけを消し、声の線・間・数字は残す。カルテには根拠の短い言葉が時刻つきで残る)。住所や番号は画面にも書きとめない。内緒と判定したメモは、記憶ストア・便り・以後のプロンプトに出さない(判定のためには一度 Claude に送る)。

## 開発の流れ

- サービス: `bash scripts/services.sh start`(whisper-server :8765 / TTS :8766)、画面: `cd app && ../.venv/bin/uvicorn fusuma.server:app --port 8780`(`/` が台所の画面(通話明細)、`/family.html` が家族の画面)
- 判定に効くファイル(`app/fusuma/brain/prompts/*.md`、`app/knowledge/cards.json`、`schemas.py`)を変えると、PostToolUse フックが知らせる(`FUSUMA_AUTO_EVAL=1` なら 4 シナリオの小さな評価を回す。約 $0.15)。全体は `eval-runner` サブエージェントか `app/scripts/run_eval.py`(15 通話で 1 回 約 $0.4)。
- 評価の最終は v6(架空の 15 通話 × 4 回。結果は `eval/`、履歴と費用は `docs/records/`)。README の数字はここから取る。
- 原則のテスト: `cd app && ../.venv/bin/python tests/test_principles.py`(Claude API を呼ばない。27 件。数十秒)。
- 提出前に `auditor` サブエージェントで原則の監査。
- 記憶の中身は MCP サーバー `fusuma-karte`(読み取り専用)で引ける。
- Managed Agents の定義は `app/managed/`(`ant apply`)。エージェントを変えるときはファイルを直して apply し直す。毎日 18:00 に走るので、使わないときは `app/scripts/managed_schedule.py pause`。
- 図は `app/web/img/*.svg` を `app/scripts/render_diagrams.py` で PNG に。画面の写真は `app/scripts/record_demo.py` の収録から切り出した JPEG(`docs/images/`)。

## 書き方

日本語。簡潔に。コメント・README・台本も日本語。

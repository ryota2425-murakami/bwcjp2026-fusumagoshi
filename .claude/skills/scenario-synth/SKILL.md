---
name: scenario-synth
description: 新しい通話シナリオを足して、祖母の声で合成し、耳と脳に通して評価に加える手順。シナリオを追加・修正するときに使う。
---

# シナリオを足す手順

1. `app/scenarios/scenarios.json` に追加する(形式は scenario-writer エージェントの説明どおり。祖母の発話だけ)。
2. サービスを起動: `bash scripts/services.sh start`(whisper-server と TTS サーバー)。
3. 合成: `.venv/bin/python app/scripts/synth_scenarios.py <ID>`
   - 各行を TTS → whisper で文字に戻して台本と比べる。`sim` が 0.72 未満なら seed を変えて作り直す。
   - それでも ⚠ が残る行は、言い回しを変えるか `READING`(読みの上書き)に足す。
   - 前に作ったシナリオを直したときは `--force` を付ける(付けないと、前に作った wav と truth.json をそのまま使う)。
4. 耳だけ確認: `.venv/bin/python app/scripts/ear_file.py data/scenarios/<ID>_16k.wav`(Claude に渡すテキストが出る)。
5. 評価に入れる: `.venv/bin/python app/scripts/run_eval.py --tag <名前> --ids <ID>`(Claude API を使う)。耳の出力はキャッシュされるので、音声を作り直したときは `--force-ear` を付ける。
6. 本物の電話なら、キーワード検知が誤警報を出すか(`kw_alert`)も見ておく。summary の誤警報数が数える本物の電話は S10〜S14 だけなので、新しく足した本物の電話は rows の `false_alarm` で見る。

# デモ動画の作り方(v2・3 分・1920×1080・日本語)

伝えたいことは「閉めたままで、そばにいる。」。14 の場面で、物語はゆっくり、しくみは早口で見せる。字幕は明朝(Shippori Mincho B1)、色は和紙・墨・朱・藍・行灯の橙だけ(`project/src/theme.ts` の `K`)。

[claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) の Remotion のひな形を土台に、Claude Code で組み立てた。v2 の場面はすべて `project/src/scenes/v2/` に書き直している。キャラ「みずち」(ウーパールーパーの親戚)の場面は HyperFrames(HTML を 1 フレームずつ書き出す)で作り、透過つきの映像として Remotion で重ねた。

## 場面

時刻は `project/src/data/timeline_v2.json` から(動画は 179.5 秒。表の時刻は、その場面に入っている最初の秒)。

| | 時刻 | 場面 | 中身 |
|---|---|---|---|
| s01 | 0:00 | けはい | 少し開いたふすま。向こうから祖母の声 |
| s02 | 0:12 | あの日 | 鳴る黒電話 → 鳴りやんだ電話。作者の祖母に実際にあったことを 2 行で |
| s03 | 0:26 | 便り | 「便りがないのは、元気な証拠。そう、思っていました。」 |
| s04 | 0:38 | 行灯 | 墨の図。台所の行灯、部屋のマイク、電話の線にはつながない、通話中は光らない・話さない。左にみずち(灯ると跳ねて出てきて、マイクの方に耳をすまし、「通話中は」で目を閉じる) |
| s05 | 0:48 | 通話 | 実際の画面の録画(架空の通話 S05)。祖母の声だけ。早送りしながら、いちばん長い沈黙だけは実時間で数える |
| s06 | 1:19 | ふすまの裏側 | 早送りで、図。友だちとの電話との比べ、Claude に渡す 1 行、音声 0 バイト |
| s07 | 1:29 | 家族会議 | 3 つの Claude の図(聞き役・反証役・まとめ役)。まとめ役が夕方の便りを選んだ理由 |
| s08 | 1:41 | 電話のあと | 実際の画面の録画。行灯が初めて灯り、ふすまごしと祖母が話す(会話は一部を詰めている)。左上の小窓は Pi の画面(実機。みずち)で、同じ録画のイベントを流し直して撮った。行灯の声は、同じ台詞をいまの声(AivisSpeech「まお」)で、録画と同じ長さに読み直した |
| s09 | 1:52 | 「つい」 | 会話が終わると、文字起こしは消える。時計が 18:00 へ |
| s10 | 1:58 | 夕方の便り | 家族の画面の録画と、便りができるまで(採点役の書き直し → 合格)。左上の小窓は家族の机の Pi(実機): 届くのは「便りが来た」ことだけ |
| s11 | 2:14 | 試験と Claude Code | 評価の結果、フックが止めた例、提出前のレビュー |
| s11b | 2:26 | 実機の Pi | 架空料金請求の電話 P01 を、実機の Pi で撮った映像(約 9.5 秒)。通話中は祖母の「えっ……4万円も、するんですか。」でのぞき、電話のあとは「行く前に、ケンタと一緒に、確かめてみない?」、祖母は「じゃあ……やめておくわ。孫に、電話してみるね。」。画面に「実機の Pi ・ 架空料金請求の電話(相手の声: 警視庁の再現ドラマ)」 |
| s12 | 2:36 | 健太の電話 | 同じ膝の話。こんどは、家族から |
| s13 | 2:48 | 結び | 両側からふすまが閉まり、すきまから灯り。ふすまの向こうで祖母が自分から話し出す「それがね、今日ね、」。少しの静けさのあと「閉めたままで、そばにいる。」 |

## 作り方

| 段階 | どうやったか | ファイル |
|---|---|---|
| 台本 | ナレーション 27 行(動画で使うのは 26 行。v17 で c01 を外した)と、祖母・孫の声 5 行。物語の行は 0.95〜1.06 倍、説明の行は 1.2〜1.5 倍の速さで読む | `script/narration.json` |
| 声 | Qwen3-TTS(MLX・ローカル)の合成音声。声見本は文章の説明から作った(ナレーターは 50 代の男性の低めの声、祖母は 85 歳くらいの声)。各行を whisper で文字に戻して台本と照合し、崩れていれば seed を変えて作り直す。速さは音程を変えずに変える(rubberband) | `script/make_narration.py` → `project/public/narration/*.wav`・`narration_meta.json` |
| 効果音とリズム | 柱時計・ふすま・判子・郵便受け・鈴・キーボード・行灯の音と、しくみの場面の拍子木と木琴のリズムを、数式から合成した(素材のライセンスが要らない) | `script/make_sfx.py` → `project/public/sfx/*.wav`・`project/public/music/wood_rhythm.wav` |
| 画面 | 実際に動いている画面を Playwright で録画(ヘッドレス Chromium、1920×1080)。ふすまごしの声を重ねるため、サーバーは `FUSUMA_SAVE_SPEECH=1` で起動 | `../app/scripts/record_demo.py` → `assets/rec/call_S05_v4`・`assets/rec/letter_v4` |
| 組み立て | 録画のイベント時刻、祖母の発話の時刻(合成のときの正解データ `S05.truth.json`)、ふすまごしの声のログ、ナレーションの長さから、場面・音声・字幕の時刻を組み立てる。画面に出す数字(沈黙の秒数、友だちとの電話の割合、採点役のことば)も記録から取る | `script/build_timeline_v2.py` → `project/src/data/timeline_v2.json` |
| 描画 | Remotion。場面は図・録画・写真を重ね、字幕は句読点で折り返す | `project/src/FusumagoshiV2.tsx`、`project/src/scenes/v2/` |
| キャラ(みずち) | Pi と同じ `rig.js`(時刻と状態から 1 枚を描く)を、HyperFrames で 1 フレームずつ書き出す。s04 は ProRes 4444(透過つき)で、みずちで書き直した。s08・s10 の小窓も、実機でみずちを撮り直した。s11b は P01 の実機撮影。時刻は `build_timeline_v2.py` が `assets/tracks.js` に書き出す | `hyperframes/lantern/andon.html` → `project/public/char/s04_andon.mov` |
| Pi の画面 | 録画のときのイベントを、中継(`lantern_bridge --replay`)から Pi に流し直し、Pi の画面を wf-recorder で撮る(Claude は呼ばない)。動画の録画の切れ目に合わせて小窓に入れる | `script/capture_pi.sh` → `project/public/char/pi_after.mp4`・`pi_letter.mp4` |
| 行灯の声 | 収録のときの行灯の台詞を、いまの行灯の声(AivisSpeech「まお」おちつき)で文ごとに読み直し、録画のときの文の長さに合わせる(rubberband) | `script/make_lamp_v3.py` → `lab/runs/speech_v3/` |
| 素材 | 写真と映像は Pexels(Pexels License)。物語の場面の音楽は Mixkit の Piano Reflections(Mixkit Stock Music Free License) | `assets/CREDITS.md` |

## 作り直すには

リポジトリに入れていないもの(ライセンスと容量のため)を先に用意する。パスはリポジトリの配置(`video/` の隣に `app/`)。作業用の配置(`video/` の隣に `lab/app/`)でも、スクリプトはそのまま動く。

1. 写真と映像: `assets/CREDITS.md` の ID で Pexels から取り、`assets/stock/` に置く(例 `photo_fusuma_ajar_38944471.jpg`、`video_phone_ringing_1721320.mp4`。使う写真 6 枚と映像 3 本のファイル名は `script/prepare_assets.sh` のとおり)。`prepare_assets.sh` が、写真(幅 2400 px まで縮める)・映像(1920×1080・30 fps。黒電話はダイヤル中央の英国の緊急番号の札だけをぼかす)・鳴りやんだ電話の 1 コマ `img/phone_still.jpg`・呼出音・効果音(`make_sfx.py` を呼ぶ)・音楽を `project/public/` にそろえる。 Getty Images の素材(写真 2 枚・映像 3 本、`assets/CREDITS.md` の表)は作者が用意したもので、`assets/getty/` に置くと `prepare_assets.sh` が変換する(リポジトリには同梱しない)。
2. 音楽: Mixkit の Piano Reflections を `assets/music/mixkit_22_piano_reflections.mp3` に置く。
3. 声の合成: `app/scripts/synth_scenarios.py` で台本の音声(S05・S11・R02 など)と正解データを作る。友だちとの電話の数字は `runs/eval/ear_S11.json` から読むので、リポジトリでは同梱の `eval/ear_cache/ear_S11.json` を `runs/eval/` に写しておく。
4. サービス: `bash scripts/services.sh start`(whisper-server と TTS)。
5. `cd project && npm install`

```bash
# video/ で(作業用の配置では ../.venv を ../lab/.venv に、../app を ../lab/app に)
../.venv/bin/python script/make_narration.py      # ナレーションと会話の声(足りないものだけ作る。--force n01 で作り直し)
bash script/prepare_assets.sh                     # 写真・映像・呼出音・音楽を public/ に。効果音とリズムもここで作る(make_sfx.py)
# 画面の録画: サーバーを FUSUMA_SAVE_SPEECH=1 で起動し(使った収録では FUSUMA_AUDIBLE=0・FUSUMA_POST_CALL_DELAY=8 も付けた)、記憶の下準備(run_call.py --reset S00 R01)をしてから
# (--clock 14:01:50 で、画面の時計が 14:00:50 の呼出音から始まる。使った収録と同じ)
../.venv/bin/python ../app/scripts/record_demo.py call --scenario S05 --clock 14:01:50 --out assets/rec/call_S05_v4
../.venv/bin/python ../app/scripts/record_demo.py letter --out assets/rec/letter_v4
../.venv/bin/python script/make_lamp_v3.py         # 行灯の台詞を、いまの声で読み直す(AivisSpeech Engine :10101)
bash script/capture_pi.sh assets/rec/call_S05_v4/timing.json 200 70 kitchen assets/pi/after_call.mp4    # Pi の画面(実機)
bash script/capture_pi.sh assets/rec/letter_v4/timing.json 126 12 family assets/pi/letter_family.mp4
../.venv/bin/python script/build_timeline_v2.py --call call_S05_v4 --letter letter_v4   # 場面・音声・字幕の時刻(hyperframes/lantern/assets/tracks.js も)
(cd hyperframes/lantern && ../hf.sh render -c andon.html --format mov -o renders/s04_andon.mov && cp renders/s04_andon.mov ../../project/public/char/)
../.venv/bin/python script/build_timeline_v2.py --call call_S05_v4 --letter letter_v4   # キャラの映像を入れて組み直す
cd project && npx remotion render FusumagoshiV2 out/fusumagoshi.mp4 --codec h264 --crf 18 --timeout=180000
```

録画は Claude API と Managed Agents を実際に呼ぶ(通話 1 本と、夕方の便り 1 回。台帳の記録では、通話 1 本 約 $0.09、便り 1 回 $0.17〜0.25)。
ナレーションを自分の声に差し替えるときは、`project/public/narration/` の同じ id の wav(`n01.wav` など)を置き換え、`make_narration.py` をもう一度動かして長さを `narration_meta.json` に読み直してから(台本が同じ行は合成し直さない)、`build_timeline_v2.py` から作り直す。場面の長さは自動で合う。

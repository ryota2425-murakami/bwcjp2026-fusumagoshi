---
version: 1
slug: "app-web-index-html"
primary_target: "app/web/index.html"
related_targets: ["app/web/family.html"]
---

# 台所の画面・家族の画面

範囲: `/`(台所の画面)と `/family.html`(家族の画面)。モード: Operate(録画した 1920×1080 のデモで、審査員が仕組みの中身を読む)。

## Direction contract

THESIS: 通話を「明細」として正直に記帳する。通話中は 1 発話 1 行ずつ増え、終わると小計と台帳(音声 0 B・文字数・費用)が締まる。拒むもの: 紙のノートの見立て(付箋・判子・テープ・手書き)と、ゲージやチップの並ぶ AI ダッシュボード。

OWN-WORLD: 冷たい白の地、墨の文字、細い罫。区画の見出しは深い青緑の帯に白抜き。行灯の琥珀は「いま動いているもの」専用で、灯りの強さ(--glow)に従い通話中は消える。朱は「最長の沈黙・断り・小さな声の約束」の注記だけ。相手の時間は青灰の斜線。本文 BIZ UDPGothic、数字と時刻 BIZ UDGothic、声に出された言葉(行灯・祖母)だけ BIZ UDPMincho。

STORY: 祖母の声だけから会話の形(間・声量・断りが消えたこと)が測られ、3 つの役が別々に判断し、音声は 1 バイトも外に出ていないことを、数字で読める。

FIRST VIEWPORT: 1920×1080。上端 64px の帯(名前・状態 4 段・日付と時計)。左 1120px は通話明細(見出し・明細表・小計・耳の処理系)。右 744px は行灯(灯りの値と一言)、台所の音、電話のあとのお話の 3 段、判定 3 列(聞き役・反証役・まとめ役)。下端 56px は台帳。署名の動き: 明細の行が通話中に 1 行ずつ積まれ、間の横棒が実測の長さで伸びる。

FORM: 通話明細書(自分の 7 案の 7 番目)。seed:e557b90239ec2a22。引き上げ: 琥珀は「いまの一手」だけ(オリエンテーリング地図から)/ 見出しは左の余白列に吊るす(マニュアルのタブ板から)/ 階層は 1 書体の大きさの差で(Emigre から)/ 行灯の言葉は 1 行 1 メッセージ(空港サインから)。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

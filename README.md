# bdg-claude-usage-check

BLUE DESIGN GROUP（BDG）のスタッフの **Claude Code 使用量と使用内容** を、Google 共有ドライブに集めて月次でレポートにするためのしくみです。

- ベースの道具: [yujirotn/claude-usage-check](https://github.com/yujirotn/claude-usage-check) v0.1.0
- 格納先: Google 共有ドライブ「10_BLUE DESIGN GROUP/BDG Claude 使用量」  
  <https://drive.google.com/drive/folders/1o-JeePozm9ZUFLhK91dnfjyF2s7Jr3G3>

## 集めるもの

- 日付ごとのセッション数・発言数・トークン数・API 換算金額・モデル名
- プロジェクトフォルダごとの発言数
- **任せ方の数字**（`bdg_stats.py`）: 任せ度（発言1回で AI が何回動いたか）・AI と作業した時間・自動実行の割合・ファイルの編集回数・ブラウザや PC 操作を任せた回数・使用時間帯・使用上限に当たった回数・使ったスキルの名前と回数。数字だけで、会話の本文やファイル名は入りません
- **使用内容サマリー**（プロンプト本文を読んで、何に Claude を使っているかを要約したマークダウン）

## 大事なこと

- 集めた内容は **井上が月次でレビュー** します
- 送ったファイルは、共有ドライブに置かれてから15分ほどで **井上だけが見られる場所へ自動で移されます**（共有フォルダには残りません）
- 何に使ったかの要約も井上が確認します（会話の中身そのものは集めません）
- API キー・パスワードらしき長い文字列は自動でマスクされます

## スタッフの使い方

Claude Code を開いて、次の文を貼ってください。

> https://github.com/sinoue-collab/bdg-claude-usage-check/blob/main/CLAUDE.md を読んで、Claude 使用量を送るしくみをセットアップしてください

初回は名前を聞かれます。セットアップ直後にその時点の数字と使用内容が送信され、以降は **毎月10日に自動で送信** されます（Claude Code のスケジュール機能）。

## 問い合わせ

井上（執行役員）まで

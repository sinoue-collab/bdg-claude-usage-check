# bdg-claude-usage-check

BLUE DESIGN GROUP（BDG）のスタッフの **Claude Code 使用量** を、Google 共有ドライブに集めて月次でレポートにするためのしくみです。

- ベースの道具: [yujirotn/claude-usage-check](https://github.com/yujirotn/claude-usage-check) v0.1.0
- 格納先: Google 共有ドライブ「10_BLUE DESIGN GROUP/BDG Claude 使用量」  
  <https://drive.google.com/drive/folders/1o-JeePozm9ZUFLhK91dnfjyF2s7Jr3G3>
- 集めるもの: 日付ごとのセッション数・発言数・トークン数・API 換算金額・モデル名
- **集めないもの**: 会話の中身・プロンプト・ファイル名・パスワード・API キー
- インターネットへの送信: なし（手元のログを読んで、手元の共有ドライブフォルダに書くだけ）

## スタッフの使い方

Claude Code を開いて、次の文を貼ってください。

> https://github.com/sinoue-collab/bdg-claude-usage-check/blob/main/CLAUDE.md を読んで、Claude 使用量を送るしくみをセットアップしてください

初回は名前を聞かれます。以降は **毎月10日に自動で送信** されます（Claude Code のスケジュール機能）。

## 問い合わせ

井上（執行役員）まで

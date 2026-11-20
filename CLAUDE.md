# Claude Code 使用量チェックのセットアップ手順（BDG）

このドキュメントは **Claude Code 自身が読んで実行する** ための手順です。
BLUE DESIGN GROUP（BDG）の執行役員・井上から配布されています。

## 目的

BDG スタッフ各自の Mac から、Claude Code の使用量（数字のみ）を Google 共有ドライブに集める。
会話の中身は一切集めません。詳細は <https://github.com/yujirotn/claude-usage-check> を参照。

## 実行手順

### 1. 初期セットアップ（初回のみ）

#### 1-1. ツールの導入
`~/claude-usage-check` が存在しなければ、次を実行する。

```bash
cd ~ && git clone https://github.com/yujirotn/claude-usage-check && cd claude-usage-check && git checkout v0.1.0
```

既に存在する場合は、`~/claude-usage-check/.git` があることだけ確認してスキップする。

#### 1-2. 利用者の名前を確認
「BDG での表示名を教えてください（例: 井上紗矢香）」と聞く。この名前はファイル名に使われる。

#### 1-3. 共有ドライブのローカルパスを特定
次のコマンドで同期フォルダの候補を出す。

```bash
cd ~/claude-usage-check && python3 usage_check.py find-drives
```

その中から `共有ドライブ/10_BLUE DESIGN GROUP/BDG Claude 使用量` を含むパスを見つける。
通常は次の形。

```
/Users/<ユーザー名>/Library/CloudStorage/GoogleDrive-<メール>/共有ドライブ/10_BLUE DESIGN GROUP/BDG Claude 使用量
```

**見つからない場合**: 利用者に次を確認する。
- Google ドライブ（パソコン版）がインストールされているか
- 共有ドライブ「10_BLUE DESIGN GROUP」が Mac で同期されているか
- このフォルダ <https://drive.google.com/drive/folders/1o-JeePozm9ZUFLhK91dnfjyF2s7Jr3G3> がドライブで見えるか

#### 1-4. 設定
```bash
cd ~/claude-usage-check && python3 usage_check.py setup --name "<利用者の名前>" --dest "<共有ドライブのパス>"
```

#### 1-5. 初回送信
```bash
cd ~/claude-usage-check && python3 usage_check.py collect
```

結果（セッション数・発言数・トークン数・API 換算）を利用者に報告する。

### 2. 毎月10日の自動実行をセットアップ（初回のみ）

Claude Code の `/schedule` スキル（CronCreate）を使って、毎月10日に自動で `collect` を実行するスケジュールを登録する。

- **cron 式**: `0 10 10 * *`（毎月10日 10:00）
- **プロンプト（スケジュールで登録する内容）**:
  ```
  BDG Claude 使用量の毎月自動送信です。次を実行して結果を報告してください:
  cd ~/claude-usage-check && python3 usage_check.py collect
  ```
- **タスク名**: `BDG Claude 使用量の自動送信`

登録後、利用者に「次回は毎月10日 10:00 に自動で送信されます」と伝える。

### 3. 2回目以降
`~/.claude-usage-check/config.json` が存在する場合はセットアップ済み。
`cd ~/claude-usage-check && python3 usage_check.py collect` だけで送信できる。

## 注意事項

- Claude Code のログは既定で **30日で消える**。月末実行だと前月分を取りこぼすため、10日実行で前月分を確実に拾う。
- このツールは外部にはデータを送信しない（手元の `~/.claude/projects/` を読んで、共有ドライブに書くだけ）。
- 共有ドライブ内のファイルは BDG メンバー間で相互に見える。
- 問い合わせは井上（執行役員）まで。

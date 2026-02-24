# SlideTasks for Windows

Google Tasks をマスターとする、Windows 向けの常駐型タスクパネルです。
`Ctrl+Shift+Space` で右端からパネルを呼び出し、キーボード中心で操作できます。

## 主な機能

- 右端スライド式パネル（トレイ常駐）
- グローバルホットキー: `Ctrl+Shift+Space`
- Google Tasks 同期（OAuth2）
- タスクリスト切り替え
- サブタスクのインデント表示
- 完了時 2 秒 Undo
- オフライン時の読み取り専用モード
- 完了ログ表示（期間指定）

## 設計方針

- Google Tasks API を正（マスター）として扱う
- ローカル SQLite は UI キャッシュ用途に限定
- タスク削除はアプリ UI から提供しない（同期事故防止）

## セットアップ

1. Python 3.11+ を用意
2. 依存をインストール

```bash
pip install -r requirements.txt
```

3. Google Cloud Console で Tasks API を有効化し、`credentials.json` を配置
4. アプリを起動

```bash
python main.py
```

初回起動時に OAuth 画面が開き、認証後に `token.json` が生成されます。

## ビルド（任意）

```bash
python build.py
```

`dist/SlideTasks_v1.0` に実行ファイル一式を生成します。

## ディレクトリ構成（主要）

- `main.py`: エントリーポイント
- `app/main_window.py`: メインウィンドウと UI 制御
- `app/task_widget.py`: タスクリスト UI と入力周り
- `app/sync_worker.py`: バックグラウンド同期ワーカー
- `app/infrastructure/google/`: Google API 連携
- `app/database.py`: ローカルキャッシュ DB

## 注意

- 機密情報（`credentials.json`, `token.json`）は公開しないでください。
- ネットワーク制限下では Google API 同期に失敗し、オフライン表示になります。

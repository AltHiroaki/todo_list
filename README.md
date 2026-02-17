# SlideTasks for Windows

Windows常駐型・スライド式TODOアプリケーション。  
画面右端に常駐し、クリックでスムーズに展開。Google Tasks連携対応。

## 特徴

- 📌 **常駐型**: 画面右端に常に表示（AlwaysOnTop, フレームレス）
- 🎞️ **スライド展開**: 40px → 340px のスムーズなアニメーション
- ✅ **タスク管理**: 追加・完了（取り消し線）・削除
- 📊 **進捗表示**: プログレスバーで今日の達成率を可視化
- 📅 **日次リセット**: 日付が変わると前日のログを自動保存
- 📈 **過去ログ**: 直近30日間の達成率をグラフで確認
- 🔗 **Google Tasks 同期**: credentials.json を配置すれば自動連携

## ダウンロード & インストール

1. **GitHub Releases** から最新の `SlideTasks_vX.X.zip` をダウンロードしてください。
2. 解凍して、任意の場所に配置します。
3. `SlideTasks.exe` を実行すれば起動します。

## セットアップ (Google Tasks 連携)

本アプリは Google Tasks と同期する機能を持っていますが、セキュリティの関係上、**認証情報は各自で用意していただく必要があります**。

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成します。
2. **Google Tasks API** と **Google Calendar API** を有効化します。
3. **OAuth 2.0 クライアントID**（アプリケーションの種類: デスクトップアプリ）を作成します。
4. JSON形式で認証情報をダウンロードし、ファイル名を `credentials.json` に変更します。
5. `SlideTasks.exe` と同じフォルダ（`SlideTasks_v1.0` フォルダ内）に `credentials.json` を配置します。
6. アプリを起動すると、初回のみブラウザが開き、Google認証を求められます。許可すると `token.json` が自動生成され、連携が開始されます。

## 開発者向け (ソースコードから実行)

```bash
# 1. リポジトリをクローン
git clone https://github.com/your-username/SlideTasks.git
cd SlideTasks

# 2. 仮想環境作成 (推奨)
python -m venv venv
./venv/Scripts/activate

# 3. 依存パッケージのインストール
pip install -r requirements.txt

# 4. アプリ起動
python main.py
```

## ファイル構成 (配布時)

```
SlideTasks_v1.0/
├── SlideTasks.exe        # アプリ本体
├── credentials.json      # [必須] 自分で配置する認証ファイル
├── README.md             # 説明書
└── data/                 # データ保存用 (自動生成)
```

## ライセンス

Private、つまり無いです。

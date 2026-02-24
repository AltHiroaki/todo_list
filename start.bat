@echo off
cd /d "%~dp0"

echo 必要なライブラリを確認・インストールしています...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo エラー: ライブラリのインストールに失敗しました。
    pause
    exit /b 1
)

start "" pythonw main.py

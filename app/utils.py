import sys
import os

def get_base_path() -> str:
    """
    アプリケーションのベースパスを取得する。
    
    Returns:
        str: EXE実行時はEXEのあるディレクトリ、開発時はプロジェクトルートディレクトリ
    """
    if getattr(sys, 'frozen', False):
        # EXE実行時
        return os.path.dirname(sys.executable)
    else:
        # スクリプト実行時: このファイル (app/utils.py) の2つ上のディレクトリがルート
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

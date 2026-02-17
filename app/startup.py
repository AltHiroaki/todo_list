"""
SlideTasks — Windows スタートアップ登録
スタートアップフォルダにショートカットを作成/削除する。
"""

import os
import sys


def get_startup_folder() -> str:
    """Windowsスタートアップフォルダのパスを返す"""
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def get_shortcut_path() -> str:
    return os.path.join(get_startup_folder(), "SlideTasks.lnk")


def is_registered() -> bool:
    """スタートアップに登録済みか"""
    return os.path.exists(get_shortcut_path())


def register():
    """スタートアップにショートカットを作成する"""
    try:
        import winreg
        # レジストリ方式（よりクリーン）
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        from app.utils import get_base_path
        script = os.path.abspath(
            os.path.join(get_base_path(), "main.py")
        )
        winreg.SetValueEx(key, "SlideTasks", 0, winreg.REG_SZ,
                          f'"{sys.executable}" "{script}"')
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def unregister():
    """スタートアップ登録を解除する"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, "SlideTasks")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

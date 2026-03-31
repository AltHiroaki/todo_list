"""
SlideTasks — Dark Theme Stylesheet (QSS)
プレミアムダークテーマ。グラスモーフィズム・グロー・グラデーション・マイクロアニメーション。
"""

# ── カラーパレット ──────────────────────────────────────
BG_PRIMARY = "#0f0f1a"       # 深い漆黒ネイビー
BG_SECONDARY = "#161625"     # パネル背景
BG_TERTIARY = "#1e1e33"      # カード背景
BG_INPUT = "#1a1a2e"         # 入力欄背景
SURFACE = "#252542"          # ホバー面

ACCENT = "#8b5cf6"           # メインアクセント（バイオレット）
ACCENT_GLOW = "#a78bfa"      # グロー
ACCENT_DEEP = "#6d28d9"      # 深いアクセント
ACCENT_SOFT = "#c4b5fd"      # 淡いアクセント
GRADIENT_START = "#8b5cf6"   # グラデーション開始
GRADIENT_END = "#06b6d4"     # グラデーション終了（シアン）
SUCCESS = "#10b981"          # 完了グリーン
SUCCESS_GLOW = "#34d399"

TEXT_PRIMARY = "#f1f0f7"     # メインテキスト（ほぼ白）
TEXT_SECONDARY = "#8b89a6"   # セカンダリ
TEXT_MUTED = "#55536e"       # ミュート
TEXT_DONE = "#4a4862"        # 完了テキスト

BORDER = "#2a2a45"           # 通常ボーダー
BORDER_SUBTLE = "#1f1f38"    # 微細ボーダー
BORDER_GLOW = "#8b5cf640"    # グロー付きボーダー

DANGER = "#ef4444"

SCROLLBAR_BG = "transparent"
SCROLLBAR_HANDLE = "#2a2a45"

MAIN_STYLESHEET = f"""
/* ── 全体 ── */
QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI Variable", "Segoe UI", "Yu Gothic UI", sans-serif;
    font-size: 13px;
}}

/* 中央ウィジェット: 格納時に背景を透過させる */
QWidget#centralWidget {{
    background: transparent;
}}

/* ── 格納モードのトグルボタン ── */
QPushButton#toggleButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ACCENT}, stop:0.5 {ACCENT_DEEP}, stop:1 #4c1d95);
    color: rgba(255, 255, 255, 0.95);
    border: none;
    border-radius: 0px;
    font-size: 14px;
    font-weight: 600;
    padding: 0px;
}}
QPushButton#toggleButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ACCENT_GLOW}, stop:0.5 {ACCENT}, stop:1 {ACCENT_DEEP});
}}
QPushButton#toggleButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ACCENT_DEEP}, stop:1 #4c1d95);
}}

/* ── コンテンツエリア ── */
QWidget#contentPanel {{
    background-color: {BG_SECONDARY};
    border-left: 1px solid {BORDER};
}}

/* ── ヘッダーラベル ── */
QLabel#headerLabel {{
    color: {TEXT_PRIMARY};
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 4px 0px 0px 0px;
}}
QLabel#dateLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 400;
    padding: 0px 0px 4px 0px;
}}

/* ── セパレータ ── */
QFrame#separator {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent, stop:0.2 {BORDER}, stop:0.8 {BORDER}, stop:1 transparent);
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* ── タスク入力欄 ── */
QLineEdit#taskInput {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 11px 16px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 400;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit#taskInput:focus {{
    border: 1px solid {ACCENT};
    background-color: {BG_TERTIARY};
}}
QPushButton#refreshButton,
QPushButton#dueButton {{
    background-color: rgba(139, 92, 246, 0.1);
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0px;
}}
QPushButton#refreshButton {{
    min-width: 24px;
    max-width: 24px;
}}
QPushButton#dueButton {{
    min-width: 72px;
    max-width: 86px;
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 700;
    padding: 0px 8px;
}}
QPushButton#refreshButton:hover,
QPushButton#dueButton:hover {{
    background-color: rgba(139, 92, 246, 0.2);
    border-color: {ACCENT};
}}
QPushButton#refreshButton:pressed,
QPushButton#dueButton:pressed {{
    background-color: rgba(139, 92, 246, 0.28);
    border-color: {ACCENT_GLOW};
}}
QPushButton#dueButton[dueSelected="false"] {{
    padding: 0px;
}}
QPushButton#dueButton[dueSelected="true"] {{
    background-color: rgba(139, 92, 246, 0.36);
    border-color: {ACCENT_GLOW};
}}
QPushButton#dueButton[dueOverdue="true"] {{
    background-color: rgba(239, 68, 68, 0.16);
    border-color: rgba(239, 68, 68, 0.48);
    color: #fecaca;
}}
QPushButton#refreshButton:disabled,
QPushButton#dueButton:disabled {{
    background-color: rgba(139, 92, 246, 0.06);
    border-color: {BORDER_SUBTLE};
}}

/* ── カウンターラベル ── */
QLabel#counterLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 500;
    padding: 2px 0px;
}}

/* ── スクロールエリア ── */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: {SCROLLBAR_BG};
    width: 5px;
    margin: 4px 1px;
    border-radius: 2px;
}}
QScrollBar::handle:vertical {{
    background: {SCROLLBAR_HANDLE};
    min-height: 40px;
    border-radius: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DEEP};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

/* ── タスクアイテム ── */
QFrame#taskItem {{
    background-color: {BG_TERTIARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 10px;
}}
QFrame#taskItem:hover {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
}}
QFrame#taskItem[selected="true"] {{
    background-color: #2d2d4d;
    border: 1px solid {ACCENT};
}}
QFrame#taskItemDone {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 10px;
}}
QFrame#taskItemDone[selected="true"] {{
    border: 1px solid {ACCENT_DEEP};
}}

/* ── チェックボックス ── */
QCheckBox {{
    spacing: 0px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid {BORDER};
    background-color: transparent;
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT_GLOW};
    background-color: rgba(139, 92, 246, 0.08);
}}
QCheckBox::indicator:checked {{
    background-color: {SUCCESS};
    border-color: {SUCCESS};
}}

/* ── タスクタイトル ── */
QLabel#taskTitle {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 450;
    padding: 2px 0px;
}}
QLabel#taskTitleDone {{
    color: {TEXT_DONE};
    font-size: 13px;
    font-weight: 400;
    text-decoration: line-through;
    font-style: italic;
    padding: 2px 0px;
}}
QLabel#taskNotes {{
    color: #cbd5e1;
    font-size: 11px;
    padding-top: 2px;
}}

/* ── プログレスバー ── */
QProgressBar {{
    background-color: {BG_TERTIARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    text-align: center;
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: 600;
    min-height: 22px;
    max-height: 22px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GRADIENT_START}, stop:1 {GRADIENT_END});
    border-radius: 7px;
}}
QProgressBar#syncProgress {{
    min-height: 3px;
    max-height: 3px;
    border: none;
    border-radius: 0px;
    background-color: rgba(255, 255, 255, 0.06);
}}
QProgressBar#syncProgress::chunk {{
    border-radius: 0px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_GLOW});
}}

/* ── フッターボタン ── */
QPushButton#footerButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#footerButton:hover {{
    background-color: rgba(139, 92, 246, 0.1);
    color: {ACCENT_GLOW};
    border-color: {ACCENT_DEEP};
}}
QPushButton#footerButton:pressed {{
    background-color: rgba(139, 92, 246, 0.2);
    color: {ACCENT_SOFT};
}}

/* ── 終了ボタン ── */
QPushButton#quitButton {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#quitButton:hover {{
    background-color: rgba(239, 68, 68, 0.1);
    color: {DANGER};
    border-color: rgba(239, 68, 68, 0.3);
}}
QPushButton#quitButton:pressed {{
    background-color: rgba(239, 68, 68, 0.2);
    color: {DANGER};
}}

/* ── プログレスラベル ── */
QLabel#progressLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 500;
}}
QLabel#progressPercent {{
    color: {ACCENT_GLOW};
    font-size: 20px;
    font-weight: 700;
}}

/* ── 空の状態 ── */
QLabel#emptyLabel {{
    color: {TEXT_MUTED};
    font-size: 13px;
    font-weight: 400;
    padding: 30px 10px;
}}

/* ── ツールチップ ── */
QToolTip {{
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 12px;
}}
"""

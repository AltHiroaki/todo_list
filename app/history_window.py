"""
SlideTasks — 過去ログ閲覧ウィンドウ（プレミアムデザイン版）
matplotlib を埋め込み、達成率を棒グラフで可視化する。
"""

from datetime import date, timedelta
import calendar
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
    QSizePolicy, QHBoxLayout, QScrollArea, QPushButton,
    QDialog, QListWidget, QListWidgetItem, QButtonGroup
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QCursor, QColor, QIcon

from app import database as db
from app.styles import (
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BG_INPUT, BORDER,
    BORDER_SUBTLE, ACCENT, ACCENT_DEEP, ACCENT_GLOW,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DONE,
    SUCCESS, GRADIENT_START, GRADIENT_END, DANGER, DANGER_HOVER,
)


class ClickableCard(QFrame):
    """クリック可能な履歴カード"""
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(50)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_TERTIARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background-color: {BG_INPUT};
                border-color: {ACCENT_GLOW};
            }}
        """)
        
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(12)

        # 日付
        date_lbl = QLabel(f"{entry['date']}")
        date_lbl.setStyleSheet(f"""
            color: {TEXT_PRIMARY}; 
            font-family: 'Consolas', 'Monaco', monospace; 
            font-size: 13px; 
            font-weight: 500;
            border: none; background: transparent;
        """)
        row.addWidget(date_lbl)

        row.addStretch()

        # タスク数
        count_lbl = QLabel(f"{entry['done_count']} / {entry['total_count']}")
        count_lbl.setStyleSheet(f"""
            color: {TEXT_SECONDARY}; 
            font-size: 12px;
            border: none; background: transparent;
        """)
        row.addWidget(count_lbl)

        # 達成率バッジ
        rate = entry["achievement_rate"]
        rate_badge = QLabel(f"{int(rate)}%")
        rate_badge.setFixedSize(48, 24)
        rate_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if rate >= 100:
            bg = "rgba(16, 185, 129, 0.15)"
            fg = SUCCESS
        elif rate >= 50:
            bg = "rgba(139, 92, 246, 0.15)"
            fg = ACCENT_GLOW
        else:
            bg = "rgba(239, 68, 68, 0.15)"
            fg = DANGER

        rate_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border-radius: 4px;
            font-size: 12px;
            font-weight: 700;
            border: none;
        """)
        row.addWidget(rate_badge)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 親ウィンドウのメソッドを呼び出すためにイベントをバブルアップさせるか、
            # シグナルを使うのが一般的だが、ここでは親を探して呼ぶ簡易実装
            window = self.window()
            if isinstance(window, HistoryWindow):
                window.show_details(self.entry['date'])
        super().mousePressEvent(event)


class DetailDialog(QDialog):
    """特定日のタスク一覧を表示するダイアログ"""
    def __init__(self, target_date_str: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{target_date_str} のタスク")
        self.setFixedSize(400, 500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER};
            }}
            QLabel {{ color: {TEXT_PRIMARY}; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ヘッダー
        header = QWidget()
        header.setStyleSheet(f"background-color: {BG_SECONDARY}; border-bottom: 1px solid {BORDER};")
        bg_layout = QHBoxLayout(header)
        bg_layout.setContentsMargins(16, 12, 16, 12)
        
        title = QLabel(f"📅 {target_date_str}")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        bg_layout.addWidget(title)
        bg_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY}; border: none; font-size: 14px;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        bg_layout.addWidget(close_btn)
        
        layout.addWidget(header)
        
        # リスト
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {BG_PRIMARY};
                border: none;
                padding: 8px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {BORDER_SUBTLE};
            }}
            QListWidget::item:hover {{
                background-color: {BG_TERTIARY};
            }}
        """)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.list_widget)
        
        # データのロード
        self._load_tasks(target_date_str)
        
    def _load_tasks(self, date_str: str):
        try:
            target_date = date.fromisoformat(date_str)
            tasks = db.get_tasks_for_date(target_date)
            
            if not tasks:
                item = QListWidgetItem("履歴が見つかりません")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.list_widget.addItem(item)
                return

            for t in tasks:
                self._add_task_item(t)
                
        except ValueError:
            pass

    def _add_task_item(self, task: dict):
        # カスタムウィジェットで表示
        item_widget = QWidget()
        l = QHBoxLayout(item_widget)
        l.setContentsMargins(4, 0, 4, 0)
        l.setSpacing(8)
        
        # 状態アイコン
        is_done = task.get('_status_on_date') == 'done'
        # もしくは現在の is_done を見るべきか？ 
        # get_tasks_for_date で _status_on_date を付与している前提
        
        icon_lbl = QLabel("✔" if is_done else "⬜")
        icon_lbl.setStyleSheet(f"""
            color: {SUCCESS if is_done else TEXT_SECONDARY};
            font-size: 14px;
        """)
        l.addWidget(icon_lbl)
        
        title_lbl = QLabel(task['title'])
        title_lbl.setWordWrap(True)
        if is_done:
            title_lbl.setStyleSheet(f"color: {TEXT_DONE}; text-decoration: line-through;")
        else:
            title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
            
        l.addWidget(title_lbl)
        
        list_item = QListWidgetItem(self.list_widget)
        list_item.setSizeHint(item_widget.sizeHint() + QSize(0, 16)) # 余白
        self.list_widget.addItem(list_item)
        self.list_widget.setItemWidget(list_item, item_widget)


class HistoryWindow(QWidget):
    """過去の達成ログを表示する別ウィンドウ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SlideTasks — 過去ログ")
        self.setMinimumSize(600, 700)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_PRIMARY};
                color: {TEXT_PRIMARY};
                font-family: "Segoe UI Variable", "Segoe UI", "Yu Gothic UI", sans-serif;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 1px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER};
                min-height: 40px;
                border-radius: 3px;
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
        """)
        
        self.current_period = 'week' # default to week
        self.view_date = date.today() # reference date for view

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── ヘッダー ──
        header_container = QWidget()
        header_container.setStyleSheet(f"background-color: {BG_SECONDARY}; border-bottom: 1px solid {BORDER};")
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(12)

        # タイトル行
        top_row = QHBoxLayout()
        title = QLabel("過去の振り返り")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT_PRIMARY};")
        top_row.addWidget(title)
        top_row.addStretch()
        header_layout.addLayout(top_row)

        # 期間切り替え
        period_row = QHBoxLayout()
        period_row.setSpacing(8)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        
        for period, label in [('week', '週 (7日)'), ('month', '月 (30日)'), ('year', '年 (12ヶ月)')]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(28)
            btn.setStyleSheet(self._get_toggle_style())
            if period == self.current_period:
                btn.setChecked(True)
            
            # ラムダで変数をキャプチャするためにデフォルト引数を使用
            btn.clicked.connect(lambda _, p=period: self._set_period(p))
            
            self.btn_group.addButton(btn)
            period_row.addWidget(btn)
            
        period_row.addStretch()
        
        # ナビゲーション
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(12)
        
        self.prev_btn = QPushButton("＜")
        self.prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.prev_btn.setFixedSize(32, 28)
        self.prev_btn.clicked.connect(lambda: self._navigate(-1))
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {BG_TERTIARY}; }}
        """)
        
        self.period_label = QLabel()
        self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.period_label.setFixedWidth(140)
        self.period_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        
        self.next_btn = QPushButton("＞")
        self.next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.next_btn.setFixedSize(32, 28)
        self.next_btn.clicked.connect(lambda: self._navigate(1))
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {BG_TERTIARY}; }}
        """)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.period_label)
        nav_layout.addWidget(self.next_btn)
        
        period_row.addLayout(nav_layout)
        header_layout.addLayout(period_row)

        layout.addWidget(header_container)

        # ── スクロールエリア ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        scroll_content = QWidget()
        self._inner_layout = QVBoxLayout(scroll_content)
        self._inner_layout.setContentsMargins(24, 24, 24, 24)
        self._inner_layout.setSpacing(24)

        # グラフ
        self.chart_wrapper = QFrame()
        self.chart_wrapper.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 12px;
            }}
        """)
        chart_layout = QVBoxLayout(self.chart_wrapper)
        chart_layout.setContentsMargins(16, 16, 16, 16)
        
        self.chart_container = QVBoxLayout()
        chart_layout.addLayout(self.chart_container)
        self._inner_layout.addWidget(self.chart_wrapper)

        # リスト
        list_header = QLabel("詳細ログ")
        list_header.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 8px;")
        self._inner_layout.addWidget(list_header)
        
        self.list_container = QVBoxLayout()
        self.list_container.setSpacing(8)
        self._inner_layout.addLayout(self.list_container)
        self._inner_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # ── フッター ──
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {BG_SECONDARY}; border-top: 1px solid {BORDER};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.addStretch()
        
        close_btn = QPushButton("閉じる")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.close)
        close_btn.setFixedSize(100, 36)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_TERTIARY};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {BG_INPUT};
                border-color: {ACCENT_GLOW};
            }}
        """)
        footer_layout.addWidget(close_btn)
        layout.addWidget(footer)

    def _get_toggle_style(self):
        return f"""
            QPushButton {{
                background-color: {BG_PRIMARY};
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER};
                border-radius: 14px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
                border-color: {ACCENT};
            }}
            QPushButton:checked {{
                background-color: {ACCENT};
                color: white;
                border-color: {ACCENT};
            }}
        """

    def showEvent(self, event):
        super().showEvent(event)
        self.view_date = date.today() # Reset to today when opening
        self._load_data()

    def _set_period(self, period):
        if self.current_period != period:
            self.current_period = period
            self.view_date = date.today() # Reset date when switching modes
            self._load_data()

    def _navigate(self, direction):
        if self.current_period == 'week':
            self.view_date += timedelta(weeks=direction)
        elif self.current_period == 'month':
            # 月単位の移動
            # 現在の月の1日を取得
            curr_month_start = self.view_date.replace(day=1)
            
            # 月の計算 (1-12に正規化)
            year = curr_month_start.year
            month = curr_month_start.month + direction
            
            # 正しい年月に補正
            year += (month - 1) // 12
            month = (month - 1) % 12 + 1
            
            self.view_date = date(year, month, 1)

        elif self.current_period == 'year':
            self.view_date = self.view_date.replace(year=self.view_date.year + direction)
        
        self._load_data()

    def _get_date_range(self):
        """現在のモードと表示基準日から、表示期間の開始日・終了日を計算"""
        if self.current_period == 'week':
            # 月曜始まり
            start = self.view_date - timedelta(days=self.view_date.weekday())
            end = start + timedelta(days=6)
            return start, end
        elif self.current_period == 'month':
            # 月初〜月末
            start = self.view_date.replace(day=1)
            _, last_day = calendar.monthrange(start.year, start.month)
            end = start.replace(day=last_day)
            return start, end
        elif self.current_period == 'year':
            # 1月1日〜12月31日
            start = date(self.view_date.year, 1, 1)
            end = date(self.view_date.year, 12, 31)
            return start, end
        return self.view_date, self.view_date

    def _update_period_label(self, start, end):
        if self.current_period == 'week':
            # "2/16 - 2/22"
            text = f"{start.strftime('%m/%d')} - {end.strftime('%m/%d')}"
            # 年が違う場合などは考慮してもいいがシンプルに
            if start.year != end.year:
                text = f"{start.strftime('%Y/%m/%d')} - {end.strftime('%Y/%m/%d')}"
        elif self.current_period == 'month':
            # "2026年 2月"
            text = f"{start.year}年 {start.month}月"
        elif self.current_period == 'year':
            # "2026年"
            text = f"{start.year}年"
        
        self.period_label.setText(text)

    def _load_data(self):
        self._clear_layout(self.chart_container)
        self._clear_layout(self.list_container)

        start_date, end_date = self._get_date_range()
        self._update_period_label(start_date, end_date)

        if self.current_period == 'year':
            logs = db.get_yearly_stats(start_date.year)
        else:
            raw_logs = db.get_logs_in_range(start_date, end_date)
            # 日付の抜け漏れを埋める（Week/Month表示用）
            logs = self._fill_missing_dates(raw_logs, start_date, end_date)

        # グラフ描画（データが全て0でも枠を表示するために draw_chart を呼ぶ）
        # ただし、logsが空（あり得ないはずだが）の場合はスキップ
        if not logs:
             # _fill_missing_dates を通せば空にはならないが念のため
            empty = QLabel("データがありません")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {TEXT_MUTED}; padding: 40px;")
            self.list_container.addWidget(empty)
            return

        try:
            self._draw_chart(logs)
        except ImportError:
            pass

        self._draw_list(logs)

    def _fill_missing_dates(self, existing_logs: list[dict], start: date, end: date) -> list[dict]:
        """指定期間の全ての日付のエントリを作成し、既存データがあれば埋め込む"""
        # 日付文字列をキーにした辞書
        log_map = {log['date']: log for log in existing_logs}
        
        filled_logs = []
        curr = start
        while curr <= end:
            d_str = curr.isoformat()
            if d_str in log_map:
                filled_logs.append(log_map[d_str])
            else:
                # 空エントリ
                filled_logs.append({
                    'date': d_str,
                    'total_count': 0,
                    'done_count': 0,
                    'achievement_rate': 0.0
                })
            curr += timedelta(days=1)
            
        # UI側は新しい日付順（降順）を期待している箇所と昇順を期待している箇所があるが
        # get_logs_in_range は DESC (新しい順) で返している。
        # ここでは日付順（古い順）に生成してしまったので、reverse して新しい順にする
        return list(reversed(filled_logs))

    def _draw_chart(self, logs: list[dict]):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        import matplotlib.pyplot as plt

        plt.rcParams['axes.facecolor'] = BG_SECONDARY
        plt.rcParams['figure.facecolor'] = BG_SECONDARY
        plt.rcParams['text.color'] = TEXT_SECONDARY
        plt.rcParams['axes.labelcolor'] = TEXT_SECONDARY
        plt.rcParams['xtick.color'] = TEXT_SECONDARY
        plt.rcParams['ytick.color'] = TEXT_SECONDARY
        plt.rcParams['axes.edgecolor'] = BORDER
        # 日本語フォント設定 (Windows向け)
        plt.rcParams['font.family'] = ['Meiryo', 'Yu Gothic', 'MS Gothic', 'sans-serif']

        # データを昇順（古い日付 -> 新しい日付）に並べ替え
        logs_asc = list(reversed(logs))
        
        # 表示形式の調整
        formatted_dates = []
        if self.current_period == 'year':
            # "2026-01" -> "1月"
            for entry in logs_asc:
                try:
                    m_str = entry["date"].split('-')[1]
                    formatted_dates.append(f"{int(m_str)}月")
                except:
                    formatted_dates.append(entry["date"])
        else:
            # "2026-02-16" -> "2/16"
            for entry in logs_asc:
                try:
                    dt = date.fromisoformat(entry["date"])
                    formatted_dates.append(f"{dt.month}/{dt.day}")
                except:
                    formatted_dates.append(entry["date"][-5:])
            
        rates = [entry["achievement_rate"] for entry in logs_asc]

        fig = Figure(figsize=(5, 2.5), dpi=100)
        ax = fig.add_subplot(111)

        bar_colors = []
        for rate in rates:
            if rate >= 100: bar_colors.append(SUCCESS)
            elif rate >= 50: bar_colors.append(ACCENT)
            else: bar_colors.append(ACCENT_DEEP)

        # 棒の太さ調整
        bar_width = 0.6
        if self.current_period == 'month':
            bar_width = 0.5
        elif self.current_period == 'week':
            bar_width = 0.5 

        ax.bar(formatted_dates, rates, color=bar_colors, width=bar_width, edgecolor="none", zorder=3)
        ax.grid(axis='y', color=BORDER, linestyle='--', linewidth=0.5, alpha=0.5, zorder=0)
        ax.set_ylim(0, 105)
        ax.tick_params(axis='both', which='major', labelsize=8)
        
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.spines['bottom'].set_visible(True)
        ax.spines['bottom'].set_color(BORDER)

        # X軸ラベルの間引き（月間表示で混雑する場合など）
        if len(formatted_dates) > 10:
            from matplotlib.ticker import MaxNLocator
            ax.xaxis.set_major_locator(MaxNLocator(nbins=10))
            # Matplotlibの自動間引きに任せるか、自前で設定するか
            # ここでは単純に set_xticks で指定するとラベルとの対応がずれることがあるので注意が必要
            # 文字列ラベルの場合はリスト指定が安全
            
            # 月間(30日)の場合、5日おきくらいにする
            if self.current_period == 'month':
                # 全てプロットした後、表示するラベルだけ残す
                ticks = range(len(formatted_dates))
                labels = [formatted_dates[i] if i % 5 == 0 else "" for i in ticks]
                # 一旦全てのTickを設定してからLabelsを上書き
                ax.set_xticks(ticks)
                ax.set_xticklabels(labels)
        
        fig.tight_layout(pad=0.5)
        
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(200)
        canvas.setStyleSheet("background: transparent;")
        self.chart_container.addWidget(canvas)

    def _draw_list(self, logs: list[dict]):
        for entry in logs:
            if self.current_period != 'year': # 年表示(月別)の時は詳細クリックは未対応(日付単位じゃないので)
                card = ClickableCard(entry)
            else:
                # 年表示の場合はクリック不可のカードにする（手抜きだが ClickableCard を流用してイベント無視でもよいが） 

                card = ClickableCard(entry)
                
            self.list_container.addWidget(card)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def show_details(self, date_str):
        # 年単位表示の "YYYY-MM" 形式などは詳細表示対象外とする（あるいはその月の全タスク？今回は日毎要件なのでスキップ）
        if len(date_str) == 7: # YYYY-MM
            return
            
        dlg = DetailDialog(date_str, self)
        dlg.exec()

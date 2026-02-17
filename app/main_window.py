"""
SlideTasks — メインウィンドウ
フレームレス常駐型ウィンドウ + スライドアニメーション。
格納時は透明な小さいホバーゾーン (36×60px) のみ。
マウスが近づくと矢印がフェードイン → クリックでパネル展開。
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QProgressBar, QLabel, QApplication,
    QSizePolicy, QFrame, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, QSize, QPoint,
    pyqtProperty, QEvent,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QDesktopServices,
    QIcon,
    QPainter,
    QPen,
    QRegion,
    QScreen, QFont, QPixmap, QBrush,
)

from datetime import date

from app.styles import MAIN_STYLESHEET
from app.task_widget import TaskListWidget
from app.history_window import HistoryWindow
from app import database as db
from app import daily_reset
from app import startup


# ── 定数 ──────────────────────────────────────────────
TRIGGER_WIDTH = 36         # ホバーゾーン幅
TRIGGER_HEIGHT = 60        # ホバーゾーン高さ
EXPANDED_WIDTH = 340       # 展開モード幅
ANIMATION_DURATION = 300   # スライドアニメーション ms
WINDOW_HEIGHT_RATIO = 0.85 # 展開時の画面高さ割合
DAILY_CHECK_INTERVAL = 60_000

# ── トグルボタンのスタイル ──
_TOGGLE_IDLE = """
    QPushButton#toggleButton {
        background: rgba(139, 92, 246, 0.15);
        color: rgba(255, 255, 255, 0.25);
        border: none;
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: 13px;
        font-weight: 600;
    }
"""
_TOGGLE_HOVER = """
    QPushButton#toggleButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #8b5cf6, stop:0.5 #6d28d9, stop:1 #4c1d95);
        color: rgba(255, 255, 255, 0.95);
        border: none;
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: 14px;
        font-weight: 600;
    }
"""
_TOGGLE_EXPANDED = """
    QPushButton#toggleButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #8b5cf6, stop:0.5 #6d28d9, stop:1 #4c1d95);
        color: rgba(255, 255, 255, 0.95);
        border: none;
        border-radius: 0px;
        font-size: 14px;
        font-weight: 600;
    }
"""


class MainWindow(QMainWindow):
    """常駐型スライドウィンドウ"""

    def __init__(self):
        super().__init__()

        # ── ウィンドウ設定 ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(MAIN_STYLESHEET)

        self._is_expanded = False
        self._animating = False
        self._current_mask_width = TRIGGER_WIDTH

        # ── ジオメトリ計算 ──
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        self._screen_right = screen_geo.right() + 1
        self._screen_top = screen_geo.top()
        self._screen_height = screen_geo.height()
        self._expanded_height = int(self._screen_height * WINDOW_HEIGHT_RATIO)
        self._expanded_y = self._screen_top + (self._screen_height - self._expanded_height) // 2
        
        # ウィンドウサイズは常に「展開時」の最大サイズで固定
        self.setFixedSize(EXPANDED_WIDTH, self._expanded_height)
        
        # 初期配置: 常に展開時の位置に固定 (右端)
        x = self._screen_right - EXPANDED_WIDTH
        self.move(x, self._expanded_y)

        # ── コンテナウィジェット (中身) ──
        # これをマスクで切り取ることでスライド表現を行う
        container = QWidget(self)
        container.setObjectName("container")
        container.setFixedSize(EXPANDED_WIDTH, self._expanded_height)
        
        # レイアウト (コンテンツ + トグルボタン)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ── コンテンツパネル（左側）──
        self.content_panel = QWidget()
        self.content_panel.setObjectName("contentPanel")
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(0, 14, 0, 14)
        content_layout.setSpacing(0)

        # タスクリスト
        self.task_list = TaskListWidget()
        self.task_list.tasks_changed.connect(self._update_progress)
        self.task_list.task_added.connect(lambda _, __: None) # シグナル接続プレースホルダ
        # 実際には下で SyncWorker と再接続するが、
        # ここではレイアウト構築に集中
        content_layout.addWidget(self.task_list)

        # ── プログレスセクション ──
        progress_container = QWidget()
        progress_outer = QVBoxLayout(progress_container)
        progress_outer.setContentsMargins(14, 4, 14, 0)
        progress_outer.setSpacing(6)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        progress_outer.addWidget(sep)
        progress_outer.addSpacing(6)

        progress_header = QHBoxLayout()
        progress_header.setSpacing(0)

        progress_label = QLabel("今日の進捗")
        progress_label.setObjectName("progressLabel")
        progress_header.addWidget(progress_label)
        progress_header.addStretch()

        self.progress_pct_label = QLabel("0%")
        self.progress_pct_label.setObjectName("progressPercent")
        progress_header.addWidget(self.progress_pct_label)

        progress_outer.addLayout(progress_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        progress_outer.addWidget(self.progress_bar)

        content_layout.addWidget(progress_container)
        content_layout.addSpacing(8)

        # ── フッターボタン群 ──
        footer_container = QWidget()
        footer_layout = QVBoxLayout(footer_container)
        footer_layout.setContentsMargins(14, 0, 14, 0)
        footer_layout.setSpacing(6)

        self.log_button = QPushButton("📊  過去ログを見る")
        self.log_button.setObjectName("footerButton")
        self.log_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_button.clicked.connect(self._show_history)
        footer_layout.addWidget(self.log_button)

        # ── 終了ボタン ──
        self.quit_button = QPushButton("✕  アプリを終了")
        self.quit_button.setObjectName("quitButton")
        self.quit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_button.clicked.connect(self._quit_app)
        footer_layout.addWidget(self.quit_button)

        content_layout.addWidget(footer_container)
        
        container_layout.addWidget(self.content_panel)

        # ── トグルボタン（右側）──
        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setObjectName("toggleButton")
        self.toggle_btn.setFixedWidth(TRIGGER_WIDTH)
        self.toggle_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_slide)
        self.toggle_btn.setStyleSheet(_TOGGLE_IDLE)

        container_layout.addWidget(self.toggle_btn)

        # ── レイアウト比率設定 ──
        # コンテンツパネルが残りの幅を全て使う
        
        # ── スライドアニメーション（マスク幅ベース）──
        self._slide_anim = QPropertyAnimation(self, b"slideWidth")
        self._slide_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._slide_anim.setDuration(ANIMATION_DURATION)
        self._slide_anim.finished.connect(self._on_animation_finished)

        # ── マウス追跡 ──
        self.setMouseTracking(True)
        container.setMouseTracking(True)
        self.content_panel.setMouseTracking(True)
        self.toggle_btn.setMouseTracking(True)

        # ── 日次リセットタイマー ──
        daily_reset.initialize()
        self._daily_timer = QTimer(self)
        self._daily_timer.timeout.connect(self._check_daily_reset)
        self._daily_timer.start(DAILY_CHECK_INTERVAL)

        # ── 過去ログウィンドウ ──
        self._history_window = None

        # ── システムトレイ ──
        self._setup_tray()
        
        # ── 初期状態のマスク適用 (格納状態) ──
        self._current_mask_width = TRIGGER_WIDTH
        self._apply_mask(TRIGGER_WIDTH)

        # ── DB 初期化 & タスク読み込み ──
        db.init_db()
        self.task_list.load_tasks()
        self._update_date_label()
        self._update_progress()

        # ── Google Sync 初期化 ──
        self.sync_thread = QThread()
        self.sync_worker = SyncWorker()
        self.sync_worker.moveToThread(self.sync_thread)
        
        # シグナル接続: UI -> Worker
        self.task_list.task_added.connect(self.sync_worker.push_add)
        self.task_list.task_toggled.connect(self.sync_worker.push_toggle)
        self.task_list.task_deleted.connect(self.sync_worker.push_delete)

        # シグナル接続: Worker -> UI
        self.sync_worker.data_changed.connect(self._on_remote_data_changed)
        
        self.sync_thread.start()
        
        # 初回同期 (スレッド内で実行)
        QTimer.singleShot(0, self.sync_worker.initial_sync)
        
        # 定期ポーリング (60秒)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.sync_worker.poll_tasks)
        self.poll_timer.start(60_000)

    def _on_remote_data_changed(self):
        """バックグラウンド同期で変更があった場合、UIを更新"""
        # 現在の入力中などでなければリロード推奨
        # ただし、入力中にリロードすると入力内容が消える恐れがあるが、
        # TaskListWidget.load_tasks は input_field をクリアしないので大丈夫そう。
        self.task_list.load_tasks()
        self._update_progress()

    def _apply_mask(self, visible_width: int):
        """ウィンドウの表示領域を右端から visible_width 分だけに切り取る"""
        # 右端を基準にするので、左端のX座標は (EXPANDED_WIDTH - visible_width)
        x = EXPANDED_WIDTH - visible_width
        rect = QRegion(x, 0, visible_width, self.height())
        self.setMask(rect)
        self._current_mask_width = visible_width

    # ━━━━ pyqtProperty: slideWidth（マスクアニメーション用）━━━━
    def _get_slide_width(self) -> int:
        return self._current_mask_width

    def _set_slide_width(self, w: int):
        self._apply_mask(w)

    slideWidth = pyqtProperty(int, fget=_get_slide_width, fset=_set_slide_width)

    # ━━━━ 廃止: 位置計算 (固定のため不要) ━━━━

    # ━━━━ ホバー: 矢印のスタイル切替 ━━━━
    def enterEvent(self, event):
        """マウスがウィンドウに入った → 矢印を明るく"""
        super().enterEvent(event)
        if not self._is_expanded and not self._animating:
            self.toggle_btn.setStyleSheet(_TOGGLE_HOVER)

    def leaveEvent(self, event):
        """マウスがウィンドウから出た → 矢印を薄く"""
        super().leaveEvent(event)
        if not self._is_expanded and not self._animating:
            self.toggle_btn.setStyleSheet(_TOGGLE_IDLE)

    # ━━━━ スライドアニメーション ━━━━
    def _toggle_slide(self):
        if self._animating:
            return
        self._animating = True

        if self._is_expanded:
            # 格納
            self.toggle_btn.setText("◀")
            self._slide_anim.setStartValue(EXPANDED_WIDTH)
            self._slide_anim.setEndValue(TRIGGER_WIDTH)
        else:
            # 展開
            self.toggle_btn.setStyleSheet(_TOGGLE_EXPANDED)
            self.toggle_btn.setText("✕")
            self.task_list.load_tasks()
            self._update_date_label()
            
            self._slide_anim.setStartValue(TRIGGER_WIDTH)
            self._slide_anim.setEndValue(EXPANDED_WIDTH)

        self._slide_anim.start()

    def _on_animation_finished(self):
        self._is_expanded = not self._is_expanded
        self._animating = False

        if not self._is_expanded:
            # 格納完了
            self.toggle_btn.setStyleSheet(_TOGGLE_IDLE)
        else:
            # 展開完了 → フォーカスを入力欄に
            self.task_list.input_field.setFocus()

    # ━━━━ フォーカスアウトで格納 ━━━━
    def changeEvent(self, event):
        super().changeEvent(event)
        if (
            event.type() == event.Type.ActivationChange
            and not self.isActiveWindow()
            and self._is_expanded
            and not self._animating
        ):
            active = QApplication.activeWindow()
            if active and isinstance(active, HistoryWindow):
                return
            self._toggle_slide()

    # ━━━━ プログレスバー更新 ━━━━
    def _update_progress(self):
        total, done = db.get_today_stats()
        pct = int(done / total * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.progress_pct_label.setText(f"{pct}%")
        if pct >= 100:
            self.progress_pct_label.setStyleSheet(
                "color: #10b981; font-size: 20px; font-weight: 700;"
            )
        else:
            self.progress_pct_label.setStyleSheet(
                "color: #a78bfa; font-size: 20px; font-weight: 700;"
            )

    # ━━━━ 日付ラベル ━━━━
    def _update_date_label(self):
        today = date.today()
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        wd = weekdays[today.weekday()]
        self.task_list.update_date_label(
            f"{today.strftime('%Y/%m/%d')} ({wd})"
        )

    # ━━━━ 日次リセット ━━━━
    def _check_daily_reset(self):
        if daily_reset.check_and_reset():
            self.task_list.load_tasks()
            self._update_progress()
            self._update_date_label()

    # ━━━━ 過去ログ ━━━━
    def _show_history(self):
        if self._history_window is None:
            self._history_window = HistoryWindow()
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    # ━━━━ システムトレイ ━━━━
    def _create_tray_icon(self) -> QIcon:
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#8b5cf6")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, size - 8, size - 8, 14, 14)
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(18, 33, 28, 43)
        painter.drawLine(28, 43, 46, 22)
        painter.end()
        return QIcon(pixmap)

    def _setup_tray(self):
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(self._create_tray_icon())
        self._tray_icon.setToolTip("SlideTasks")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e33;
                color: #f1f0f7;
                border: 1px solid #2a2a45;
                border-radius: 8px;
                padding: 6px 2px;
                font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 24px 8px 16px;
                border-radius: 4px;
                margin: 1px 4px;
            }
            QMenu::item:selected {
                background-color: rgba(139, 92, 246, 0.2);
                color: #a78bfa;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2a2a45;
                margin: 4px 12px;
            }
        """)

        toggle_action = QAction("📋  パネルを開く", self)
        toggle_action.triggered.connect(self._toggle_slide)
        tray_menu.addAction(toggle_action)

        history_action = QAction("📊  過去ログ", self)
        history_action.triggered.connect(self._show_history)
        tray_menu.addAction(history_action)

        tray_menu.addSeparator()

        self._startup_action = QAction(self)
        self._update_startup_action_text()
        self._startup_action.triggered.connect(self._toggle_startup)
        tray_menu.addAction(self._startup_action)

        tray_menu.addSeparator()

        quit_action = QAction("✕  終了", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_slide()

    def _toggle_startup(self):
        if startup.is_registered():
            startup.unregister()
        else:
            startup.register()
        self._update_startup_action_text()

    def _update_startup_action_text(self):
        if startup.is_registered():
            self._startup_action.setText("⏻  スタートアップ解除")
        else:
            self._startup_action.setText("⏻  スタートアップに登録")

    def _quit_app(self):
        self._tray_icon.hide()
        QApplication.quit()


# ── 同期ワーカースレッド ──
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from app.google_sync import google_sync

class SyncWorker(QObject):
    """Google Tasks との同期をバックグラウンドで行う"""
    
    # UI更新要求シグナル
    data_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
    
    def initial_sync(self):
        """起動時の同期: Google優先 + カレンダー削除同期"""
        if not google_sync.is_available():
            return
            
        # 認証 (初回など)
        if not google_sync.authenticate():
            return

        # 1. カレンダー側で削除されたものを検知して同期
        self._sync_calendar_deletions()

        # 2. Tasks 同期
        self._pull_from_google()
        self._push_missing_to_google()
        self.data_changed.emit()

    def _sync_calendar_deletions(self):
        """カレンダーで削除されたイベントに対応するタスクを削除"""
        conn = db._get_connection()
        # カレンダー連携しており、かつ未完了のタスク
        rows = conn.execute(
            "SELECT id, google_calendar_event_id, google_task_id FROM tasks WHERE google_calendar_event_id IS NOT NULL"
        ).fetchall()
        conn.close()
        
        tasks_to_check = [dict(r) for r in rows]
        if not tasks_to_check:
            return
            
        deleted_ids = google_sync.check_calendar_deletions(tasks_to_check)
        
        if deleted_ids:
            # 削除実行
            for tid in deleted_ids:
                # DBからタスク情報を取得（Google Task IDが必要）
                # tasks_to_check から探す
                target = next((t for t in tasks_to_check if t['id'] == tid), None)
                if target:
                    # Google Tasks からも削除
                    if target['google_task_id']:
                        google_sync.delete_task(target['google_task_id'])
                        
                    # ローカル削除
                    db.delete_task(tid)
            
            # 変更通知は initial_sync の最後で emit

    def poll_tasks(self):
        """定期ポーリング"""
        if not google_sync.is_available():
            return
        
        # 変更があった場合のみ emit したいが、
        # 簡易実装として pull して変更あれば DB 更新 -> data_changed
        if self._pull_from_google():
            self.data_changed.emit()

    def push_add(self, task_id: int, title: str, due_date: str = ""):
        """タスク追加をPush"""
        # due_date が空文字の場合は None にする
        d_date = due_date if due_date else None
        gid = google_sync.add_task(title, due_date=d_date)
        if gid:
            db.update_google_task_id(task_id, gid)
            
        # カレンダー連携: 期限がある場合のみ
        if due_date:
            eid = google_sync.add_calendar_event(title, due_date)
            if eid:
                db.update_google_calendar_event_id(task_id, eid)

    def push_toggle(self, task_id: int, is_done: bool):
        """完了状態をPush"""
        # Google ID を取得
        conn = db._get_connection()
        row = conn.execute("SELECT google_task_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        
        gid = row["google_task_id"] if row else None
        if not gid:
            return

        if is_done:
            google_sync.complete_task(gid)
        else:
            # 完了を取り消す (needsActionに戻す)
            google_sync.reopen_task(gid) 

    def push_delete(self, task_id: int, google_task_id: str):
        """削除をPush"""
        if google_task_id:
            google_sync.delete_task(google_task_id)

    def _pull_from_google(self) -> bool:
        """
        Google からタスクを取得し、ローカルDBと同期する。
        変更があったら True を返す。
        """
        remote_tasks = google_sync.fetch_tasks() # list[dict(id, title, ...)]
        if remote_tasks is None:
            return False

        changed = False
        remote_map = {t['id']: t for t in remote_tasks}
        
        # 1. リモートにあるものをローカルに反映 (追加/更新)
        # ローカルの全タスク(アクティブ)を取得
        local_tasks = db.get_active_tasks()
        local_map = {t['google_task_id']: t for t in local_tasks if t['google_task_id']}
        
        conn = db._get_connection()
        
        for gid, r_item in remote_map.items():
            title = r_item['title']
            is_completed = (r_item['status'] == 'completed')
            
            if gid in local_map:
                # 既存: タイトル更新 / 完了状態同期
                l_item = local_map[gid]
                
                # タイトルの同期
                if l_item['title'] != title:
                    conn.execute("UPDATE tasks SET title = ? WHERE google_task_id = ?", (title, gid))
                    changed = True
                
                # 完了状態の同期 (Googleが完了ならローカルも完了に、逆も然り)
                # ただし「今日完了したタスク」などはローカルに残っているので、ステータス合わせる
                l_done = bool(l_item['is_done'])
                if l_done != is_completed:
                    # Googleの状態を正とする
                    new_done = 1 if is_completed else 0
                    completed_at = None
                    if new_done:
                        from datetime import datetime
                        completed_at = datetime.now().isoformat()
                    
                    conn.execute(
                        "UPDATE tasks SET is_done = ?, completed_at = ? WHERE id = ?",
                        (new_done, completed_at, l_item['id'])
                    )
                    changed = True

            else:
                # 新規 (ローカルにない)
                # ただし「完了済み」でかつ「今日作成/完了」でない古いタスクを持ってきてしまうと
                # 過去ログ行きのはずがリストに復活してしまう可能性がある。
                # get_active_tasks は「今日完了」or「未完了」しか返さない。
                # Googleから取得したのは「未完了」+「直近24時間完了」。
                # したがって、ここで追加してよい。
                
                # ただし、DBには「過去に完了してアーカイブされた」タスクが残っているわけではない(deleteされている)。
                # なので単純に追加でOK。
                # もし「昨日完了」したものがGoogleから返ってきた場合、ローカルでは「今日完了」として復活する？
                # -> created_at は現在時刻になるので、「今日作成された完了タスク」に見える。
                # 実用上は大きな問題ではないが、completed_at は入れておきたい。
                
                now_str = date.today().isoformat()
                from datetime import datetime
                created_at = datetime.now().isoformat()
                completed_at = created_at if is_completed else None
                is_done_val = 1 if is_completed else 0
                
                conn.execute(
                    "INSERT INTO tasks (title, is_done, created_at, completed_at, google_task_id) VALUES (?, ?, ?, ?, ?)",
                    (title, is_done_val, created_at, completed_at, gid)
                )
                changed = True
        
        # 2. ローカルにあってリモートにないもの (Googleで削除された -> ローカルも削除)
        # ただし "まだ同期されていない新規ローカルタスク" (google_task_id is None) は消してはいけない
        for gid, l_item in local_map.items():
            if gid not in remote_map:
                # Google側で消えている -> ローカルも削除
                # ここで「完了タスク」が消えていたバグ対策:
                # Google側で完了していても remote_map に入るようになったので、
                # ここで remote_map に無い＝「本当に削除された」or「24時間以上前に完了した」
                # 古い完了タスクはローカルからも消えて良いので、このロジックでOK。
                conn.execute("DELETE FROM tasks WHERE id = ?", (l_item['id'],))
                changed = True

        if changed:
            conn.commit()
        conn.close()
        return changed

    def _push_missing_to_google(self):
        """google_task_id がないタスクを Google にアップロード"""
        conn = db._get_connection()
        rows = conn.execute("SELECT * FROM tasks WHERE google_task_id IS NULL").fetchall()
        conn.close()
        
        for row in rows:
            gid = google_sync.add_task(row["title"])
            if gid:
                db.update_google_task_id(row["id"], gid)

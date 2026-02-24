"""Calendar popup used for due-date selection."""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import QDate, QLocale, Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class CalendarPopup(QDialog):
    """Due-date picker with quick presets and calendar-only selection."""

    def __init__(self, parent=None, initial_due: str | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("calendarPopup")
        self._selected_due: str | None = None
        self._formatted_dates: list[QDate] = []

        self.setStyleSheet(
            """
            QDialog#calendarPopup {
                background-color: #1e1e33;
                border: 1px solid #2a2a45;
                border-radius: 10px;
            }
            QLabel#calendarPopupTitle {
                color: #f8fafc;
                font-size: 13px;
                font-weight: 700;
                padding: 0px 2px 2px 2px;
            }
            QPushButton#quickDueButton,
            QPushButton#quickDueClearButton {
                background-color: rgba(139, 92, 246, 0.12);
                color: #c4b5fd;
                border: 1px solid #2a2a45;
                border-radius: 7px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#quickDueButton:hover,
            QPushButton#quickDueClearButton:hover {
                background-color: rgba(139, 92, 246, 0.22);
                border-color: #8b5cf6;
                color: #ede9fe;
            }
            QPushButton#quickDueClearButton {
                color: #fecaca;
                background-color: rgba(239, 68, 68, 0.10);
                border-color: rgba(239, 68, 68, 0.35);
            }
            QPushButton#quickDueClearButton:hover {
                background-color: rgba(239, 68, 68, 0.18);
                border-color: rgba(239, 68, 68, 0.55);
            }
            QCalendarWidget {
                background: transparent;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #17172a;
                border: 1px solid #2a2a45;
                border-radius: 8px;
                margin-bottom: 4px;
                padding: 2px;
            }
            QCalendarWidget QToolButton {
                color: #e2e8f0;
                background: transparent;
                border: none;
                min-width: 26px;
                min-height: 24px;
                font-size: 12px;
                font-weight: 600;
            }
            QCalendarWidget QToolButton:hover {
                background: rgba(139, 92, 246, 0.18);
                border-radius: 6px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                font-size: 12px;
                color: #f8fafc;
                background-color: #1e1e33;
                selection-background-color: #7c3aed;
                selection-color: #ffffff;
                outline: 0;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title_label = QLabel("期限を設定")
        title_label.setObjectName("calendarPopupTitle")
        layout.addWidget(title_label)

        quick_top = QHBoxLayout()
        quick_top.setSpacing(6)
        layout.addLayout(quick_top)

        quick_bottom = QHBoxLayout()
        quick_bottom.setSpacing(6)
        layout.addLayout(quick_bottom)

        def _quick_button(label: str, object_name: str = "quickDueButton") -> QPushButton:
            button = QPushButton(label)
            button.setObjectName(object_name)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            return button

        self.quick_today_btn = _quick_button("今日")
        self.quick_tomorrow_btn = _quick_button("明日")
        self.quick_weekend_btn = _quick_button("今週末")
        self.quick_next_week_btn = _quick_button("来週")
        self.quick_clear_btn = _quick_button("期限なし", "quickDueClearButton")

        quick_top.addWidget(self.quick_today_btn)
        quick_top.addWidget(self.quick_tomorrow_btn)
        quick_top.addWidget(self.quick_weekend_btn)
        quick_bottom.addWidget(self.quick_next_week_btn)
        quick_bottom.addWidget(self.quick_clear_btn)
        quick_bottom.addStretch()

        self.calendar = QCalendarWidget()
        self.calendar.setObjectName("dueCalendar")
        self.calendar.setGridVisible(False)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.calendar.setLocale(QLocale(QLocale.Language.Japanese, QLocale.Country.Japan))
        self.calendar.setMinimumHeight(220)
        self.calendar.clicked.connect(self._accept_qdate)
        self.calendar.currentPageChanged.connect(self._refresh_date_formats)
        layout.addWidget(self.calendar)

        self.quick_today_btn.clicked.connect(lambda: self._accept_pydate(date.today()))
        self.quick_tomorrow_btn.clicked.connect(lambda: self._accept_pydate(date.today() + timedelta(days=1)))
        self.quick_weekend_btn.clicked.connect(self._accept_this_weekend)
        self.quick_next_week_btn.clicked.connect(self._accept_next_week)
        self.quick_clear_btn.clicked.connect(self._accept_no_due)

        initial_qdate = self._parse_qdate(initial_due)
        if initial_qdate is not None:
            self.calendar.setSelectedDate(initial_qdate)
            self._selected_due = initial_due
        else:
            self.calendar.setSelectedDate(QDate.currentDate())
            self._selected_due = None

        self._refresh_date_formats()

    @staticmethod
    def _parse_qdate(raw: str | None) -> QDate | None:
        if not raw:
            return None
        parsed = QDate.fromString(raw, "yyyy-MM-dd")
        return parsed if parsed.isValid() else None

    @staticmethod
    def _to_qdate(value: date) -> QDate:
        return QDate(value.year, value.month, value.day)

    def _accept_pydate(self, value: date) -> None:
        self._accept_qdate(self._to_qdate(value))

    def _accept_this_weekend(self) -> None:
        today = date.today()
        if today.weekday() >= 5:
            self._accept_pydate(today)
            return
        days_until_sat = 5 - today.weekday()
        self._accept_pydate(today + timedelta(days=days_until_sat))

    def _accept_next_week(self) -> None:
        today = date.today()
        days_until_next_monday = 7 - today.weekday()
        self._accept_pydate(today + timedelta(days=days_until_next_monday))

    def _accept_qdate(self, value: QDate) -> None:
        if not value.isValid():
            return
        self._selected_due = value.toString("yyyy-MM-dd")
        self.accept()

    def _accept_no_due(self) -> None:
        self._selected_due = None
        self.accept()

    def _refresh_date_formats(self, *_args) -> None:
        default_fmt = QTextCharFormat()
        for formatted in self._formatted_dates:
            self.calendar.setDateTextFormat(formatted, default_fmt)
        self._formatted_dates.clear()

        shown = QDate(self.calendar.yearShown(), self.calendar.monthShown(), 1)
        if not shown.isValid():
            return

        today = QDate.currentDate()
        overdue_fmt = QTextCharFormat()
        overdue_fmt.setForeground(QColor("#fca5a5"))

        for day in range(1, shown.daysInMonth() + 1):
            current = QDate(shown.year(), shown.month(), day)
            if current < today:
                self.calendar.setDateTextFormat(current, overdue_fmt)
                self._formatted_dates.append(current)

        today_fmt = QTextCharFormat()
        today_fmt.setForeground(QColor("#f8fafc"))
        today_fmt.setBackground(QColor("#7c3aed"))
        today_fmt.setFontWeight(QFont.Weight.DemiBold)
        self.calendar.setDateTextFormat(today, today_fmt)
        self._formatted_dates.append(today)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._accept_no_due()
            event.accept()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept_qdate(self.calendar.selectedDate())
            event.accept()
            return

        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.calendar.setFocus()

    def selected_date(self) -> str | None:
        return self._selected_due

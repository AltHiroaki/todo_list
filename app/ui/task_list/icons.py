"""Icon builders for task list controls."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


def build_refresh_icon(size: int = 16, color: str = "#a78bfa") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    arc_rect = QRectF(2.0, 2.0, size - 4.0, size - 4.0)
    painter.drawArc(arc_rect, 38 * 16, 280 * 16)

    head = QPolygonF(
        [
            QPointF(size - 2.6, size * 0.46),
            QPointF(size - 6.1, size * 0.34),
            QPointF(size - 4.4, size * 0.68),
        ]
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPolygon(head)
    painter.end()

    return QIcon(pixmap)


def build_calendar_icon(size: int = 16, color: str = "#a78bfa") -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    body = QRectF(2.2, 3.0, size - 4.4, size - 5.0)
    painter.drawRoundedRect(body, 2.6, 2.6)
    painter.drawLine(QPointF(2.4, 6.4), QPointF(size - 2.4, 6.4))

    painter.drawLine(QPointF(5.0, 1.8), QPointF(5.0, 4.6))
    painter.drawLine(QPointF(size - 5.0, 1.8), QPointF(size - 5.0, 4.6))

    dot_pen = QPen(QColor(color))
    dot_pen.setWidthF(1.9)
    dot_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(dot_pen)
    dots = [
        QPointF(5.3, 9.2),
        QPointF(8.0, 9.2),
        QPointF(10.7, 9.2),
        QPointF(5.3, 11.6),
        QPointF(8.0, 11.6),
        QPointF(10.7, 11.6),
    ]
    for dot in dots:
        painter.drawPoint(dot)

    painter.end()
    return QIcon(pixmap)

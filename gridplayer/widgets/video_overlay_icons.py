import math

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen


def draw_volume_on(rect, painter, color_fg, color_bg):
    draw_volume_off(rect, painter, color_fg, color_bg)

    painter.fillRect(
        rect.x() + 5 + 6 + 3, rect.y() + 6, 4, rect.height() - 12, color_fg
    )


def draw_volume_off(rect, painter, color_fg, color_bg):
    painter.setRenderHint(QPainter.Antialiasing, True)

    path = QPainterPath()

    path.moveTo(rect.x() + 5, round(rect.height() / 2) - 3)

    path.lineTo(rect.x() + 5 + 3, round(rect.height() / 2) - 3)
    path.lineTo(rect.x() + 5 + 6, 4)
    path.lineTo(rect.x() + 5 + 6, rect.height() - 4)
    path.lineTo(rect.x() + 5 + 3, round(rect.height() / 2) + 3)
    path.lineTo(rect.x() + 5, round(rect.height() / 2) + 3)

    path.lineTo(rect.x() + 5, round(rect.height() / 2) - 3)

    painter.setPen(Qt.NoPen)
    painter.fillPath(path, QBrush(color_fg))


def draw_play(rect, painter, color_fg, color_bg):
    painter.setRenderHint(QPainter.Antialiasing, True)

    path = QPainterPath()

    path.moveTo(rect.x() + 5, rect.y() + 4)
    path.lineTo(rect.width() - 5, round(rect.height() / 2))
    path.lineTo(rect.x() + 5, rect.height() - 4)
    path.lineTo(rect.x() + 5, rect.y() + 4)

    painter.setPen(Qt.NoPen)
    painter.fillPath(path, QBrush(color_fg))


def draw_pause(rect, painter, color_fg, color_bg):
    painter.fillRect(rect.x() + 5, rect.y() + 4, 5, rect.height() - 8, color_fg)
    painter.fillRect(rect.width() - 5 - 5, rect.y() + 4, 5, rect.height() - 8, color_fg)


def draw_cross(rect, painter, color_fg, color_bg):
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(color_fg, 4))

    line_len = round(math.sqrt((rect.width() - 10) ** 2 + (rect.width() - 10) ** 2))

    painter.drawLine(
        rect.x() + 5,
        rect.y() + 5,
        rect.x() + line_len,
        rect.y() + line_len,
    )
    painter.drawLine(
        rect.x() + line_len,
        rect.y() + 5,
        rect.x() + 5,
        rect.y() + line_len,
    )


def draw_spin_circle(
    rect: QRect, painter: QPainter, color_fg: QColor, color_bg: QColor, spin: int
):
    painter.setRenderHint(QPainter.Antialiasing, True)

    rect_spin = rect.adjusted(5, 5, -5, -5)

    painter.setPen(QPen(color_fg, 4))
    painter.drawArc(rect_spin, 0, 16 * 360)

    painter.setPen(QPen(color_bg, 2))
    painter.drawArc(rect_spin, -spin * 16, 16 * 90)


def _skip_arrow(painter, x, rect, width, color_fg):
    path = QPainterPath()
    path.moveTo(x, rect.y() + 5)
    path.lineTo(x + width, round(rect.height() / 2))
    path.lineTo(x, rect.height() - 5)
    path.lineTo(x, rect.y() + 5)
    painter.fillPath(path, QBrush(color_fg))


def draw_skip(rect, painter, color_fg, color_bg):
    """Next: a triangle running into a bar."""

    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)

    bar_width = 3
    bar_x = rect.width() - 5 - bar_width
    _skip_arrow(painter, rect.x() + 5, rect, bar_x - 1 - (rect.x() + 5), color_fg)
    painter.fillRect(bar_x, rect.y() + 5, bar_width, rect.height() - 10, color_fg)


def draw_skip_all(rect, painter, color_fg, color_bg):
    """Next for every cell: two triangles running into a bar."""

    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)

    bar_width = 3
    bar_x = rect.width() - 4 - bar_width
    left = rect.x() + 3
    arrow = (bar_x - 1 - left) / 2
    _skip_arrow(painter, left, rect, arrow, color_fg)
    _skip_arrow(painter, left + arrow, rect, arrow, color_fg)
    painter.fillRect(bar_x, rect.y() + 5, bar_width, rect.height() - 10, color_fg)

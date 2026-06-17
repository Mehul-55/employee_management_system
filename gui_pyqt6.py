"""
Employee Management System - Full UI
Rewritten in PyQt6 from CustomTkinter
Install: pip install PyQt6
"""

import sys
from datetime import datetime as _dt

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QSizePolicy, QStackedWidget, QMessageBox, QTextEdit, QComboBox,
    QDialog, QCalendarWidget, QDateEdit,
    QFileDialog, QGraphicsOpacityEffect, QCheckBox, QStyle, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer, QPoint, QSize, QRect, QLineF,
    pyqtSignal, QParallelAnimationGroup, QDate
)
from PyQt6.QtGui import QFont, QColor, QPalette, QCursor, QIcon, QPainter, QPen, QPainterPath, QPixmap

import attendance
from app_time import today_iso as _app_today_iso
from audit_log import log_action, get_recent_logs

# Color Palette
BG        = "#f5f0e8"
BG2       = "#ede8df"
BG3       = "#faf7f2"
SIDEBAR   = "#faf7f2"
BORDER    = "#d9d0c0"
TEXT      = "#1c1917"
TEXT2     = "#78716c"
TEXT3     = "#a8a29e"
ACCENT    = "#1f2937"
DANGER    = "#dc2626"
SUCCESS   = "#16a34a"
ENTRY_BG  = "#faf7f2"
COMBO_BG  = "#ffffff"
COMBO_POPUP_BG = "#fffdfa"


def combo_box_style(font_size=14, padding="0 12px"):
    return f"""
        QComboBox {{
            background: {COMBO_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: {padding};
            font-size: {font_size}px;
        }}
        QComboBox:hover {{
            border: 1px solid {ACCENT};
        }}
        QComboBox:focus {{
            border: 1.5px solid {ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            background: {COMBO_POPUP_BG};
            color: {TEXT};
            border: 1px solid {ACCENT};
            outline: 0;
            selection-background-color: {ACCENT};
            selection-color: #ffffff;
            padding: 4px;
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 28px;
            padding: 6px 10px;
        }}
    """


def desktop_work_area(widget=None):
    """Returns Qt's DPI-aware usable desktop area, with a small taskbar gap."""
    screen = None
    if widget is not None and widget.windowHandle():
        screen = widget.windowHandle().screen()
    screen = screen or QApplication.primaryScreen()
    area = screen.availableGeometry()
    return QRect(area.x(), area.y(), area.width(), max(area.height() - 8, 580))


def popup_stylesheet():
    return f"""
        QDialog, QMessageBox, QInputDialog, QFileDialog {{
            background-color: {BG3};
            color: {TEXT};
        }}
        QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel, QFileDialog QLabel {{
            color: {TEXT};
            background: transparent;
            font-size: 13px;
            font-weight: 600;
        }}
        QMessageBox QLabel#qt_msgbox_label {{
            color: {TEXT};
            font-size: 13px;
            font-weight: 600;
        }}
        QMessageBox QLabel#qt_msgboxex_icon_label {{
            background: transparent;
        }}
        QDialog QTextEdit, QDialog QPlainTextEdit, QDialog QLineEdit,
        QMessageBox QTextEdit, QMessageBox QPlainTextEdit, QMessageBox QLineEdit,
        QInputDialog QTextEdit, QInputDialog QPlainTextEdit, QInputDialog QLineEdit,
        QFileDialog QTextEdit, QFileDialog QPlainTextEdit, QFileDialog QLineEdit {{
            background: {ENTRY_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 6px 8px;
            selection-background-color: {ACCENT};
            selection-color: #ffffff;
        }}
        QDialog QComboBox, QInputDialog QComboBox, QFileDialog QComboBox {{
            background: {COMBO_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 4px 8px;
        }}
        QDialog QComboBox QAbstractItemView, QInputDialog QComboBox QAbstractItemView, QFileDialog QComboBox QAbstractItemView {{
            background: {COMBO_POPUP_BG};
            color: {TEXT};
            border: 1px solid {ACCENT};
            selection-background-color: {ACCENT};
            selection-color: #ffffff;
        }}
        QFileDialog QListView, QFileDialog QTreeView {{
            background: {ENTRY_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            selection-background-color: {ACCENT};
            selection-color: #ffffff;
        }}
        QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton, QFileDialog QPushButton,
        QDialogButtonBox QPushButton, QMessageBox QDialogButtonBox QPushButton {{
            background-color: {ACCENT};
            color: #ffffff;
            border: 1px solid {ACCENT};
            border-radius: 6px;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 800;
            min-width: 78px;
            min-height: 28px;
        }}
        QDialog QPushButton:hover, QMessageBox QPushButton:hover,
        QInputDialog QPushButton:hover, QFileDialog QPushButton:hover,
        QDialogButtonBox QPushButton:hover, QMessageBox QDialogButtonBox QPushButton:hover {{
            background-color: #374151;
            border: 1px solid #374151;
            color: #ffffff;
        }}
        QDialog QPushButton:pressed, QMessageBox QPushButton:pressed,
        QInputDialog QPushButton:pressed, QFileDialog QPushButton:pressed,
        QDialogButtonBox QPushButton:pressed, QMessageBox QDialogButtonBox QPushButton:pressed {{
            background-color: #111827;
            border: 1px solid #111827;
            color: #ffffff;
        }}
        QDialog QPushButton:disabled, QMessageBox QPushButton:disabled,
        QInputDialog QPushButton:disabled, QFileDialog QPushButton:disabled,
        QDialogButtonBox QPushButton:disabled, QMessageBox QDialogButtonBox QPushButton:disabled {{
            background-color: {BORDER};
            border: 1px solid {BORDER};
            color: {TEXT3};
        }}
    """

def confirm_popup(parent, title, message):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Icon.Question)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    box.setStyleSheet(popup_stylesheet())

    for button in box.buttons():
        button.setMinimumSize(90, 34)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #ffffff;
                border: 1px solid {ACCENT};
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: #374151;
                border-color: #374151;
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #111827;
                border-color: #111827;
                color: #ffffff;
            }}
        """)

    return box.exec() == QMessageBox.StandardButton.Yes

# ----------------------------------------------------------------------
#  STYLE HELPERS
# ----------------------------------------------------------------------
def styled(widget, css):
    widget.setStyleSheet(css)
    return widget

def make_label(text, size=13, color=TEXT, bold=False):
    lbl = QLabel(text)
    weight = "700" if bold else "400"
    lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {weight}; background: transparent; border: none;")
    return lbl

def display_department(user):
    return str(user.get("department") or "N/A").strip() or "N/A"

def make_entry(placeholder, password=False, width=None):
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    if password:
        e.setEchoMode(QLineEdit.EchoMode.Password)
    if width:
        e.setFixedWidth(width)
    e.setMinimumHeight(42)
    e.setStyleSheet(f"""
        QLineEdit {{
            background: {ENTRY_BG};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 0 12px;
            font-size: 15px;
            color: {TEXT};
        }}
        QLineEdit:focus {{
            border: 1.5px solid {ACCENT};
        }}
    """)
    return e

def make_button(text, color=ACCENT, text_color="#ffffff", hover=None, danger=False, height=42):
    btn = QPushButton(text)
    bg    = DANGER if danger else color
    hov   = hover or ("#b91c1c" if danger else "#374151")
    btn.setMinimumHeight(height)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {text_color};
            border: none;
            border-radius: 6px;
            font-size: 15px;
            font-weight: 700;
            padding: 0 16px;
        }}
        QPushButton:hover {{
            background: {hov};
        }}
        QPushButton:pressed {{
            background: {ACCENT};
        }}
    """)
    return btn


def short_text(value, limit=42):
    value = str(value or "")
    return value if len(value) <= limit else value[:limit - 3] + "..."


def show_text_popup(parent, title, heading, text):
    dlg = QDialog(parent)
    dlg.setModal(True)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(520, 320)
    dlg.setStyleSheet(popup_stylesheet())

    dlay = QVBoxLayout(dlg)
    dlay.setContentsMargins(18, 18, 18, 18)
    dlay.setSpacing(10)
    dlay.addWidget(make_label(heading, 16, TEXT, bold=True))

    text_box = QTextEdit()
    text_box.setReadOnly(True)
    text_box.setPlainText(str(text or ""))
    text_box.setStyleSheet(f"""
        QTextEdit {{
            background: {ENTRY_BG};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 10px;
            font-size: 13px;
            line-height: 1.4;
        }}
    """)
    dlay.addWidget(text_box)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    close_btn = make_button("Close", height=34)
    close_btn.setFixedWidth(90)
    close_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(close_btn)
    dlay.addLayout(btn_row)
    dlg.exec()


def make_detail_button(parent, title, heading, text, tooltip="View details"):
    btn = QPushButton("View")
    btn.setFixedSize(62, 28)
    btn.setToolTip(tooltip)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {BG3};
            color: {ACCENT};
            border: 1px solid {BORDER};
            border-radius: 5px;
            font-size: 12px;
            font-weight: 800;
        }}
        QPushButton:hover {{ background: {BG}; }}
    """)
    btn.clicked.connect(lambda: show_text_popup(parent, title, heading, text))
    return btn


def make_calendar_button(height=42, width=42, tooltip="Pick date"):
    btn = QPushButton()
    btn.setFixedSize(width, height)
    btn.setToolTip(tooltip)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setIcon(make_calendar_icon(TEXT))
    btn.setIconSize(QSize(22, 22))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {BG3};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 0;
        }}
        QPushButton:hover {{
            background: {BG2};
        }}
    """)
    return btn


def display_date(value):
    """User-facing date format: DD/MM/YY. Backend storage remains YYYY-MM-DD."""
    raw = str(value or "").strip()
    if not raw or raw in {"-", "—", "N/A", "None"}:
        return raw or "-"
    for fmt in ("%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return _dt.strptime(raw[:10], fmt).strftime("%d/%m/%y")
        except ValueError:
            pass
    return raw


def parse_display_date(value):
    """Accept DD/MM/YY from the UI and return YYYY-MM-DD for backend queries."""
    raw = str(value or "").strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return _dt.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("Date must be in DD/MM/YY format.")


def qdate_display(qdate):
    return qdate.toString("dd/MM/yy")


def qdate_iso(qdate):
    return qdate.toString("yyyy-MM-dd")


def qdate_from_display(value):
    try:
        return QDate.fromString(parse_display_date(value), "yyyy-MM-dd")
    except ValueError:
        return QDate()


def make_calendar_icon(color=TEXT, size=28):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)

    pen = QPen(QColor(color), 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    painter.drawLine(21, 10, 3, 10)
    painter.drawLine(16, 2, 16, 6)
    painter.drawLine(8, 2, 8, 6)

    path = QPainterPath()
    path.moveTo(7.8, 22)
    path.lineTo(16.2, 22)
    path.cubicTo(17.8802, 22, 18.7202, 22, 19.362, 21.673)
    path.cubicTo(19.9265, 21.3854, 20.3854, 20.9265, 20.673, 20.362)
    path.cubicTo(21, 19.7202, 21, 18.8802, 21, 17.2)
    path.lineTo(21, 8.8)
    path.cubicTo(21, 7.11984, 21, 6.27976, 20.673, 5.63803)
    path.cubicTo(20.3854, 5.07354, 19.9265, 4.6146, 19.362, 4.32698)
    path.cubicTo(18.7202, 4, 17.8802, 4, 16.2, 4)
    path.lineTo(7.8, 4)
    path.cubicTo(6.11984, 4, 5.27976, 4, 4.63803, 4.32698)
    path.cubicTo(4.07354, 4.6146, 3.6146, 5.07354, 3.32698, 5.63803)
    path.cubicTo(3, 6.27976, 3, 7.11984, 3, 8.8)
    path.lineTo(3, 17.2)
    path.cubicTo(3, 18.8802, 3, 19.7202, 3.32698, 20.362)
    path.cubicTo(3.6146, 20.9265, 4.07354, 21.3854, 4.63803, 21.673)
    path.cubicTo(5.27976, 22, 6.11984, 22, 7.8, 22)
    painter.drawPath(path)

    painter.end()
    return QIcon(pix)


def make_shift_management_icon(color=TEXT, accent=ACCENT, size=28):
    """Calendar with a clock, used for Shift Management."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 28, size / 28)

    outline = QPen(QColor(color), 1.8)
    outline.setCapStyle(Qt.PenCapStyle.RoundCap)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(outline)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(3, 5, 20, 18, 2, 2)
    painter.drawLine(3, 10, 23, 10)
    painter.drawLine(8, 3, 8, 7)
    painter.drawLine(18, 3, 18, 7)

    painter.setPen(QPen(QColor(accent), 1.8))
    painter.setBrush(QColor(BG3))
    painter.drawEllipse(13, 13, 12, 12)
    painter.drawLine(19, 16, 19, 19)
    painter.drawLine(QLineF(19, 19, 22, 20.5))

    painter.end()
    return QIcon(pix)


def make_salary_report_icon(color=TEXT, accent=ACCENT, size=28):
    """Salary report document matching the approved folded-corner reference."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 28, size / 28)

    navy = QColor("#0b315f")
    teal = QColor("#12aaa5")
    blue = QColor("#2878db")

    outline = QPen(navy, 2.0)
    outline.setCapStyle(Qt.PenCapStyle.RoundCap)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(outline)
    painter.setBrush(QColor("#ffffff"))

    document = QPainterPath()
    document.moveTo(5, 2)
    document.lineTo(18, 2)
    document.lineTo(24, 8)
    document.lineTo(24, 25)
    document.quadTo(24, 26, 23, 26)
    document.lineTo(6, 26)
    document.quadTo(4, 26, 4, 24)
    document.lineTo(4, 4)
    document.quadTo(4, 2, 5, 2)
    document.closeSubpath()
    painter.drawPath(document)

    fold = QPainterPath()
    fold.moveTo(18, 2)
    fold.lineTo(18, 8)
    fold.quadTo(18, 9, 19, 9)
    fold.lineTo(24, 9)
    fold.closeSubpath()
    painter.setPen(outline)
    painter.setBrush(blue)
    painter.drawPath(fold)

    painter.setPen(QPen(teal, 1.5))
    rupee_font = QFont("Segoe UI Symbol", 13)
    rupee_font.setBold(True)
    painter.setFont(rupee_font)
    painter.drawText(QRect(6, 6, 11, 12), Qt.AlignmentFlag.AlignCenter, "₹")

    lines_pen = QPen(blue, 2.0)
    lines_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(lines_pen)
    painter.drawLine(8, 20, 21, 20)
    painter.drawLine(8, 24, 20, 24)

    painter.end()
    return QIcon(pix)


def make_feature_icon(key, style, standard_icon_name):
    if key == "shift_management":
        return make_shift_management_icon()
    if key == "salary_report":
        return make_salary_report_icon()
    standard_icon = getattr(
        QStyle.StandardPixmap,
        standard_icon_name,
        QStyle.StandardPixmap.SP_FileIcon,
    )
    return style.standardIcon(standard_icon)


def divider():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {BORDER}; background: {BORDER}; max-height: 1px;")
    return line

def card_frame(radius=10):
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {BG3};
            border: 1px solid {BORDER};
            border-radius: {radius}px;
        }}
    """)
    return f


# ----------------------------------------------------------------------
#  FADE ANIMATION HELPER  (used for login - dashboard transition)
# ----------------------------------------------------------------------
def fade_in(widget, duration=280):
    def _start():
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        widget._fade_anim = anim
    QTimer.singleShot(0, _start)


# ----------------------------------------------------------------------
#  SLIDING STACKED WIDGET - smooth slide+fade between pages
# ----------------------------------------------------------------------
class SlidingStack(QStackedWidget):
    """
    Replaces QStackedWidget with a slide-from-right + simultaneous fade.
    Duration: 320ms, OutQuint easing a fast start, smooth deceleration.
    """
    DURATION = 320
    EASING   = QEasingCurve.Type.OutQuint

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animating = False

    def slide_to(self, new_widget):
        if self._animating:
            return
        old_widget = self.currentWidget()
        if old_widget is new_widget:
            return

        # Make sure new widget is in the stack
        if self.indexOf(new_widget) == -1:
            self.addWidget(new_widget)

        w = self.width()
        h = self.height()

        # Position new widget just off-screen to the right
        new_widget.setGeometry(w, 0, w, h)
        new_widget.show()
        new_widget.raise_()

        self._animating = True
        group = QParallelAnimationGroup(self)

        # Slide old widget out to the left
        anim_old_pos = QPropertyAnimation(old_widget, b"geometry")
        anim_old_pos.setDuration(self.DURATION)
        anim_old_pos.setStartValue(QRect(0, 0, w, h))
        anim_old_pos.setEndValue(QRect(-w // 3, 0, w, h))
        anim_old_pos.setEasingCurve(self.EASING)

        # Fade out old widget
        old_effect = QGraphicsOpacityEffect(old_widget)
        old_widget.setGraphicsEffect(old_effect)
        anim_old_fade = QPropertyAnimation(old_effect, b"opacity")
        anim_old_fade.setDuration(self.DURATION)
        anim_old_fade.setStartValue(1.0)
        anim_old_fade.setEndValue(0.0)
        anim_old_fade.setEasingCurve(self.EASING)

        # Slide new widget in from the right
        anim_new_pos = QPropertyAnimation(new_widget, b"geometry")
        anim_new_pos.setDuration(self.DURATION)
        anim_new_pos.setStartValue(QRect(w, 0, w, h))
        anim_new_pos.setEndValue(QRect(0, 0, w, h))
        anim_new_pos.setEasingCurve(self.EASING)

        # Fade in new widget
        new_effect = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(new_effect)
        anim_new_fade = QPropertyAnimation(new_effect, b"opacity")
        anim_new_fade.setDuration(self.DURATION)
        anim_new_fade.setStartValue(0.0)
        anim_new_fade.setEndValue(1.0)
        anim_new_fade.setEasingCurve(self.EASING)

        group.addAnimation(anim_old_pos)
        group.addAnimation(anim_old_fade)
        group.addAnimation(anim_new_pos)
        group.addAnimation(anim_new_fade)

        def on_finished():
            self._animating = False
            self.setCurrentWidget(new_widget)
            old_widget.setGraphicsEffect(None)
            new_widget.setGraphicsEffect(None)
            # Reset geometry using current size so resize during animation is handled correctly
            new_widget.setGeometry(self.rect())

        group.finished.connect(on_finished)
        group.start()
        self._anim_group = group  # prevent GC


# ----------------------------------------------------------------------
#  TOAST NOTIFICATION
# ----------------------------------------------------------------------
class Toast(QLabel):
    def __init__(self, parent, message, success=True):
        super().__init__(message, parent)
        bg = SUCCESS if success else DANGER
        self.setStyleSheet(f"""
            background: {bg};
            color: white;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 700;
            padding: 8px 20px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adjustSize()
        self.setMinimumWidth(260)
        self.raise_()
        self._reposition(parent)
        fade_in(self, 180)
        QTimer.singleShot(2500, self.deleteLater)

    def _reposition(self, parent):
        parent.resizeEvent = self._make_resize(parent, parent.resizeEvent if hasattr(parent, 'resizeEvent') else None)
        self._do_pos(parent)

    def _make_resize(self, parent, orig):
        def handler(e):
            if orig:
                orig(e)
            self._do_pos(parent)
        return handler

    def _do_pos(self, parent):
        pw, ph = parent.width(), parent.height()
        self.move((pw - self.width()) // 2, ph - self.height() - 20)


# ----------------------------------------------------------------------
#  CUSTOM TITLE BAR
# ----------------------------------------------------------------------
class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._window   = parent
        self._drag_pos = None
        self._maximized = False
        self._normal_geometry = None
        self.setFixedHeight(38)
        self.setStyleSheet(f"background: {BG3}; border-bottom: 1px solid {BORDER};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(0)

        title = QLabel("  Employee Management System")
        title.setStyleSheet(f"color: {TEXT3}; font-size: 14px; font-weight: 600; background: transparent;")
        lay.addWidget(title)
        lay.addStretch()

        for key, label, hover_color, slot in [
            ("min", "\u2212", BG2, self._minimize),
            ("max", "\u25a1", BG2, self._toggle_max),
            ("close", "\u00d7", "#fee2e2", self._close),
        ]:
            btn = QPushButton(label)
            btn.setFixedSize(38, 38)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT};
                    font-size: 18px;
                    font-weight: 800;
                    border: none;
                }}
                QPushButton:hover {{ background: {hover_color}; }}
            """)
            btn.clicked.connect(slot)
            lay.addWidget(btn)
            if key == "max":
                self._max_btn = btn

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self._maximized:
            self._drag_pos = e.globalPosition().toPoint() - self._window.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton and not self._maximized:
            self._window.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def _minimize(self):
        self._window.showMinimized()

    def maximize_to_screen(self):
        if self._maximized:
            return
        self._normal_geometry = self._window.geometry()
        self._window.setGeometry(desktop_work_area(self._window))
        self._max_btn.setText("\u2750")
        self._maximized = True

    def _toggle_max(self):
        if self._maximized:
            if self._normal_geometry is not None:
                self._window.setGeometry(self._normal_geometry)
            self._max_btn.setText("\u25a1")
        else:
            self._normal_geometry = self._window.geometry()
            screen = self._window.windowHandle().screen() if self._window.windowHandle() else QApplication.primaryScreen()
            self._window.setGeometry(screen.availableGeometry())
            self._max_btn.setText("\u2750")
        self._maximized = not self._maximized

    def _close(self):
        self._window.close()


# ----------------------------------------------------------------------
#  SIDEBAR
# ----------------------------------------------------------------------
class Sidebar(QWidget):
    def __init__(self, items, on_select, on_logout, panel_label="ADMIN PANEL"):
        super().__init__()
        self.setFixedWidth(200)
        self.setStyleSheet(f"background: {SIDEBAR};")
        self._buttons  = {}
        self._active   = None
        self._on_select = on_select

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Logo
        logo = QWidget()
        logo.setStyleSheet("background: transparent;")
        logo_lay = QVBoxLayout(logo)
        logo_lay.setContentsMargins(18, 20, 18, 14)
        logo_lay.setSpacing(2)
        logo_lay.addWidget(make_label("EMS", 20, TEXT, bold=True))
        logo_lay.addWidget(make_label(panel_label, 11, TEXT3))
        lay.addWidget(logo)
        lay.addWidget(divider())

        # Nav buttons
        nav = QWidget()
        nav.setStyleSheet("background: transparent;")
        nav_lay = QVBoxLayout(nav)
        nav_lay.setContentsMargins(8, 8, 8, 8)
        nav_lay.setSpacing(2)

        for key, icon, text in items:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setStyleSheet(self._nav_style(False))
            btn.clicked.connect(lambda checked, k=key: self._select(k))
            nav_lay.addWidget(btn)
            self._buttons[key] = btn

        lay.addWidget(nav)
        lay.addStretch()
        lay.addWidget(divider())

        logout_btn = QPushButton("Logout")
        logout_btn.setMinimumHeight(40)
        logout_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {DANGER};
                font-size: 15px;
                font-weight: 600;
                text-align: left;
                padding-left: 12px;
                border: none;
                border-radius: 6px;
                margin: 4px 8px 8px 8px;
            }}
            QPushButton:hover {{ background: #fde8e8; }}
        """)
        logout_btn.clicked.connect(on_logout)
        lay.addWidget(logout_btn)

    def _nav_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background: #f0e8d5;
                    color: {ACCENT};
                    font-size: 15px;
                    font-weight: 700;
                    text-align: left;
                    padding-left: 12px;
                    border: none;
                    border-radius: 6px;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent;
                color: {TEXT2};
                font-size: 15px;
                font-weight: 500;
                text-align: left;
                padding-left: 12px;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: #d6cfc4; }}
        """

    def _select(self, key):
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setStyleSheet(self._nav_style(False))
        self._active = key
        self._buttons[key].setStyleSheet(self._nav_style(True))
        self._on_select(key)

    def select(self, key):
        self._select(key)


# ----------------------------------------------------------------------
#  LOGIN SCREEN - Redesigned: dark left panel + clean right form
# ----------------------------------------------------------------------

# Login-specific palette (isolated so it doesn't bleed into dashboards)
LGN_DARK      = "#0f1117"   # deep charcoal a left panel bg
LGN_DARK2     = "#1a1d27"   # slightly lighter a card / stripe
LGN_GOLD      = "#c9a84c"   # warm gold accent
LGN_GOLD2     = "#e8c97a"   # lighter gold for hover
LGN_TEXT      = "#f0ece4"   # off-white body text
LGN_TEXT2     = "#8a8693"   # muted secondary
LGN_BORDER    = "#2e3140"   # subtle dark border
LGN_ENTRY     = "#1e2130"   # input field background
LGN_RIGHT     = "#f7f3ed"   # right panel a warm paper
LGN_RIGHT2    = "#ede8df"   # right panel field bg
LGN_R_TEXT    = "#1a1714"   # right panel main text
LGN_R_TEXT2   = "#7a7068"   # right panel muted
LGN_R_BORDER  = "#d4c9b8"   # right panel border
LGN_R_ACCENT  = "#0f1117"   # right panel button bg
LGN_R_ENTRY   = "#faf7f2"   # right panel entry bg


class LoginScreen(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._mode = "admin"
        self._build()
        fade_in(self)

    # helpers scoped to login
    @staticmethod
    def _login_entry(placeholder, password=False):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        if password:
            e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setMinimumHeight(46)
        e.setStyleSheet(f"""
            QLineEdit {{
                background: {LGN_R_ENTRY};
                border: 1.5px solid {LGN_R_BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: {LGN_R_TEXT};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {LGN_R_ACCENT};
                background: #ffffff;
            }}
            QLineEdit::placeholder {{
                color: {LGN_R_TEXT2};
            }}
        """)
        return e

    @staticmethod
    def _field_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {LGN_R_TEXT2};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            background: transparent;
            border: none;
        """)
        return lbl

    # build
    def _build(self):
        self.setStyleSheet(f"background: {LGN_DARK};")
        root_lay = QHBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        root_lay.addWidget(self._build_left(),  stretch=5)
        root_lay.addWidget(self._build_right(), stretch=6)

    # LEFT PANEL - EMS brand block
    def _build_left(self):
        left = QWidget()
        left.setStyleSheet(f"""
            QWidget {{
                background: {SIDEBAR};
            }}
        """)

        lay = QVBoxLayout(left)
        lay.setContentsMargins(48, 48, 48, 48)
        lay.setSpacing(0)

        lay.addStretch()

        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(0)
        center_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_frame = QFrame()
        icon_frame.setFixedSize(72, 72)
        icon_frame.setStyleSheet(f"""
            QFrame {{
                background: {BG3};
                border: 1px solid {BORDER};
                border-radius: 36px;
            }}
        """)
        icon_lay = QVBoxLayout(icon_frame)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        people_icon = QLabel("👥")
        people_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        people_icon.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                font-size: 34px;
            }
        """)
        icon_lay.addWidget(people_icon)
        center_lay.addWidget(icon_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        center_lay.addSpacing(18)

        title = QLabel("EMPLOYEE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 22px;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        center_lay.addWidget(title)

        subtitle = QLabel("MANAGEMENT SYSTEM")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 13px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        center_lay.addWidget(subtitle)

        line = QFrame()
        line.setFixedSize(28, 1)
        line.setStyleSheet(f"background: {BORDER}; border: none;")
        center_lay.addWidget(line, alignment=Qt.AlignmentFlag.AlignCenter)
        center_lay.addSpacing(16)

        tagline = QLabel("Track. Manage. Succeed.")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 14px;
            font-weight: 400;
            background: transparent;
            border: none;
        """)
        center_lay.addWidget(tagline)

        lay.addWidget(center)
        lay.addStretch()
        return left

    # RIGHT PANEL - clean form
    def _build_right(self):
        right = QWidget()
        right.setStyleSheet(f"background: {LGN_RIGHT};")

        outer = QVBoxLayout(right)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setFixedWidth(400)
        card.setStyleSheet("background: transparent;")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # Header
        card_lay.addWidget(self._r_label("Welcome back", 24, LGN_R_TEXT, bold=True))
        card_lay.addSpacing(4)
        card_lay.addWidget(self._r_label("Sign in to your account to continue", 13, LGN_R_TEXT2))
        card_lay.addSpacing(28)

        # Role toggle
        toggle_wrap = QWidget()
        toggle_wrap.setFixedHeight(44)
        toggle_wrap.setStyleSheet(f"""
            background: {LGN_RIGHT2};
            border: 1.5px solid {LGN_R_BORDER};
            border-radius: 10px;
        """)
        tl = QHBoxLayout(toggle_wrap)
        tl.setContentsMargins(4, 4, 4, 4)
        tl.setSpacing(4)

        self._admin_btn = QPushButton("Admin")
        self._emp_btn   = QPushButton("Employee")
        for btn in (self._admin_btn, self._emp_btn):
            btn.setMinimumHeight(34)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("")
        self._admin_btn.clicked.connect(lambda: self._set_mode("admin"))
        self._emp_btn.clicked.connect(lambda:   self._set_mode("employee"))
        tl.addWidget(self._admin_btn)
        tl.addWidget(self._emp_btn)
        card_lay.addWidget(toggle_wrap)
        card_lay.addSpacing(22)

        self._set_mode("admin")

        # Username field
        card_lay.addWidget(self._field_label("USERNAME / EMPLOYEE ID"))
        card_lay.addSpacing(6)
        self._user_entry = self._login_entry("Enter your username or ID")
        self._user_entry.returnPressed.connect(self._do_login)
        card_lay.addWidget(self._user_entry)
        card_lay.addSpacing(14)

        # Password field
        card_lay.addWidget(self._field_label("PASSWORD"))
        card_lay.addSpacing(6)
        self._pass_entry = self._login_entry("Enter your password", password=True)
        self._pass_entry.returnPressed.connect(self._do_login)
        card_lay.addWidget(self._pass_entry)
        card_lay.addSpacing(22)

        # Login button
        login_btn = QPushButton("SIGN IN")
        login_btn.setMinimumHeight(48)
        login_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        login_btn.setStyleSheet(f"""
            QPushButton {{
                background: {LGN_R_ACCENT};
                color: #f0ece4;
                border: none;
                border-radius: 9px;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }}
            QPushButton:hover {{
                background: #2c3347;
            }}
            QPushButton:pressed {{
                background: #060810;
            }}
        """)
        login_btn.clicked.connect(self._do_login)
        card_lay.addWidget(login_btn)
        card_lay.addSpacing(16)

        # Divider
        div = QHBoxLayout()
        for side in [0, 1]:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(f"color: {LGN_R_BORDER};")
            div.addWidget(line)
            if side == 0:
                mid = QLabel("  secure login  ")
                mid.setStyleSheet(f"color: {LGN_R_TEXT2}; font-size: 11px; letter-spacing: 0.5px; background: transparent; border: none;")
                div.addWidget(mid)
        card_lay.addLayout(div)
        card_lay.addSpacing(14)

        # Security badge row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        badge_row.addStretch()
        for icon, txt in [("Lock", "Encrypted"), ("Shield", "Protected")]:
            pill = QWidget()
            pill.setStyleSheet(f"""
                background: {LGN_RIGHT2};
                border: 1px solid {LGN_R_BORDER};
                border-radius: 12px;
            """)
            pl = QHBoxLayout(pill)
            pl.setContentsMargins(10, 4, 12, 4)
            pl.setSpacing(4)
            ic = QLabel(icon)
            ic.setStyleSheet("background: transparent; border: none; font-size: 12px;")
            tx = QLabel(txt)
            tx.setStyleSheet(f"color: {LGN_R_TEXT2}; font-size: 11px; background: transparent; border: none;")
            pl.addWidget(ic); pl.addWidget(tx)
            badge_row.addWidget(pill)
        badge_row.addStretch()
        card_lay.addLayout(badge_row)

        # Error label
        self._err_label = QLabel("")
        self._err_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err_label.setStyleSheet(f"""
            color: {DANGER};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        card_lay.addSpacing(10)
        card_lay.addWidget(self._err_label)

        outer.addWidget(card)
        return right

    @staticmethod
    def _r_label(text, size=13, color=LGN_R_TEXT, bold=False):
        lbl = QLabel(text)
        w = "700" if bold else "400"
        lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {w}; background: transparent; border: none;")
        return lbl

    # mode toggle
    def _set_mode(self, mode):
        self._mode = mode
        active = f"""
            QPushButton {{
                background: {LGN_R_ACCENT};
                color: #f0ece4;
                border-radius: 7px;
                font-size: 13px;
                font-weight: 700;
                border: none;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{ background: #2c3347; }}
        """
        inactive = f"""
            QPushButton {{
                background: transparent;
                color: {LGN_R_TEXT2};
                border-radius: 7px;
                font-size: 13px;
                font-weight: 500;
                border: none;
            }}
            QPushButton:hover {{ background: {LGN_R_BORDER}; }}
        """
        self._admin_btn.setStyleSheet(active if mode == "admin" else inactive)
        self._emp_btn.setStyleSheet(active if mode == "employee" else inactive)

    # submit
    def _do_login(self):
        user = self._user_entry.text().strip()
        pw   = self._pass_entry.text().strip()
        if not user or not pw:
            self._err_label.setText("Please fill in all fields.")
            return
        self._err_label.setText("")
        self.controller.handle_login(self._mode, user, pw, self._err_label)


# ----------------------------------------------------------------------
#  SCROLL AREA HELPER
# ----------------------------------------------------------------------
def make_scroll(inner_widget):
    class LockedScrollArea(QScrollArea):
        def wheelEvent(self, event):
            super().wheelEvent(event)
            event.accept()

    scroll = LockedScrollArea()
    scroll.setWidget(inner_widget)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet(f"background: transparent; border: none;")
    inner_widget.setStyleSheet(f"background: transparent;")
    return scroll


def make_sticky_table_scroll(header_widget, rows_widget, rows_height=None, header_height=52):
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(container)
    lay.setContentsMargins(0,0,0,0)
    lay.setSpacing(6)

    header_scroll = make_scroll(header_widget)
    header_scroll.setFixedHeight(header_height)
    header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    rows_scroll = make_scroll(rows_widget)
    if rows_height:
        rows_scroll.setFixedHeight(rows_height)

    rows_scroll.horizontalScrollBar().valueChanged.connect(header_scroll.horizontalScrollBar().setValue)
    header_scroll.horizontalScrollBar().valueChanged.connect(rows_scroll.horizontalScrollBar().setValue)

    lay.addWidget(header_scroll)
    lay.addWidget(rows_scroll)
    return container, rows_scroll, header_scroll


# ----------------------------------------------------------------------
#  CONTENT PAGE BASE - handles fade-in
# ----------------------------------------------------------------------
class ContentPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {BG2};")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

    def page_header(self, title, subtitle=None):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 28, 28, 0)
        lay.setSpacing(4)
        lay.addWidget(make_label(title, 20, TEXT, bold=True))
        if subtitle:
            lay.addWidget(make_label(subtitle, 13, TEXT3))
        return w

    def stat_card(self, num, label_text, color=TEXT):
        card = card_frame(8)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        lay.addWidget(make_label(str(num), 30, color, bold=True), alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(make_label(label_text, 11, TEXT3),           alignment=Qt.AlignmentFlag.AlignCenter)
        return card


# ----------------------------------------------------------------------
#  ADMIN DASHBOARD
# ----------------------------------------------------------------------
class AdminDashboard(QWidget):
    # Shift ends after which all unmarked employees are auto-marked absent.
    # Each entry is (shift name, hour, minute) in 24-hour local time.
    _SHIFT_ENDS = [
        ("Night",   6,  0),
        ("Morning", 17, 0),
        ("Evening", 22, 0),
    ]

    def __init__(self, controller, username):
        super().__init__()
        self.controller = controller
        self.username   = username
        self.setStyleSheet(f"background: {BG};")
        self._build()
        self._absent_timers = []
        self._schedule_auto_absent()

    # ------------------------------------------------------------------
    #  AUTO ABSENT — fires once per shift end, catches up on startup
    # ------------------------------------------------------------------
    def _schedule_auto_absent(self):
        from datetime import datetime as _dt
        from datetime import timedelta
        now = _dt.now()

        for shift_name, hour, minute in self._SHIFT_ENDS:
            # Always catch up once on startup. The backend resumes from the
            # persisted per-shift checkpoint and processes every missed date.
            self._run_auto_absent(shift_name, catchup=True)

            shift_end = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if shift_end <= now:
                shift_end = shift_end + timedelta(days=1)

            ms_until = int((shift_end - now).total_seconds() * 1000)
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda s=shift_name, h=hour, m=minute: self._on_shift_end(s, h, m))
            timer.start(ms_until)
            self._absent_timers.append(timer)

    def _on_shift_end(self, shift_name, hour, minute):
        self._run_auto_absent(shift_name)
        # Reschedule for the same time tomorrow (86400 seconds).
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_shift_end(shift_name, hour, minute))
        timer.start(86_400_000)
        self._absent_timers.append(timer)

    def _run_auto_absent(self, shift_name=None, catchup=False):
        try:
            ok, marked = attendance.auto_mark_absent_for_today(shift_name)
        except Exception as exc:
            print(f"[AUTO ABSENT] Error: {exc}")
            return
        if ok and marked:
            log_action(
                "MARK_ATTENDANCE",
                "system",
                target=shift_name or "ALL",
                details=f"Auto-marked absent for {shift_name or 'completed shifts'} "
                        f"({'catch-up' if catchup else 'scheduled'}): {', '.join(marked)}.",
            )
            print(f"[AUTO ABSENT] Marked absent: {', '.join(marked)}")
        else:
            print(f"[AUTO ABSENT] No unmarked employees found.")

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._feature_items = [
            ("employees",        "SP_FileDialogDetailedView", "All Employees",     "All Employees"),
            ("add",              "SP_FileDialogNewFolder",    "Add Employee",      "Add Employee"),
            ("delete",           "SP_TrashIcon",              "Delete Employee",   "Delete Employee"),
            ("reset",            "SP_DialogResetButton",      "Reset Password",     "Reset Password"),
            ("attendance",       "SP_FileDialogListView",     "Attendance",         "Attendance"),
            ("leaves",           "SP_DialogApplyButton",      "Manage Leaves",      "Manage Leaves"),
            ("leave_requests",   "SP_MessageBoxInformation",  "Leave Requests",     "Leave Requests"),
            ("shift_management", "SP_DialogSaveButton",       "Shift Management",   "Shift Management"),
            ("salary_report",    "SP_DialogHelpButton",       "Salary Report",      "Salary Report"),
            ("monthly_attendance","SP_FileDialogContentsView", "Monthly Attendance", "Monthly Attendance"),
            ("daily_report",     "SP_FileIcon",               "Daily Report",       "Daily Report"),
        ]
        nav_items = [
            ("dashboard",        "aSz", "Dashboard"),
        ]
        self._sidebar = Sidebar(nav_items, self._show_page, self.controller.show_login, "ADMIN PANEL")
        lay.addWidget(self._sidebar)

        self._stack = SlidingStack()
        self._stack.setStyleSheet(f"background: {BG2};")
        lay.addWidget(self._stack)

        self._pages = {}
        self._sidebar.select("dashboard")

    def _show_page(self, key):
        # BUG FIX: always rebuild salary_report so updated basic salaries are never stale
        if key == "salary_report" and key in self._pages:
            old = self._pages.pop(key)
            self._stack.removeWidget(old)
            old.deleteLater()
        if key not in self._pages:
            page = self._build_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)
        self._stack.slide_to(self._pages[key])

    def _build_page(self, key):
        return {
            "dashboard":        self._page_dashboard,
            "employees":        self._page_employees,
            "add":              self._page_add,
            "delete":           self._page_delete,
            "reset":            self._page_reset,
            "attendance":       self._page_attendance,
            "leaves":           self._page_leaves,
            "leave_requests":   self._page_leave_requests,
            "shift_management": self._page_shift_management,
            "salary_report":    self._page_salary_report,
            "monthly_attendance": self._page_monthly_attendance_report,
            "daily_report":     self._page_daily_report,
        }[key]()

    def _refresh_page(self, key):
        """Rebuild and re-show a page (for after mutations)."""
        if key in self._pages:
            old = self._pages.pop(key)
            self._stack.removeWidget(old)
            old.deleteLater()
        self._show_page(key)  # will slide_to the new page

    # Dashboard
    def _page_dashboard(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        inner = QWidget(); inner.setStyleSheet("background: transparent;")
        il = QVBoxLayout(inner); il.setContentsMargins(28, 28, 28, 28); il.setSpacing(0)

        from datetime import date as _date

        emp = self.controller.get_all_employees()
        emp.sort(key=lambda u: int(u["id"]) if str(u["id"]).isdigit() else 0)
        today_str = _app_today_iso()
        active_count = sum(1 for u in emp if self.controller.account_exists(u["id"]))
        registered_today = sum(1 for u in emp if str(u.get("created_at", "")).startswith(today_str))

        il.addWidget(make_label("Dashboard", 20, TEXT, bold=True))
        il.addSpacing(4)
        il.addWidget(make_label(f"Welcome back, {self.username}", 13, TEXT3))
        il.addSpacing(16)
        il.addWidget(divider())
        il.addSpacing(16)

        # Stat cards
        stats_row = QHBoxLayout(); stats_row.setSpacing(10)

        def stat_card(num, lbl_text, color=TEXT):
            card = card_frame(8)
            cl = QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(4)
            cl.addWidget(make_label(str(num), 30, color, bold=True), alignment=Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(make_label(lbl_text, 11, TEXT3),             alignment=Qt.AlignmentFlag.AlignCenter)
            return card

        stats_row.addWidget(stat_card(len(emp),     "Total employees"))
        stats_row.addWidget(stat_card(active_count, "Active accounts", SUCCESS))
        stats_row.addWidget(stat_card(registered_today, "Registered today"))
        il.addLayout(stats_row)
        il.addSpacing(20)

        il.addWidget(make_label("Features", 14, TEXT, bold=True))
        il.addSpacing(10)

        feature_grid = QGridLayout()
        feature_grid.setHorizontalSpacing(10)
        feature_grid.setVerticalSpacing(10)

        def feature_button(key, icon_name, short_label, full_label):
            btn = QPushButton(short_label)
            btn.setMinimumHeight(64)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setIcon(make_feature_icon(key, self.style(), icon_name))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(full_label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG3};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 700;
                    text-align: left;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {BG};
                    border: 1px solid {ACCENT};
                }}
                QPushButton::icon {{
                    padding-left: 0px;
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._show_page(k))
            return btn

        for i, (key, icon_name, short_label, full_label) in enumerate(self._feature_items):
            feature_grid.addWidget(feature_button(key, icon_name, short_label, full_label), i // 3, i % 3)

        il.addLayout(feature_grid)
        il.addSpacing(24)

        # Recent employees
        il.addWidget(make_label("Recent employees", 14, TEXT, bold=True))
        il.addSpacing(10)
        il.addWidget(self._employee_table(emp[:6]))
        il.addSpacing(24)

        # ----------------------------------------------------------------------
        #  AUDIT LOG WIDGET
        # ----------------------------------------------------------------------
        il.addWidget(divider())
        il.addSpacing(16)
        il.addWidget(make_label("Audit Log", 14, TEXT, bold=True))
        il.addSpacing(8)

        # Toggle + Refresh control row
        self._audit_important_only = False
        ctrl_row = QWidget(); ctrl_row.setStyleSheet("background: transparent;")
        crl = QHBoxLayout(ctrl_row); crl.setContentsMargins(0,0,0,0); crl.setSpacing(8)

        toggle_btn = QPushButton("All Actions")
        toggle_btn.setFixedHeight(28)
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(False)
        toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        toggle_btn.setStyleSheet(self._audit_toggle_style(False))

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setFixedWidth(96)
        refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: {TEXT2}; border: 1px solid {BORDER};
                           border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 10px; }}
            QPushButton:hover {{ background: {BG}; }}
        """)
        crl.addWidget(toggle_btn)
        crl.addWidget(refresh_btn)
        crl.addStretch()
        il.addWidget(ctrl_row)
        il.addSpacing(8)

        # Column header bar
        AUDIT_COLS   = [("Timestamp", 150), ("Action", 150), ("Performed By", 130), ("Target", 190), ("Details", 360)]
        audit_table_width = sum(width for _, width in AUDIT_COLS) + 22
        col_hdr = QWidget(); col_hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        col_hdr.setMinimumWidth(audit_table_width)
        chl = QHBoxLayout(col_hdr); chl.setContentsMargins(8,6,8,6); chl.setSpacing(0)
        for col_name, width in AUDIT_COLS:
            lbl = make_label(col_name, 11, TEXT3, bold=True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(width)
            lbl.setFixedHeight(28)
            chl.addWidget(lbl)
        il.addWidget(col_hdr)
        il.addSpacing(4)

        # Scrollable rows area
        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_w.setMinimumWidth(audit_table_width)
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        audit_scroll = make_scroll(rows_w)
        audit_scroll.setFixedHeight(260)
        il.addWidget(audit_scroll)
        il.addSpacing(16)

        ACTION_COLORS = {
            "LOGIN":              "#1a73e8",
            "LOGOUT":             TEXT3,
            "ADD_EMPLOYEE":       SUCCESS,
            "UPDATE_EMPLOYEE":    "#f0a500",
            "DELETE_EMPLOYEE":    DANGER,
            "MARK_ATTENDANCE":    SUCCESS,
            "UPDATE_ATTENDANCE":  "#f0a500",
            "DELETE_ATTENDANCE":  "#e65100",
            "LEAVE_APPROVED":     SUCCESS,
            "LEAVE_REJECTED":     DANGER,
            "LEAVE_REVERT_REQUESTED": "#2980b9",
            "LEAVE_REVERTED":     TEXT3,
            "LEAVE_REVERT_REJECTED": DANGER,
            "LEAVE_REQUEST":      "#1a73e8",
            "EXPORT_CSV":         TEXT3,
            "PASSWORD_CHANGE":    "#9334e6",
            "PROFILE_UPDATE":     TEXT3,
        }

        def _short_text(value, limit=42):
            value = str(value or "")
            return value if len(value) <= limit else value[:limit - 3] + "..."

        def _audit_cell(text, width, color=TEXT2, bold=False, align=Qt.AlignmentFlag.AlignCenter):
            lbl = make_label(_short_text(text), 11, color, bold=bold)
            lbl.setAlignment(align)
            lbl.setFixedWidth(width)
            lbl.setFixedHeight(28)
            lbl.setWordWrap(False)
            lbl.setToolTip(str(text or ""))
            return lbl

        def _show_audit_log_popup(log):
            dlg = QDialog(self)
            dlg.setWindowTitle("Audit Log Details")
            dlg.setModal(True)
            dlg.setMinimumSize(640, 420)
            dlg.setStyleSheet(popup_stylesheet())
            dl = QVBoxLayout(dlg); dl.setContentsMargins(18,18,18,18); dl.setSpacing(10)
            dl.addWidget(make_label("Audit Log Details", 16, TEXT, bold=True))

            meta = [
                ("Timestamp", log.get("timestamp", "")),
                ("Action", log.get("action", "")),
                ("Performed By", log.get("performed_by", "")),
                ("Target", log.get("target", "")),
            ]
            for label, value in meta:
                row = QHBoxLayout(); row.setSpacing(8)
                row.addWidget(make_label(label, 12, TEXT3, bold=True))
                row.addStretch()
                row.addWidget(make_label(str(value or "-"), 12, TEXT2))
                dl.addLayout(row)

            dl.addWidget(make_label("Details", 12, TEXT3, bold=True))
            details_e = QTextEdit()
            details_e.setReadOnly(True)
            details_e.setPlainText(str(log.get("details") or ""))
            details_e.setMinimumHeight(170)
            details_e.setStyleSheet(f"""
                QTextEdit {{
                    background: {ENTRY_BG};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 6px;
                    padding: 8px 10px;
                    font-size: 13px;
                }}
            """)
            dl.addWidget(details_e)

            btn_row = QHBoxLayout(); btn_row.addStretch()
            close_b = make_button("Close", height=36)
            close_b.setFixedWidth(100)
            close_b.clicked.connect(dlg.accept)
            btn_row.addWidget(close_b)
            dl.addLayout(btn_row)
            dlg.exec()

        def _reload_audit():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            logs = get_recent_logs(limit=100, important_only=self._audit_important_only)
            if not logs:
                rows_l.addWidget(make_label("No audit logs found.", 12, TEXT3))
                return
            for log in logs:
                row = QWidget()
                row.setMinimumWidth(audit_table_width)
                row.setFixedHeight(44)
                row.setStyleSheet(f"background: {BG3}; border: 1px solid {BORDER}; border-radius: 5px;")
                rl = QHBoxLayout(row); rl.setContentsMargins(8,6,8,6); rl.setSpacing(0)
                color = ACTION_COLORS.get(log["action"], TEXT2)
                values = [
                    (log.get("timestamp", ""), AUDIT_COLS[0][1], TEXT2, Qt.AlignmentFlag.AlignCenter),
                    (log.get("action", ""), AUDIT_COLS[1][1], color, Qt.AlignmentFlag.AlignCenter),
                    (log.get("performed_by", ""), AUDIT_COLS[2][1], TEXT2, Qt.AlignmentFlag.AlignCenter),
                    (log.get("target", ""), AUDIT_COLS[3][1], TEXT2, Qt.AlignmentFlag.AlignCenter),
                ]
                for val, width, clr, align in values:
                    rl.addWidget(_audit_cell(val, width, clr, align=align))

                details_text = str(log.get("details") or "")
                detail_btn = QPushButton("View" if details_text else "-")
                detail_btn.setFixedWidth(AUDIT_COLS[4][1])
                detail_btn.setFixedHeight(28)
                detail_btn.setEnabled(bool(details_text))
                detail_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                detail_btn.setToolTip(_short_text(details_text, 120))
                detail_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {ACCENT if details_text else TEXT3};
                        border: none;
                        font-size: 12px;
                        font-weight: 700;
                        text-decoration: {'underline' if details_text else 'none'};
                    }}
                    QPushButton:hover {{ color: {TEXT}; }}
                    QPushButton:disabled {{ color: {TEXT3}; }}
                """)
                detail_btn.clicked.connect(lambda checked=False, item=dict(log): _show_audit_log_popup(item))
                rl.addWidget(detail_btn)
                rows_l.addWidget(row)

        def _toggle_filter():
            self._audit_important_only = toggle_btn.isChecked()
            toggle_btn.setText("Important Only" if self._audit_important_only else "All Actions")
            toggle_btn.setStyleSheet(self._audit_toggle_style(self._audit_important_only))
            _reload_audit()

        toggle_btn.clicked.connect(_toggle_filter)
        refresh_btn.clicked.connect(_reload_audit)
        _reload_audit()

        scroll = make_scroll(inner)
        lay.addWidget(scroll)
        return page

    def _audit_toggle_style(self, active):
        if active:
            return f"""QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: 6px; font-size: 12px; font-weight: 700; padding: 0 14px;
            }} QPushButton:hover {{ background: #374151; }}"""
        return f"""QPushButton {{
            background: {BG3}; color: {TEXT2}; border: 1px solid {BORDER};
            border-radius: 6px; font-size: 12px; font-weight: 600; padding: 0 14px;
        }} QPushButton:hover {{ background: {BG}; }}"""

    # All Employees
    def _page_employees(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        inner = QWidget(); inner.setStyleSheet("background: transparent;")
        il = QVBoxLayout(inner); il.setContentsMargins(28,28,28,28); il.setSpacing(0)
        il.addWidget(make_label("All Employees",     20, TEXT, bold=True))
        il.addSpacing(4)
        il.addWidget(make_label("Full employee roster", 13, TEXT3))
        il.addSpacing(16); il.addWidget(divider()); il.addSpacing(16)
        filter_row = QWidget(); filter_row.setStyleSheet("background: transparent;")
        fr = QHBoxLayout(filter_row); fr.setContentsMargins(0,0,0,0); fr.setSpacing(10)
        self._emp_search_e = make_entry("Search employee", width=240)
        self._emp_search_e.setFixedHeight(36)
        self._emp_search_e.setPlaceholderText("Search by name, ID, role, or department")
        self._emp_search_e.textChanged.connect(lambda _: _reload_emp_table())
        fr.addWidget(self._emp_search_e, 2)
        self._emp_dept_cb = QComboBox()
        self._emp_dept_cb.setFixedHeight(36)
        self._emp_dept_cb.setStyleSheet(combo_box_style(13))
        self._emp_dept_cb.currentIndexChanged.connect(lambda _: _reload_emp_table())
        fr.addWidget(self._emp_dept_cb, 1)
        il.addWidget(filter_row)
        il.addSpacing(8)
        # Show deleted toggle
        toggle_row = QWidget(); toggle_row.setStyleSheet("background: transparent;")
        tlay = QHBoxLayout(toggle_row); tlay.setContentsMargins(0,0,0,8); tlay.setSpacing(8)
        self._show_deleted_cb = QCheckBox("Show deactivated employees")
        self._show_deleted_cb.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        tlay.addWidget(self._show_deleted_cb)
        tlay.addStretch()
        il.addWidget(toggle_row)

        self._emp_table_container = QWidget(); self._emp_table_container.setStyleSheet("background: transparent;")
        self._emp_table_lay = QVBoxLayout(self._emp_table_container); self._emp_table_lay.setContentsMargins(0,0,0,0)
        il.addWidget(self._emp_table_container)

        def _refresh_dept_filter(emps):
            current = self._emp_dept_cb.currentText() if self._emp_dept_cb.count() else "All Departments"
            db_depts = self.controller.get_departments()
            employee_depts = [display_department(u) for u in emps if display_department(u) != "N/A"]
            depts = ["All Departments"] + sorted({*db_depts, *employee_depts})
            self._emp_dept_cb.blockSignals(True)
            self._emp_dept_cb.clear()
            self._emp_dept_cb.addItems(depts)
            idx = self._emp_dept_cb.findText(current)
            self._emp_dept_cb.setCurrentIndex(idx if idx >= 0 else 0)
            self._emp_dept_cb.blockSignals(False)

        def _reload_emp_table():
            include_del = self._show_deleted_cb.isChecked()
            emps = self.controller.get_all_employees(include_deleted=include_del)
            _refresh_dept_filter(emps)
            query = self._emp_search_e.text().strip().lower()
            dept_filter = self._emp_dept_cb.currentText()
            if query:
                emps = [
                    u for u in emps
                    if query in str(u.get("id", "")).lower()
                    or query in str(u.get("name", "")).lower()
                    or query in str(u.get("role", "")).lower()
                    or query in display_department(u).lower()
                    or query in ("deactivated" if u.get("deleted", False) else "active")
                ]
            if dept_filter != "All Departments":
                emps = [u for u in emps if display_department(u) == dept_filter]
            emps.sort(key=lambda u: int(u["id"]) if str(u["id"]).isdigit() else 0)
            # clear old table
            while self._emp_table_lay.count():
                item = self._emp_table_lay.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            self._emp_table_lay.addWidget(self._employee_table(emps, show_delete=True))

        self._show_deleted_cb.stateChanged.connect(lambda _: _reload_emp_table())
        _reload_emp_table()
        il.addStretch()
        scroll = make_scroll(inner)
        lay.addWidget(scroll)
        return page

    def _employee_table(self, users, show_delete=False):
        container = QWidget(); container.setStyleSheet("background: transparent;")
        vlay = QVBoxLayout(container); vlay.setContentsMargins(0,0,0,0); vlay.setSpacing(0)

        cols = ["ID", "Name", "Department", "Role", "Status", "Attend %"] + (["Action"] if show_delete else [])
        hdr  = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hlay = QHBoxLayout(hdr); hlay.setContentsMargins(10, 8, 10, 8)
        for c in cols:
            l = make_label(c, 11, TEXT3, bold=True)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hlay.addWidget(l, 2 if c == "Name" else 1)

        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(4)

        for u in users:
            row = QWidget()
            row.setStyleSheet(f"background: {BG3}; border: 1px solid {BORDER}; border-radius: 6px;")
            rlay = QHBoxLayout(row); rlay.setContentsMargins(10, 8, 10, 8)

            for val, stretch in [
                (u["id"], 1),
                (u["name"], 2),
                (display_department(u), 1),
                (u["role"], 1),
            ]:
                l = make_label(str(val), 12, TEXT2 if val != u["name"] else TEXT)
                l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                rlay.addWidget(l, stretch)

            is_deleted = u.get("deleted", False)

            # Row styling - red tint for deleted
            row.setStyleSheet(
                f"background: #fee2e2; border: 1px solid #fca5a5; border-radius: 6px;"
                if is_deleted else
                f"background: {BG3}; border: 1px solid {BORDER}; border-radius: 6px;"
            )

            badge = QLabel(" Deactivated " if is_deleted else " Active ")
            badge.setStyleSheet(
                "background: #fecaca; color: #b91c1c; border-radius: 4px; font-size: 12px; font-weight: 700; padding: 2px 6px;"
                if is_deleted else
                "background: #dcfce7; color: #15803d; border-radius: 4px; font-size: 13px; font-weight: 700; padding: 2px 6px;"
            )
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rlay.addWidget(badge, 1)

            attendance_pct = attendance.get_employee_monthly_attendance_percentage(u["id"])
            pct_color = SUCCESS if attendance_pct >= 90 else ("#f0a500" if attendance_pct >= 75 else DANGER)
            pct_lbl = make_label(f"{attendance_pct}%", 12, pct_color, bold=True)
            pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rlay.addWidget(pct_lbl, 1)

            if show_delete:
                if is_deleted:
                    act_btn = QPushButton("Restore")
                    act_btn.setFixedHeight(28)
                    act_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    act_btn.setStyleSheet(f"""
                        QPushButton {{ background: transparent; color: #1d4ed8; border: 1px solid #93c5fd;
                                       border-radius: 4px; font-size: 13px; font-weight: 600; padding: 0 10px; }}
                        QPushButton:hover {{ background: #dbeafe; }}
                    """)
                    act_btn.clicked.connect(lambda _, uid=u["id"]: self._restore_from_table(uid))
                    rlay.addWidget(act_btn, 1)
                else:
                    del_btn = QPushButton("Deactivate")
                    del_btn.setFixedHeight(28)
                    del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    del_btn.setStyleSheet(f"""
                        QPushButton {{ background: transparent; color: {DANGER}; border: 1px solid #fca5a5;
                                       border-radius: 4px; font-size: 13px; font-weight: 600; padding: 0 10px; }}
                        QPushButton:hover {{ background: #fee2e2; }}
                    """)
                    del_btn.clicked.connect(lambda _, uid=u["id"]: self._delete_from_table(uid))
                    rlay.addWidget(del_btn, 1)

            rows_l.addWidget(row)

        if not show_delete:
            vlay.setSpacing(4)
            vlay.addWidget(hdr)
            vlay.addWidget(rows_w)
            return container

        table_box, _, _ = make_sticky_table_scroll(hdr, rows_w, rows_height=380, header_height=48)
        vlay.addWidget(table_box)
        return container

    def _delete_from_table(self, uid):
        if confirm_popup(
            self,
            "Confirm Deactivation",
            f"Deactivate Employee {uid}?\nThey will not be able to log in but can be restored later."
        ):
            ok, msg = self.controller.delete_emp_account(uid)
            Toast(self, msg, success=ok)
            if ok:
                log_action("DELETE_EMPLOYEE", self.username, target=str(uid),
                           details=f"Employee {uid} deactivated by {self.username}.")
                if hasattr(self, "_show_deleted_cb"):
                    self._show_deleted_cb.setChecked(False)
                self._refresh_page("employees")

    def _restore_from_table(self, uid):
        if confirm_popup(
            self,
            "Confirm Restore",
            f"Restore Employee {uid}?\nThey will be able to log in again."
        ):
            ok, msg = self.controller.restore_employee(uid)
            Toast(self, msg, success=ok)
            if ok:
                self._refresh_page("employees")

    # Add Employee
    def _page_add(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        outer_lay = QVBoxLayout(page); outer_lay.setContentsMargins(28,28,28,28); outer_lay.setSpacing(0)
        outer_lay.addWidget(make_label("Add Employee",                    20, TEXT, bold=True))
        outer_lay.addSpacing(4)
        outer_lay.addWidget(make_label("Register a new employee account", 13, TEXT3))
        outer_lay.addSpacing(16); outer_lay.addWidget(divider()); outer_lay.addSpacing(16)

        # Scrollable form so all fields are accessible on smaller screens
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_inner = QWidget(); scroll_inner.setStyleSheet("background: transparent;")
        scroll_lay = QVBoxLayout(scroll_inner); scroll_lay.setContentsMargins(0,0,4,0); scroll_lay.setSpacing(0)
        scroll.setWidget(scroll_inner)

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,20,20,20); fl.setSpacing(8)

        # ── Core fields ──────────────────────────────────────────────
        fl.addWidget(make_label("Employee ID", 12, TEXT2))
        id_e = make_entry("e.g. 005"); fl.addWidget(id_e)

        fl.addWidget(make_label("Full Name", 12, TEXT2))
        name_e = make_entry("e.g. Ananya Singh"); fl.addWidget(name_e)

        fl.addWidget(make_label("Department", 12, TEXT2))
        dept_cb = QComboBox()
        dept_cb.setMinimumHeight(42)
        dept_cb.setStyleSheet(combo_box_style(15))
        departments = self.controller.get_departments()
        dept_cb.addItem("Select Department")
        dept_cb.addItems(departments)
        if not departments:
            dept_cb.setEnabled(False)
            dept_cb.setToolTip("No departments found in the database.")
        fl.addWidget(dept_cb)

        fl.addWidget(make_label("Password", 12, TEXT2))
        pass_e = make_entry("Set initial password", password=True); fl.addWidget(pass_e)

        fl.addWidget(make_label("Basic Salary (₹)", 12, TEXT2))
        sal_e = make_entry("e.g. 25000"); fl.addWidget(sal_e)

        fl.addWidget(make_label("Joining Date (DD/MM/YY)", 12, TEXT2))
        join_e = make_entry("e.g. 08/06/26"); fl.addWidget(join_e)
        join_e.setText(QDate.currentDate().toString("dd/MM/yy"))

        # ── Contact fields (optional) ─────────────────────────────────
        fl.addSpacing(8)
        fl.addWidget(divider())
        fl.addSpacing(4)
        fl.addWidget(make_label("Contact Information  (optional)", 12, TEXT3))
        fl.addSpacing(4)

        fl.addWidget(make_label("Email Address", 12, TEXT2))
        email_e = make_entry("e.g. ananya@company.com"); fl.addWidget(email_e)

        fl.addWidget(make_label("Phone Number", 12, TEXT2))
        phone_e = make_entry("e.g. +91 98765 43210"); fl.addWidget(phone_e)

        fl.addWidget(make_label("Address", 12, TEXT2))
        address_e = QTextEdit()
        address_e.setPlaceholderText("e.g. 12, MG Road, Jaipur, Rajasthan")
        address_e.setFixedHeight(80)
        address_e.setStyleSheet(f"""
            QTextEdit {{
                background: {ENTRY_BG};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                color: {TEXT};
            }}
            QTextEdit:focus {{ border: 1.5px solid {ACCENT}; }}
        """)
        fl.addWidget(address_e)

        # ── Status + button ───────────────────────────────────────────
        fl.addSpacing(4)
        msg_lbl = make_label("", 12, DANGER); fl.addWidget(msg_lbl)
        btn = make_button("Register Employee"); fl.addWidget(btn)

        scroll_lay.addWidget(form)
        scroll_lay.addStretch()
        outer_lay.addWidget(scroll, stretch=1)

        def do_add():
            eid     = id_e.text().strip()
            name    = name_e.text().strip()
            pw      = pass_e.text().strip()
            sal     = sal_e.text().strip()
            joining = join_e.text().strip()
            dept    = dept_cb.currentText().strip()
            email   = email_e.text().strip()
            phone   = phone_e.text().strip()
            address = address_e.toPlainText().strip()

            if not eid or not name or not pw or not sal or not joining or dept == "Select Department":
                msg_lbl.setText("Employee ID, Name, Department, Password, Salary and Joining Date are required.")
                msg_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                return

            ok, msg = self.controller.register_employee(
                eid, name, pw, sal, dept,
                email=email or None,
                phone=phone or None,
                address=address or None,
                joining_date=joining,
            )
            msg_lbl.setText(msg)
            msg_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
            if ok:
                id_e.clear(); name_e.clear(); pass_e.clear(); sal_e.clear()
                join_e.setText(QDate.currentDate().toString("dd/MM/yy"))
                dept_cb.setCurrentIndex(0)
                email_e.clear(); phone_e.clear(); address_e.clear()

        btn.clicked.connect(do_add)
        return page

    # Delete Employee
    def _page_delete(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Delete Employee",                      20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Deactivate an employee record. It can be restored later.", 13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,20,20,20); fl.setSpacing(8)
        fl.addWidget(make_label("Employee ID to delete", 12, TEXT2))
        id_e = make_entry("Enter employee ID"); fl.addWidget(id_e)
        msg_lbl = make_label("", 12, DANGER); fl.addWidget(msg_lbl)
        btn = make_button("Delete Employee", danger=True); fl.addWidget(btn)
        lay.addWidget(form); lay.addStretch()

        def do_delete():
            eid = id_e.text().strip()
            if not eid:
                msg_lbl.setText("Employee ID is required."); return
            if confirm_popup(
                self,
                "Confirm Deactivation",
                f"Deactivate account for Employee {eid}?\nThey can be restored by Admin later."
            ):
                ok, msg = self.controller.delete_emp_account(eid)
                msg_lbl.setText(msg)
                msg_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
                if ok:
                    log_action("DELETE_EMPLOYEE", self.username, target=eid,
                               details=f"Employee {eid} deactivated via Delete Employee page by {self.username}.")
                    id_e.clear()

        btn.clicked.connect(do_delete)
        return page

    # Reset Password
    def _page_reset(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Reset Password",                     20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Set a new password for any employee", 13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,20,20,20); fl.setSpacing(8)
        fl.addWidget(make_label("Employee ID", 12, TEXT2))
        id_e = make_entry("Enter employee ID"); fl.addWidget(id_e)
        fl.addWidget(make_label("New Password", 12, TEXT2))
        pass_e = make_entry("Enter new password", password=True); fl.addWidget(pass_e)
        msg_lbl = make_label("", 12, DANGER); fl.addWidget(msg_lbl)
        btn = make_button("Reset Password"); fl.addWidget(btn)
        lay.addWidget(form); lay.addStretch()

        def do_reset():
            eid, pw = id_e.text().strip(), pass_e.text().strip()
            if not eid or not pw:
                msg_lbl.setText("All fields required."); return
            ok, msg = self.controller.reset_password(eid, pw)
            msg_lbl.setText(msg)
            msg_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
            if ok: id_e.clear(); pass_e.clear()

        btn.clicked.connect(do_reset)
        return page

    # Attendance (Admin)
    def _page_attendance(self):
        from datetime import date as _date


        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Attendance Management", 20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label(f"Today: {display_date(_app_today_iso())}", 13, TEXT3))
        lay.addSpacing(10)

        lay.addWidget(divider()); lay.addSpacing(14)

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,14,20,14); fl.setSpacing(8)

        inp_row = QHBoxLayout()
        inp_row.addWidget(make_label("Emp ID:", 12, TEXT2))
        emp_id_e = make_entry("e.g. 101", width=160); inp_row.addWidget(emp_id_e)
        inp_row.addSpacing(20)
        inp_row.addWidget(make_label("Time (HH:MM):", 12, TEXT2))
        time_e = make_entry("09:00 (blank = now)", width=160); inp_row.addWidget(time_e)
        inp_row.addStretch()
        fl.addLayout(inp_row)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        btn_cfg = dict(height=38)

        checkin_btn  = make_button("Check In",      color=SUCCESS, text_color="#111", hover="#388a3c", **btn_cfg)
        checkout_btn = make_button("Check Out",     color="#2980b9",text_color=TEXT,  hover="#1f6391", **btn_cfg)
        absent_btn   = make_button("Mark Absent",   danger=True,   text_color=TEXT,  **btn_cfg)
        auto_btn         = make_button("Auto-Mark All Absent",   color="#5a3000", text_color="#ffcc66", hover="#7a4400",  **btn_cfg)
        all_present_btn  = make_button("Mark All Present",         color="#166534", text_color="#bbf7d0", hover="#14532d",  **btn_cfg)

        for b in [checkin_btn, checkout_btn, absent_btn, auto_btn, all_present_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        fl.addLayout(btn_row)

        msg_lbl = make_label("", 12, SUCCESS); fl.addWidget(msg_lbl)
        lay.addWidget(form)
        lay.addSpacing(14)
        lay.addWidget(make_label("Today's Attendance", 14, TEXT, bold=True))
        lay.addSpacing(8)

        # Filter row
        att_filter_row = QHBoxLayout(); att_filter_row.setSpacing(6)
        att_filter_row.addWidget(make_label("Filter:", 12, TEXT2))
        self._att_status_filter = "All"
        _att_filter_btns = {}
        _att_pill_styles = {
            "All":      (TEXT2,    BG3,    BORDER),
            "Present":  (SUCCESS,  BG3,    SUCCESS),
            "Late":     ("#f0a500",BG3,    "#f0a500"),
            "Half-Day": ("#3498db",BG3,    "#3498db"),
            "Absent":   (DANGER,   BG3,    DANGER),
        }
        def _att_pill_ss(val, active):
            clr, bg, bdr = _att_pill_styles[val]
            bg_active = clr
            return (
                f"QPushButton {{ background: {bg_active}; color: #fff; border: 1px solid {bdr};"
                f" border-radius: 6px; font-size: 12px; font-weight: 700; padding: 2px 14px; }}"
                if active else
                f"QPushButton {{ background: {bg}; color: {clr}; border: 1px solid {bdr};"
                f" border-radius: 6px; font-size: 12px; font-weight: 600; padding: 2px 14px; }}"
                f" QPushButton:hover {{ background: {BG2}; }}"
            )
        def _att_set_filter(val):
            self._att_status_filter = val
            for v, b in _att_filter_btns.items():
                b.setStyleSheet(_att_pill_ss(v, v == val))
            _reload_table()
        for val in ["All", "Present", "Late", "Half-Day", "Absent"]:
            fb = QPushButton(val); fb.setFixedHeight(28)
            fb.setStyleSheet(_att_pill_ss(val, val == "All"))
            fb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            fb.clicked.connect(lambda _, v=val: _att_set_filter(v))
            _att_filter_btns[val] = fb
            att_filter_row.addWidget(fb)
        att_filter_row.addStretch()
        att_fw = QWidget(); att_fw.setLayout(att_filter_row)
        lay.addWidget(att_fw); lay.addSpacing(8)

        date_row = QWidget(); date_row.setStyleSheet("background: transparent;")
        dr = QHBoxLayout(date_row); dr.setContentsMargins(0,0,0,0); dr.setSpacing(8)
        dr.addWidget(make_label("Date:", 12, TEXT2))
        self._att_view_date = _app_today_iso()
        self._att_date_e = make_entry(display_date(self._att_view_date), width=180)
        self._att_date_e.setFixedHeight(36)
        self._att_date_e.setPlaceholderText("DD/MM/YY")
        dr.addWidget(self._att_date_e)
        cal_btn = make_calendar_button(height=36, width=40, tooltip="Pick attendance date")
        dr.addWidget(cal_btn)
        dr.addStretch()
        lay.addWidget(date_row)
        lay.addSpacing(8)

        # Table
        COLS   = ["Emp ID", "Name", "Dept", "Status", "In", "Out", "Hrs", "Late"]
        STATUS_CLR = {"Present": SUCCESS, "Late": "#f0a500", "Half-Day": "#3498db", "Absent": DANGER, "Missed Checkout": DANGER}

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hlay = QHBoxLayout(hdr); hlay.setContentsMargins(4,7,4,7)
        for c in COLS:
            l = make_label(c, 11, TEXT3, bold=True); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hlay.addWidget(l)

        rows_container = QWidget(); rows_container.setStyleSheet("background: transparent;")
        rows_lay = QVBoxLayout(rows_container); rows_lay.setContentsMargins(0,0,0,0); rows_lay.setSpacing(3)

        table_box, _, _ = make_sticky_table_scroll(hdr, rows_container, rows_height=208, header_height=46)
        lay.addWidget(table_box)
        lay.addStretch()

        def _get_inputs():
            eid = emp_id_e.text().strip()
            t   = time_e.text().strip() or None
            if not eid:
                msg_lbl.setText("Error: Employee ID is required.")
                msg_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                return None, None
            try:
                return int(eid), t
            except ValueError:
                msg_lbl.setText("Error: Emp ID must be a number.")
                msg_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                return None, None

        def _reload_table():
            while rows_lay.count():
                item = rows_lay.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            records = attendance.get_attendance_by_date(self._att_view_date)
            flt = self._att_status_filter
            if flt != "All":
                records = [r for r in records if r.get("status", "") == flt]
            if not records:
                rows_lay.addWidget(make_label(f"No records for {display_date(self._att_view_date)}.", 12, TEXT3))
                return
            for rec in records:
                row = QWidget()
                row.setStyleSheet(f"background: {BG3}; border: 1px solid {BORDER}; border-radius: 5px;")
                rl = QHBoxLayout(row); rl.setContentsMargins(4,6,4,6)
                status = rec.get("status", "N/A")
                display_status = "Missed Checkout" if attendance.is_missed_checkout(rec) else status
                vals = [str(rec.get("emp_id","N/A")), rec.get("name","N/A"), rec.get("department","N/A"),
                        display_status, rec.get("arrival_time") or "N/A", rec.get("checkout_time") or "N/A",
                        str(rec.get("hours_worked") or "N/A"), str(rec.get("late_minutes",0))]
                for j, val in enumerate(vals):
                    clr = STATUS_CLR.get(val, TEXT) if j == 3 else TEXT
                    l = make_label(val, 12, clr); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    rl.addWidget(l)
                rows_lay.addWidget(row)

        def _load_att_date():
            raw = self._att_date_e.text().strip() or display_date(_app_today_iso())
            try:
                raw = parse_display_date(raw)
            except ValueError:
                msg_lbl.setText("Error: Enter a valid date in DD/MM/YY format.")
                msg_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                return
            self._att_view_date = raw
            _reload_table()

        def _open_att_calendar():
            dlg = QDialog(self)
            dlg.setModal(True)
            dlg.setWindowTitle("Select Attendance Date")
            dlg.setFixedSize(360, 400)
            dlg.setStyleSheet("background-color: #0f1115; color: #f8f5ef;")

            dlay = QVBoxLayout(dlg)
            dlay.setContentsMargins(14, 14, 14, 14)
            dlay.setSpacing(10)

            cal = QCalendarWidget()
            cal.setGridVisible(True)
            current = qdate_from_display(self._att_date_e.text().strip())
            cal.setSelectedDate(current if current.isValid() else QDate.currentDate())
            cal.setStyleSheet("""
                QCalendarWidget {
                    background-color: #0f1115;
                    color: #f8f5ef;
                    border: 1px solid #2b313d;
                    border-radius: 10px;
                }
                QCalendarWidget QWidget#qt_calendar_navigationbar {
                    background-color: #111827;
                    border-bottom: 1px solid #2b313d;
                }
                QCalendarWidget QToolButton {
                    background-color: #111827;
                    color: #f8f5ef;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 8px;
                    font-weight: 600;
                }
                QCalendarWidget QToolButton:hover {
                    background-color: #1f2937;
                }
                QCalendarWidget QSpinBox {
                    background-color: #111827;
                    color: #f8f5ef;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    padding: 2px 6px;
                }
                QCalendarWidget QAbstractItemView {
                    selection-background-color: #f8f5ef;
                    selection-color: #0f1115;
                    background-color: #0f1115;
                    color: #f8f5ef;
                }
            """)
            dlay.addWidget(cal)

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(34)
            cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #f8f5ef;
                    border: 1px solid #374151;
                    border-radius: 7px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background: #1f2937;
                }
            """)
            ok_btn = QPushButton("Select")
            ok_btn.setFixedHeight(34)
            ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            ok_btn.setStyleSheet("""
                QPushButton {
                    background: #f8f5ef;
                    color: #111827;
                    border: none;
                    border-radius: 7px;
                    font-size: 13px;
                    font-weight: 700;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background: #ede8df;
                }
            """)
            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(ok_btn)
            dlay.addLayout(btn_row)

            cancel_btn.clicked.connect(dlg.reject)
            ok_btn.clicked.connect(dlg.accept)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._att_date_e.setText(qdate_display(cal.selectedDate()))
                _load_att_date()

        self._att_date_e.editingFinished.connect(_load_att_date)
        cal_btn.clicked.connect(_open_att_calendar)

        def do_checkin():
            eid, t = _get_inputs()
            if eid is None: return
            ok, msg = attendance.mark_arrival(eid, arrival_time=t, manual_override=bool(t), query_date=self._att_view_date)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
            _reload_table()

        def do_checkout():
            eid, t = _get_inputs()
            if eid is None: return
            ok, msg = attendance.mark_checkout(eid, checkout_time=t, manual_override=bool(t), query_date=self._att_view_date)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
            _reload_table()

        def do_absent():
            eid, _ = _get_inputs()
            if eid is None: return
            if not confirm_popup(self, "Mark Absent", f"Mark Emp ID {eid} as absent for {display_date(self._att_view_date)}?"):
                return
            ok, msg = attendance.mark_absent(eid, query_date=self._att_view_date)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
            _reload_table()

        def do_auto_absent():
            if confirm_popup(
                self,
                "Auto-Mark Absent",
                "Mark employees absent only if their assigned shift has already ended and no check-in exists?"
            ):
                ok, names = attendance.auto_mark_absent_for_today()
                if not ok:
                    msg_lbl.setText(names)
                    msg_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                    _reload_table()
                    return
                if names:
                    msg_lbl.setText(f"Marked {len(names)} absent.")
                    msg_lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
                else:
                    msg_lbl.setText("All employees already have records for today.")
                    msg_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 12px;")
                _reload_table()

        def do_all_present():
            if confirm_popup(
                self,
                "Mark All Present",
                "Mark present only employees whose shift is currently active?"
            ):
                ok, marked, skipped, wrong_shift = attendance.mark_all_present_today()
                if not ok:
                    msg_lbl.setText(wrong_shift[0] if wrong_shift else "Attendance cannot be marked today.")
                    msg_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                    _reload_table()
                    return
                parts = []
                if marked:
                    parts.append(f"{len(marked)} marked present")
                if skipped:
                    parts.append(f"{len(skipped)} already recorded")
                if wrong_shift:
                    parts.append(f"{len(wrong_shift)} skipped (wrong shift window)")
                msg_lbl.setText(" | ".join(parts) if parts else "Nothing to mark.")
                color = SUCCESS if marked else TEXT2
                if wrong_shift and not marked:
                    color = DANGER
                msg_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
                if marked:
                    log_action("MARK_ATTENDANCE", self.username, target="ALL",
                               details=f"Bulk mark-all-present: {len(marked)} marked, {len(skipped)} skipped, {len(wrong_shift)} wrong-shift.")
                if wrong_shift:
                    QMessageBox.information(self, "Shift Mismatch - Not Marked",
                        "These employees were NOT marked (shift not active now):\n\n" +
                        "\n".join(f"  - {n}" for n in wrong_shift))
                _reload_table()

        checkin_btn.clicked.connect(do_checkin)
        checkout_btn.clicked.connect(do_checkout)
        absent_btn.clicked.connect(do_absent)
        auto_btn.clicked.connect(do_auto_absent)
        all_present_btn.clicked.connect(do_all_present)
        _reload_table()
        return page

    # Manage Leaves
    def _page_leaves(self):
        from auth_model import set_employee_leaves, get_employee_leaves
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Manage Leaves",                        20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Set total allowed leaves per employee", 13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,16,20,16); fl.setSpacing(8)
        inp_row = QHBoxLayout()
        inp_row.addWidget(make_label("Employee ID:", 12, TEXT2))
        id_e = make_entry("e.g. 101", width=160); inp_row.addWidget(id_e)
        inp_row.addSpacing(20)
        inp_row.addWidget(make_label("Total Leaves:", 12, TEXT2))
        leaves_e = make_entry("e.g. 20", width=160); inp_row.addWidget(leaves_e)
        inp_row.addStretch()
        fl.addLayout(inp_row)
        msg_lbl = make_label("", 12, SUCCESS); fl.addWidget(msg_lbl)
        btn = make_button("Set Leaves", height=38); btn.setFixedWidth(140); fl.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(form)
        lay.addSpacing(16)
        lay.addWidget(make_label("Leave Summary - All Employees", 14, TEXT, bold=True))
        lay.addSpacing(8)

        # Filter row
        lv_filter_row = QHBoxLayout(); lv_filter_row.setSpacing(6)
        lv_filter_row.addWidget(make_label("Filter:", 12, TEXT2))
        self._lv_filter = "All"
        _lv_filter_btns = {}
        def _lv_pill_ss(val, active):
            clr = TEXT2 if val == "All" else (SUCCESS if val == "Has Leaves" else DANGER)
            return (
                f"QPushButton {{ background: {clr}; color: #fff; border: 1px solid {clr};"
                f" border-radius: 6px; font-size: 12px; font-weight: 700; padding: 2px 14px; }}"
                if active else
                f"QPushButton {{ background: {BG3}; color: {clr}; border: 1px solid {clr};"
                f" border-radius: 6px; font-size: 12px; font-weight: 600; padding: 2px 14px; }}"
                f" QPushButton:hover {{ background: {BG2}; }}"
            )
        def _lv_set_filter(val):
            self._lv_filter = val
            for v, b in _lv_filter_btns.items():
                b.setStyleSheet(_lv_pill_ss(v, v == val))
            _reload()
        for val in ["All", "Has Leaves", "No Leaves"]:
            fb = QPushButton(val); fb.setFixedHeight(28)
            fb.setStyleSheet(_lv_pill_ss(val, val == "All"))
            fb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            fb.clicked.connect(lambda _, v=val: _lv_set_filter(v))
            _lv_filter_btns[val] = fb
            lv_filter_row.addWidget(fb)
        lv_filter_row.addStretch()
        lv_fw = QWidget(); lv_fw.setLayout(lv_filter_row)
        lay.addWidget(lv_fw); lay.addSpacing(8)

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(10,8,10,8)
        for c in ["Emp ID", "Name", "Total", "Used", "Remaining"]:
            l = make_label(c, 11, TEXT3, bold=True); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hl.addWidget(l, 4 if c == "Name" else 1)
        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        table_box, _, _ = make_sticky_table_scroll(hdr, rows_w, rows_height=198, header_height=46)
        lay.addWidget(table_box)
        lay.addStretch()

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            flt = self._lv_filter
            for emp in sorted(self.controller.get_all_employees(), key=lambda u: int(u["id"]) if str(u["id"]).isdigit() else 0):
                ok2, info = get_employee_leaves(emp["id"])
                remaining = info["remaining"] if ok2 else 0
                if flt == "Has Leaves" and (not ok2 or remaining <= 0): continue
                if flt == "No Leaves"  and (not ok2 or remaining > 0):  continue
                total     = info["total"]     if ok2 else "N/A"
                used      = info["used"]      if ok2 else "N/A"
                remaining_val = info["remaining"] if ok2 else "N/A"
                rem_color = SUCCESS if ok2 and info["remaining"] > 0 else DANGER
                row = QWidget()
                row.setStyleSheet(f"background: {BG3}; border: 1px solid {BORDER}; border-radius: 6px;")
                rl  = QHBoxLayout(row); rl.setContentsMargins(10,8,10,8)
                for val, stretch, clr in [(emp["id"],1,TEXT2),(emp["name"],4,TEXT),(str(total),1,TEXT),(str(used),1,TEXT2),(str(remaining_val),1,rem_color)]:
                    l = make_label(str(val), 12, clr); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    rl.addWidget(l, stretch)
                rows_l.addWidget(row)

        def do_set():
            eid = id_e.text().strip(); lv = leaves_e.text().strip()
            if not eid or not lv:
                msg_lbl.setText("Both fields are required."); msg_lbl.setStyleSheet(f"color:{DANGER}; font-size:12px;"); return
            ok2, msg = set_employee_leaves(eid, lv)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color: {SUCCESS if ok2 else DANGER}; font-size: 12px;")
            if ok2: id_e.clear(); leaves_e.clear(); _reload()

        btn.clicked.connect(do_set)
        _reload()
        return page

    # Shift Management
    def _page_shift_management(self):
        from shift_model import assign_shift, get_all_shift_assignments, approve_sunday_work, SHIFTS, SHIFT_COLORS
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Shift Management",                 20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Assign or update Morning / Evening / Night shifts for employees", 13, TEXT3))
        lay.addSpacing(14); lay.addWidget(divider()); lay.addSpacing(14)

        # Shift info cards
        info_row = QHBoxLayout(); info_row.setSpacing(10)
        shift_info = [
            ("Morning", "09:00 to 17:00", SHIFT_COLORS["Morning"]),
            ("Evening", "14:00 to 22:00", SHIFT_COLORS["Evening"]),
            ("Night",   "22:00 to 06:00", SHIFT_COLORS["Night"]),
        ]
        for title, hours, color in shift_info:
            c = QFrame()
            c.setStyleSheet(f"QFrame {{ background: {BG3}; border: 1px solid {BORDER}; border-radius: 8px; }}")
            cl = QVBoxLayout(c); cl.setContentsMargins(14,12,14,12); cl.setSpacing(4)
            t = make_label(title, 14, color, bold=True); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h = make_label(hours, 12, TEXT2);             h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            g = make_label("8 hrs  |  Grace: 15 min", 11, TEXT3); g.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(t); cl.addWidget(h); cl.addWidget(g)
            info_row.addWidget(c)
        lay.addLayout(info_row); lay.addSpacing(16)

        # Assign form
        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,16,20,16); fl.setSpacing(8)
        fl.addWidget(make_label("Assign / Update Shift", 13, TEXT, bold=True))
        row1 = QHBoxLayout(); row1.setSpacing(12)
        row1.addWidget(make_label("Employee ID:", 12, TEXT2))
        id_e = make_entry("e.g. 101", width=160); row1.addWidget(id_e)
        row1.addSpacing(16)
        row1.addWidget(make_label("Shift:", 12, TEXT2))
        shift_cb = QComboBox(); shift_cb.addItems(list(SHIFTS.keys()))
        shift_cb.setMinimumHeight(38); shift_cb.setMinimumWidth(180)
        shift_cb.setStyleSheet(combo_box_style(15))
        row1.addWidget(shift_cb); row1.addStretch()
        fl.addLayout(row1)
        msg_lbl = make_label("", 12, SUCCESS); fl.addWidget(msg_lbl)
        btn_assign = make_button("Assign / Update Shift", height=38); btn_assign.setFixedWidth(180)
        fl.addWidget(btn_assign, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(form); lay.addSpacing(16)

        sunday_form = card_frame()
        sfl = QVBoxLayout(sunday_form); sfl.setContentsMargins(20,16,20,16); sfl.setSpacing(8)
        sfl.addWidget(make_label("Approve Sunday Work", 13, TEXT, bold=True))
        sunday_row = QHBoxLayout(); sunday_row.setSpacing(12)
        sunday_row.addWidget(make_label("Employee ID:", 12, TEXT2))
        sunday_emp_e = make_entry("e.g. 101", width=130); sunday_row.addWidget(sunday_emp_e)
        sunday_row.addWidget(make_label("Date:", 12, TEXT2))
        sunday_date_e = make_entry("DD/MM/YY", width=130)
        sunday_date_e.setText(qdate_display(QDate.currentDate()))
        sunday_row.addWidget(sunday_date_e)
        sunday_date_btn = make_calendar_button(height=38, width=40, tooltip="Pick Sunday work date")
        sunday_row.addWidget(sunday_date_btn)
        sunday_row.addWidget(make_label("Reason:", 12, TEXT2))
        sunday_reason_e = make_entry("e.g. operations coverage", width=260)
        sunday_row.addWidget(sunday_reason_e)
        sunday_row.addStretch()
        sfl.addLayout(sunday_row)
        sunday_msg_lbl = make_label("", 12, SUCCESS); sfl.addWidget(sunday_msg_lbl)
        approve_sunday_btn = make_button("Approve Sunday Work", height=38); approve_sunday_btn.setFixedWidth(190)
        sfl.addWidget(approve_sunday_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(sunday_form); lay.addSpacing(16)

        # Assignments table
        lay.addWidget(make_label("All Shift Assignments", 14, TEXT, bold=True))
        lay.addSpacing(8)

        COLS = ["Emp ID", "Name", "Department", "Assigned Shift", "Shift Hours", "Assigned On"]
        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(6,8,6,8)
        for c in COLS:
            l = make_label(c, 11, TEXT3, bold=True); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hl.addWidget(l, 3 if c in ("Name","Department","Assigned Shift") else 1)
        lay.addWidget(hdr)

        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        scroll = make_scroll(rows_w); scroll.setFixedHeight(280); lay.addWidget(scroll)
        lay.addStretch()

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            assignments = sorted(get_all_shift_assignments(), key=lambda a: int(a["emp_id"]) if str(a["emp_id"]).isdigit() else 0)
            if not assignments:
                rows_l.addWidget(make_label("No employees found.", 12, TEXT3)); return
            for i, a in enumerate(assignments):
                row = QWidget()
                row.setStyleSheet(f"background: {'#faf7f2' if i%2==0 else '#f5f0e8'}; border: 1px solid {BORDER}; border-radius: 5px;")
                rl = QHBoxLayout(row); rl.setContentsMargins(6,8,6,8)
                shift = a["shift"]
                shift_color = SHIFT_COLORS.get(shift, TEXT2)
                hours_label = f"{SHIFTS[shift].get('hours', '?')} hrs  ({SHIFTS[shift]['start']} to {SHIFTS[shift]['end']})" if shift in SHIFTS else "N/A"
                for val, stretch, clr in [
                    (a["emp_id"], 1, TEXT2),
                    (a["name"],   3, TEXT),
                    (a["department"], 3, TEXT2),
                    (shift,       3, shift_color),
                    (hours_label, 1, TEXT3),
                    (display_date(a["assigned_on"]), 1, TEXT3),
                ]:
                    l = make_label(str(val), 12, clr); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    rl.addWidget(l, stretch)
                rows_l.addWidget(row)

        def _open_sunday_calendar():
            dlg = QDialog(self)
            dlg.setModal(True)
            dlg.setWindowTitle("Pick Sunday Work Date")
            dlg.setFixedSize(360, 400)
            dlg.setStyleSheet("background-color: #0f1115; color: #f8f5ef;")

            dlay = QVBoxLayout(dlg)
            dlay.setContentsMargins(12, 12, 12, 12)
            dlay.setSpacing(10)

            cal = QCalendarWidget()
            cal.setGridVisible(True)
            current = qdate_from_display(sunday_date_e.text().strip())
            cal.setSelectedDate(current if current.isValid() else QDate.currentDate())
            cal.setStyleSheet("""
                QCalendarWidget {
                    background-color: #0f1115;
                    color: #f8f5ef;
                    border: 1px solid #2b313d;
                    border-radius: 10px;
                }
                QCalendarWidget QWidget#qt_calendar_navigationbar {
                    background-color: #111827;
                    border-bottom: 1px solid #2b313d;
                }
                QCalendarWidget QToolButton {
                    background-color: #111827;
                    color: #f8f5ef;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 8px;
                    font-weight: 600;
                }
                QCalendarWidget QToolButton:hover {
                    background-color: #1f2937;
                }
                QCalendarWidget QSpinBox {
                    background-color: #111827;
                    color: #f8f5ef;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    padding: 2px 6px;
                }
                QCalendarWidget QAbstractItemView {
                    selection-background-color: #f8f5ef;
                    selection-color: #0f1115;
                    background-color: #0f1115;
                    color: #f8f5ef;
                }
            """)
            dlay.addWidget(cal)

            btn_row = QHBoxLayout(); btn_row.addStretch()
            cancel_b = make_button("Cancel", color=BG3, text_color=TEXT, hover=BG2, height=34)
            ok_b = make_button("OK", height=34)
            cancel_b.clicked.connect(dlg.reject)
            ok_b.clicked.connect(dlg.accept)
            btn_row.addWidget(cancel_b); btn_row.addWidget(ok_b)
            dlay.addLayout(btn_row)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                sunday_date_e.setText(qdate_display(cal.selectedDate()))

        def do_assign():
            eid = id_e.text().strip()
            if not eid:
                msg_lbl.setText("Employee ID is required.")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;"); return
            shift_name = shift_cb.currentText()
            if not confirm_popup(self, "Assign Shift", f"Assign {shift_name} shift to Emp ID {eid}?"):
                return
            ok2, msg = assign_shift(eid, shift_name)
            msg_lbl.setText(msg)
            msg_lbl.setStyleSheet(f"color:{SUCCESS if ok2 else DANGER};font-size:12px;")
            if ok2: id_e.clear(); _reload()

        def do_approve_sunday():
            from datetime import date as _date
            eid = sunday_emp_e.text().strip()
            reason = sunday_reason_e.text().strip()
            if not eid:
                sunday_msg_lbl.setText("Employee ID is required.")
                sunday_msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            if not reason:
                sunday_msg_lbl.setText("Reason is required for Sunday work approval.")
                sunday_msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            try:
                work_date = parse_display_date(sunday_date_e.text().strip())
            except ValueError:
                sunday_msg_lbl.setText("Enter a valid Sunday date in DD/MM/YY format.")
                sunday_msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            try:
                if _date.fromisoformat(work_date).weekday() != 6:
                    sunday_msg_lbl.setText("Selected date is not Sunday. Choose a Sunday date first.")
                    sunday_msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                    return
            except ValueError:
                sunday_msg_lbl.setText("Enter a valid Sunday date in DD/MM/YY format.")
                sunday_msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            if not confirm_popup(
                self,
                "Approve Sunday Work",
                f"Approve Sunday work for Emp ID {eid} on {display_date(work_date)}?"
            ):
                return
            ok3, msg3 = approve_sunday_work(eid, work_date, approved_by=self.username, reason=reason)
            sunday_msg_lbl.setText(msg3)
            sunday_msg_lbl.setStyleSheet(f"color:{SUCCESS if ok3 else DANGER};font-size:12px;")
            if ok3:
                sunday_emp_e.clear()
                sunday_reason_e.clear()

        btn_assign.clicked.connect(do_assign)
        sunday_date_btn.clicked.connect(_open_sunday_calendar)
        approve_sunday_btn.clicked.connect(do_approve_sunday)
        _reload()
        return page

    # Monthly Attendance Report
    def _page_monthly_attendance_report(self):
        import csv, os
        from datetime import datetime as _dt, date as _date

        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)

        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

        hdr_row = QHBoxLayout()
        lc = QVBoxLayout()
        lc.addWidget(make_label("Monthly Attendance", 20, TEXT, bold=True))
        lc.addWidget(make_label("Employee-wise attendance summary for a selected month", 13, TEXT3))
        hdr_row.addLayout(lc); hdr_row.addStretch()

        month_cb = QComboBox()
        month_cb.addItems(month_names)
        month_cb.setCurrentIndex(_dt.today().month - 1)
        month_cb.setFixedHeight(38)
        month_cb.setFixedWidth(132)
        month_cb.setStyleSheet(combo_box_style(14))

        year_e = make_entry("Year", width=82)
        year_e.setText(str(_dt.today().year))

        export_btn = QPushButton("Export CSV")
        export_btn.setFixedHeight(38); export_btn.setFixedWidth(110)
        export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        export_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT}; color:#fff; border:none;
                           border-radius:6px; font-size:14px; font-weight:700; padding:0 12px; }}
            QPushButton:hover {{ background:#374151; }}
        """)

        hdr_row.addWidget(make_label("Month:", 12, TEXT2))
        hdr_row.addSpacing(6); hdr_row.addWidget(month_cb)
        hdr_row.addSpacing(6); hdr_row.addWidget(year_e)
        hdr_row.addSpacing(6); hdr_row.addWidget(export_btn)
        lay.addLayout(hdr_row)
        lay.addSpacing(12); lay.addWidget(divider()); lay.addSpacing(10)

        msg_lbl = make_label("", 12, SUCCESS)
        lay.addWidget(msg_lbl)
        lay.addSpacing(8)

        summary_row = QHBoxLayout(); summary_row.setSpacing(10)
        total_emp_lbl = make_label("0", 26, TEXT, bold=True)
        present_lbl = make_label("0", 26, SUCCESS, bold=True)
        halfday_lbl = make_label("0", 26, "#3498db", bold=True)
        absent_lbl = make_label("0", 26, DANGER, bold=True)
        avg_lbl = make_label("0%", 26, "#2980b9", bold=True)

        for num_lbl, caption in [
            (total_emp_lbl, "Employees"),
            (present_lbl, "Full Attendance"),
            (halfday_lbl, "Half Days"),
            (absent_lbl, "Absent/Missed"),
            (avg_lbl, "Overall Attendance"),
        ]:
            c = card_frame(8)
            cl = QVBoxLayout(c); cl.setContentsMargins(12,14,12,14); cl.setSpacing(4)
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(num_lbl)
            cl.addWidget(make_label(caption, 11, TEXT3), alignment=Qt.AlignmentFlag.AlignCenter)
            summary_row.addWidget(c)
        lay.addLayout(summary_row)
        lay.addSpacing(12)

        COLUMNS = [
            ("Emp ID", 70), ("Name", 160), ("Dept", 130), ("Eligible", 78),
            ("Not Marked", 88),
            ("Present", 78), ("Late", 70), ("Half Day", 82), ("Absent", 78),
            ("Missed Out", 88), ("Late Hrs", 82), ("Hours", 82), ("OT Hrs", 76), ("Attendance", 96),
        ]
        table_min_width = sum(width for _, width in COLUMNS) + 22

        def _cell(text, size, color, bold=False, width=90):
            l = make_label(str(text), size, color, bold=bold)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setFixedWidth(width)
            l.setMinimumHeight(28)
            l.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return l

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hdr.setMinimumWidth(table_min_width)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(8,10,8,10); hl.setSpacing(0)
        for c, width in COLUMNS:
            hl.addWidget(_cell(c, 11, TEXT3, bold=True, width=width))

        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_w.setMinimumWidth(table_min_width)
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)

        table_box, _, _ = make_sticky_table_scroll(hdr, rows_w, rows_height=378, header_height=52)
        lay.addWidget(table_box)
        lay.addStretch()

        def _selected_month_year():
            year = year_e.text().strip()
            if not (year.isdigit() and len(year) == 4):
                return None, None
            return month_cb.currentIndex() + 1, int(year)

        def _month_label():
            return f"{month_cb.currentText()} {year_e.text().strip()}"

        def _get_report():
            month, year = _selected_month_year()
            if month is None:
                return None
            return attendance.get_monthly_attendance_report(month, year)

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)

            report = _get_report()
            if report is None:
                total_emp_lbl.setText("0")
                present_lbl.setText("0")
                halfday_lbl.setText("0")
                absent_lbl.setText("0")
                avg_lbl.setText("0%")
                msg_lbl.setText("Error: Enter a valid 4-digit year.")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return

            total_emp_lbl.setText(str(len(report)))
            eligible_days = sum(r["eligible_days"] for r in report)
            present_days = sum(r["present"] + r["late"] for r in report)
            half_days = sum(r["half_day"] for r in report)
            absent_days = sum(r["absent"] + r.get("missed_checkout", 0) for r in report)
            attendance_credit = present_days + (half_days * 0.5)
            avg_att = round((attendance_credit / eligible_days) * 100, 2) if eligible_days else 0
            present_lbl.setText(str(present_days))
            halfday_lbl.setText(str(half_days))
            absent_lbl.setText(str(absent_days))
            avg_lbl.setText(f"{avg_att}%")

            if not report:
                rows_l.addWidget(make_label(f"No employees found for {_month_label()}.", 12, TEXT3))
                msg_lbl.setText("")
                return

            msg_lbl.setText(f"Showing {len(report)} employees for {_month_label()}.")
            msg_lbl.setStyleSheet(f"color:{TEXT2};font-size:12px;")

            report.sort(key=lambda r: int(r["emp_id"]) if str(r["emp_id"]).isdigit() else 0)
            for i, rec in enumerate(report):
                pct = rec["attendance_percentage"]
                pct_color = SUCCESS if pct >= 90 else ("#f0a500" if pct >= 75 else DANGER)
                row = QWidget()
                row.setStyleSheet(f"background: {'#faf7f2' if i%2==0 else '#f5f0e8'}; border:1px solid {BORDER}; border-radius:5px;")
                row.setMinimumHeight(46)
                row.setMinimumWidth(table_min_width)
                rl = QHBoxLayout(row); rl.setContentsMargins(8,10,8,10); rl.setSpacing(0)
                values = [
                    (rec["emp_id"], TEXT2),
                    (rec["name"], TEXT),
                    (rec["department"], TEXT2),
                    (rec["eligible_days"], TEXT),
                    (rec["not_marked"], DANGER if rec["not_marked"] else TEXT3),
                    (rec["present"], SUCCESS if rec["present"] else TEXT3),
                    (rec["late"], "#f0a500" if rec["late"] else TEXT3),
                    (rec["half_day"], "#3498db" if rec["half_day"] else TEXT3),
                    (rec["absent"], DANGER if rec["absent"] else TEXT3),
                    (rec.get("missed_checkout", 0), DANGER if rec.get("missed_checkout", 0) else TEXT3),
                    (rec["total_late_hours"], "#f0a500" if rec["total_late_hours"] else TEXT3),
                    (rec["total_hours_worked"], TEXT2),
                    (rec["total_overtime_hours"], SUCCESS if rec["total_overtime_hours"] else TEXT3),
                    (f"{pct}%", pct_color),
                ]
                for (val, clr), (_, width) in zip(values, COLUMNS):
                    rl.addWidget(_cell(val, 12, clr, width=width))
                rows_l.addWidget(row)

        def _export_csv():
            report = _get_report()
            if report is None:
                msg_lbl.setText("Error: Enter a valid 4-digit year.")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            if not report:
                msg_lbl.setText("Error: No records to export.")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return

            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Monthly Attendance",
                f"monthly_attendance_{month_cb.currentText()}_{year_e.text().strip()}.csv",
                "CSV files (*.csv)"
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"

            fields = [
                "month", "emp_id", "name", "department", "month_days",
                "eligible_days", "recorded_days", "not_marked",
                "present", "late", "half_day", "absent",
                "missed_checkout", "total_late_hours", "total_hours_worked",
                "total_overtime_hours", "attendance_percentage",
            ]
            rows = [{field: rec.get(field, "") for field in fields} for rec in report]
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                msg_lbl.setText(f"Exported {len(rows)} attendance records to {os.path.basename(path)}")
                msg_lbl.setStyleSheet(f"color:{SUCCESS};font-size:12px;")
            except Exception as e:
                msg_lbl.setText(f"Export failed: {e}")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")

        month_cb.currentIndexChanged.connect(lambda _: _reload())
        year_e.editingFinished.connect(_reload)
        export_btn.clicked.connect(_export_csv)
        _reload()
        return page

    # Salary Report

    def _page_salary_report(self):
        import csv, os
        from shift_model import get_all_salary_summaries, save_salary_summaries, SHIFTS, GRACE_MINUTES, OT_MULTIPLIER, MIN_OVERTIME_AFTER_SHIFT_MINUTES
        from datetime import datetime as _dt, date as _date
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)

        hdr_row = QHBoxLayout()
        lc = QVBoxLayout()
        lc.addWidget(make_label("Salary Report", 20, TEXT, bold=True))
        hdr_row.addLayout(lc); hdr_row.addStretch()

        # Salary revision card
        from auth_model import (
            set_basic_salary, get_salary_history,
            update_salary_history_entry, delete_salary_history_entry
        )
        sal_card = card_frame(8)
        sal_card.setFixedHeight(128)
        scl = QVBoxLayout(sal_card); scl.setContentsMargins(16,12,16,12); scl.setSpacing(10)

        sal_title_row = QHBoxLayout(); sal_title_row.setSpacing(8)
        sal_title_row.addWidget(make_label("Salary Revision", 13, TEXT, bold=True))
        sal_title_row.addWidget(make_label("Manage effective-date salary changes for accurate old reports.", 11, TEXT3))
        sal_title_row.addStretch()
        scl.addLayout(sal_title_row)

        sal_form_row = QHBoxLayout(); sal_form_row.setSpacing(8)
        sal_id_e  = make_entry("Emp ID", width=88)
        sal_amt_e = make_entry("Amount e.g. +5000 / -2000 / 25000", width=210)
        sal_effective_e = make_entry("DD/MM/YY", width=128)
        sal_effective_e.setText(qdate_display(QDate.currentDate()))
        sal_date_btn = make_calendar_button(height=42, width=42, tooltip="Pick effective date")
        sal_note_e = make_entry("Revision note / reason", width=220)
        sal_msg_l = make_label("", 12, SUCCESS)
        sal_msg_l.setMinimumHeight(18)
        sal_warning_l = make_label("This salary will apply from the selected effective date onward.", 11, TEXT3)

        sal_btn = make_button("Save Revision", height=38)
        sal_btn.setFixedWidth(130)
        sal_form_row.addWidget(sal_id_e)
        sal_form_row.addWidget(sal_amt_e)
        sal_form_row.addWidget(sal_effective_e)
        sal_form_row.addWidget(sal_date_btn)
        sal_form_row.addWidget(sal_note_e)
        sal_form_row.addWidget(sal_btn)
        sal_form_row.addStretch()
        scl.addLayout(sal_form_row)
        sal_warning_l.setVisible(False)
        scl.addWidget(sal_msg_l)

        history_table = QWidget(); history_table.setStyleSheet("background: transparent;")
        history_table.setVisible(False)
        history_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        history_l = QVBoxLayout(history_table); history_l.setContentsMargins(0,0,0,0); history_l.setSpacing(6)
        history_hdr = QWidget(); history_hdr.setStyleSheet(f"background:{BG}; border-radius:6px;")
        history_hdr.setFixedHeight(42)
        hhl = QHBoxLayout(history_hdr); hhl.setContentsMargins(8,8,8,8); hhl.setSpacing(0)
        salary_history_cols = [("Effective", 104), ("Salary", 120), ("Previous", 120), ("Note", 360), ("Created", 170), ("Actions", 190)]

        def _salary_history_cell(text, width, color=TEXT2, bold=False):
            lbl = make_label(str(text), 11, color, bold=bold)
            lbl.setFixedWidth(width)
            lbl.setFixedHeight(28)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(False)
            return lbl

        for text, width in salary_history_cols:
            hhl.addWidget(_salary_history_cell(text, width, TEXT3, bold=True))
        history_l.addWidget(history_hdr)
        salary_history_rows_w = QWidget(); salary_history_rows_w.setStyleSheet("background: transparent;")
        salary_history_rows_l = QVBoxLayout(salary_history_rows_w); salary_history_rows_l.setContentsMargins(0,0,0,0); salary_history_rows_l.setSpacing(5)
        salary_history_scroll = make_scroll(salary_history_rows_w)
        salary_history_scroll.setFixedHeight(96)
        history_l.addWidget(salary_history_scroll)
        scl.addWidget(history_table)

        def _open_salary_date_picker():
            dlg = QDialog(self)
            dlg.setModal(True)
            dlg.setWindowTitle("Pick Effective Date")
            dlg.setFixedSize(360, 400)
            dlg.setStyleSheet("background-color: #0f1115; color: #f8f5ef;")

            dlay = QVBoxLayout(dlg)
            dlay.setContentsMargins(12, 12, 12, 12)
            dlay.setSpacing(10)

            cal = QCalendarWidget()
            cal.setGridVisible(True)
            current = qdate_from_display(sal_effective_e.text().strip())
            cal.setSelectedDate(current if current.isValid() else QDate.currentDate())
            cal.setStyleSheet("""
                QCalendarWidget {
                    background-color: #0f1115;
                    color: #f8f5ef;
                    border: 1px solid #2b313d;
                    border-radius: 10px;
                }
                QCalendarWidget QWidget#qt_calendar_navigationbar {
                    background-color: #111827;
                    border-bottom: 1px solid #2b313d;
                }
                QCalendarWidget QToolButton {
                    background-color: #111827;
                    color: #f8f5ef;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 8px;
                    font-weight: 600;
                }
                QCalendarWidget QToolButton:hover {
                    background-color: #1f2937;
                }
                QCalendarWidget QSpinBox {
                    background-color: #111827;
                    color: #f8f5ef;
                    border: 1px solid #374151;
                    border-radius: 6px;
                    padding: 2px 6px;
                }
                QCalendarWidget QAbstractItemView {
                    selection-background-color: #f8f5ef;
                    selection-color: #0f1115;
                    background-color: #0f1115;
                    color: #f8f5ef;
                }
            """)
            dlay.addWidget(cal)

            btn_row = QHBoxLayout(); btn_row.addStretch()
            cancel_b = make_button("Cancel", color=BG3, text_color=TEXT, hover=BG2, height=34)
            ok_b = make_button("OK", height=34)
            cancel_b.clicked.connect(dlg.reject)
            ok_b.clicked.connect(dlg.accept)
            btn_row.addWidget(cancel_b); btn_row.addWidget(ok_b)
            dlay.addLayout(btn_row)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                sal_effective_e.setText(qdate_display(cal.selectedDate()))

        sal_date_btn.clicked.connect(_open_salary_date_picker)

        def _selected_salary_emp_id():
            eid = sal_id_e.text().strip()
            if not eid:
                sal_msg_l.setText("Enter Employee ID and press Enter to view salary history.")
                sal_msg_l.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return None
            return eid

        def _clear_salary_history_rows():
            while salary_history_rows_l.count():
                item = salary_history_rows_l.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

        def _edit_salary_history(entry):
            dlg = QDialog(self)
            dlg.setWindowTitle("Edit Salary Revision")
            dlg.setStyleSheet(popup_stylesheet())
            dl = QVBoxLayout(dlg); dl.setContentsMargins(18,18,18,18); dl.setSpacing(10)
            dl.addWidget(make_label("Edit Salary Revision", 15, TEXT, bold=True))
            amt_e = make_entry("Amount", width=260)
            amt_e.setText(str(entry["basic_salary"]))
            eff_e = QDateEdit()
            eff_e.setCalendarPopup(True)
            eff_e.setDisplayFormat("dd/MM/yy")
            saved_date = qdate_from_display(display_date(entry["effective_from"]))
            eff_e.setDate(saved_date if saved_date.isValid() else QDate.currentDate())
            eff_e.setFixedHeight(42)
            eff_e.setStyleSheet(f"""
                QDateEdit {{ background:{ENTRY_BG}; color:{TEXT}; border:1px solid {BORDER};
                             border-radius:6px; padding:0 10px; font-size:14px; }}
                QDateEdit::drop-down {{ border:none; width:24px; }}
            """)
            eff_e.calendarWidget().setStyleSheet("""
                QCalendarWidget { background-color: #0f1115; color: #f8f5ef; border: 1px solid #2b313d; border-radius: 10px; }
                QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #111827; border-bottom: 1px solid #2b313d; }
                QCalendarWidget QToolButton { background-color: #111827; color: #f8f5ef; border: none; border-radius: 6px; padding: 6px 8px; font-weight: 600; }
                QCalendarWidget QToolButton:hover { background-color: #1f2937; }
                QCalendarWidget QSpinBox { background-color: #111827; color: #f8f5ef; border: 1px solid #374151; border-radius: 6px; padding: 2px 6px; }
                QCalendarWidget QAbstractItemView { selection-background-color: #f8f5ef; selection-color: #0f1115; background-color: #0f1115; color: #f8f5ef; alternate-background-color: #111827; gridline-color: #2b313d; outline: 0; }
            """)
            note_e = QTextEdit()
            note_e.setPlainText(str(entry.get("note", "")))
            note_e.setFixedHeight(90)
            note_e.setStyleSheet(f"background:{ENTRY_BG}; color:{TEXT}; border:1px solid {BORDER}; border-radius:6px; padding:8px;")
            msg_l = make_label("", 12, DANGER)
            btn_row = QHBoxLayout(); btn_row.addStretch()
            save_b = make_button("Save", height=36); cancel_b = make_button("Cancel", color=BG3, text_color=TEXT, hover=BG2, height=36)
            btn_row.addWidget(cancel_b); btn_row.addWidget(save_b)
            dl.addWidget(amt_e); dl.addWidget(eff_e); dl.addWidget(note_e); dl.addWidget(msg_l); dl.addLayout(btn_row)

            def _save_edit():
                ok, msg = update_salary_history_entry(
                    entry["id"],
                    amt_e.text().strip(),
                    qdate_iso(eff_e.date()),
                    note_e.toPlainText().strip()
                )
                if ok:
                    dlg.accept()
                    sal_msg_l.setText(msg); sal_msg_l.setStyleSheet(f"color:{SUCCESS};font-size:12px;")
                    _reload_salary_history()
                    _reload()
                else:
                    msg_l.setText(msg)

            save_b.clicked.connect(_save_edit)
            cancel_b.clicked.connect(dlg.reject)
            dlg.exec()

        def _reload_salary_history():
            eid = _selected_salary_emp_id()
            if not eid:
                return
            history = get_salary_history(eid)

            dlg = QDialog(self)
            dlg.setWindowTitle("Salary Revision History")
            dlg.setModal(True)
            dlg.setMinimumSize(980, 420)
            dlg.setStyleSheet(popup_stylesheet())
            dl = QVBoxLayout(dlg); dl.setContentsMargins(18,18,18,18); dl.setSpacing(10)
            dl.addWidget(make_label(f"Salary Revision History - Employee ID {eid}", 16, TEXT, bold=True))

            if not history:
                dl.addWidget(make_label("No salary history found for this employee.", 12, TEXT3))
            else:
                popup_hdr = QWidget(); popup_hdr.setStyleSheet(f"background:{BG}; border-radius:6px;")
                popup_hdr.setFixedHeight(42)
                phl = QHBoxLayout(popup_hdr); phl.setContentsMargins(8,8,8,8); phl.setSpacing(0)
                for text, width in salary_history_cols:
                    phl.addWidget(_salary_history_cell(text, width, TEXT3, bold=True))
                dl.addWidget(popup_hdr)

                popup_rows_w = QWidget(); popup_rows_w.setStyleSheet("background: transparent;")
                popup_rows_l = QVBoxLayout(popup_rows_w); popup_rows_l.setContentsMargins(0,0,0,0); popup_rows_l.setSpacing(6)
                popup_scroll = make_scroll(popup_rows_w)
                popup_scroll.setMinimumHeight(240)
                dl.addWidget(popup_scroll)

                for i, entry in enumerate(history):
                    row = QWidget()
                    row.setStyleSheet(f"background:{'#faf7f2' if i % 2 == 0 else '#f5f0e8'}; border:1px solid {BORDER}; border-radius:5px;")
                    row.setFixedHeight(42)
                    rl = QHBoxLayout(row); rl.setContentsMargins(8,6,8,6); rl.setSpacing(0)
                    prev = entry.get("previous_salary")
                    values = [
                        entry["effective_from"],
                        f"Rs. {entry['basic_salary']:,.0f}",
                        "N/A" if prev is None else f"Rs. {float(prev):,.0f}",
                        entry.get("note", "") or "-",
                        entry.get("created_at", "") or "-",
                    ]
                    for value, (_, width) in zip(values, salary_history_cols[:-1]):
                        rl.addWidget(_salary_history_cell(value, width, TEXT if value != "-" else TEXT3))
                    action_w = QWidget(); action_w.setStyleSheet("background: transparent;")
                    al = QHBoxLayout(action_w); al.setContentsMargins(0,0,0,0); al.setSpacing(8)
                    edit_b = make_button("Edit", height=26); edit_b.setFixedWidth(72)
                    del_b = make_button("Delete", danger=True, height=26); del_b.setFixedWidth(84)
                    edit_b.clicked.connect(lambda checked=False, e=entry, d=dlg: (d.accept(), _edit_salary_history(e)))
                    del_b.clicked.connect(lambda checked=False, e=entry, d=dlg: (d.accept(), _delete_salary_history(e)))
                    al.addWidget(edit_b); al.addWidget(del_b); al.addStretch()
                    action_w.setFixedWidth(salary_history_cols[-1][1])
                    action_w.setFixedHeight(28)
                    rl.addWidget(action_w)
                    popup_rows_l.addWidget(row)

            btn_row = QHBoxLayout(); btn_row.addStretch()
            close_b = make_button("Close", height=36); close_b.setFixedWidth(100)
            close_b.clicked.connect(dlg.accept)
            btn_row.addWidget(close_b)
            dl.addLayout(btn_row)
            dlg.exec()

        def _delete_salary_history(entry):
            if not confirm_popup(self, "Delete Salary Revision", f"Delete salary revision ₹{entry['basic_salary']:,.0f} from {display_date(entry['effective_from'])}?"):
                return
            ok, msg = delete_salary_history_entry(entry["id"])
            sal_msg_l.setText(msg)
            sal_msg_l.setStyleSheet(f"color:{SUCCESS if ok else DANGER};font-size:12px;")
            if ok:
                _reload()

        def _do_set_salary():
            eid = sal_id_e.text().strip()
            amt = sal_amt_e.text().strip()
            effective_from_display = sal_effective_e.text().strip()
            note = sal_note_e.text().strip()
            if not eid or not amt:
                sal_msg_l.setText("Employee ID and salary amount are required.")
                sal_msg_l.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            try:
                effective_from = parse_display_date(effective_from_display)
            except ValueError:
                sal_msg_l.setText("Effective date must be in DD/MM/YY format.")
                sal_msg_l.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            try:
                amount_label = f"Rs. {float(amt):,.2f}"
            except ValueError:
                amount_label = amt
            if not confirm_popup(
                self,
                "Save Salary Revision",
                f"Save salary revision of {amount_label} for Emp ID {eid} effective {display_date(effective_from)}?"
            ):
                return
            ok2, msg2 = set_basic_salary(eid, amt, effective_from, note)
            sal_msg_l.setText(msg2)
            sal_msg_l.setStyleSheet(f"color:{SUCCESS if ok2 else DANGER};font-size:12px;")
            if ok2:
                sal_amt_e.clear()
                sal_note_e.clear()
                _reload()



        sal_btn.clicked.connect(_do_set_salary)
        sal_id_e.returnPressed.connect(_reload_salary_history)

        # Month picker
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        month_cb = QComboBox()
        month_cb.addItems(month_names)
        month_cb.setCurrentIndex(_dt.today().month - 1)
        month_cb.setFixedHeight(38)
        month_cb.setFixedWidth(130)
        month_cb.setStyleSheet(combo_box_style(14))
        year_e = make_entry("Year", width=82)
        year_e.setText(str(_dt.today().year))

        def _selected_year_month():
            year = year_e.text().strip()
            if not (year.isdigit() and len(year) == 4):
                return None
            return f"{year}-{month_cb.currentIndex() + 1:02d}"

        def _selected_month_label():
            return f"{month_cb.currentText()} {year_e.text().strip()}"

        def _selected_ot_rules():
            return OT_MULTIPLIER, MIN_OVERTIME_AFTER_SHIFT_MINUTES

        hdr_row.addSpacing(10); hdr_row.addWidget(make_label("Month:", 12, TEXT2))
        hdr_row.addSpacing(6); hdr_row.addWidget(month_cb)
        hdr_row.addSpacing(6); hdr_row.addWidget(year_e)
        export_btn = QPushButton("Export CSV")
        export_btn.setFixedHeight(38); export_btn.setFixedWidth(110)
        export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        export_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT}; color:#fff; border:none;
                           border-radius:6px; font-size:14px; font-weight:700; padding:0 12px; }}
            QPushButton:hover {{ background:#374151; }}
        """)
        hdr_row.addSpacing(6); hdr_row.addWidget(export_btn)
        lay.addLayout(hdr_row)
        lay.addSpacing(10); lay.addWidget(divider()); lay.addSpacing(10)
        lay.addWidget(sal_card); lay.addSpacing(10)
        export_lbl = make_label("", 12, SUCCESS)
        lay.addWidget(export_lbl)
        lay.addSpacing(6)

        # Rules reminder
        rule_card = QFrame()
        rule_card.setStyleSheet(f"QFrame {{ background:{BG3}; border:1px solid {BORDER}; border-radius:8px; }}")
        rl = QHBoxLayout(rule_card); rl.setContentsMargins(16,10,16,10); rl.setSpacing(30)
        for txt in [
            f"Late Deduction: per-minute rate x late minutes",
            "Overtime: uses OT x and OT after min inputs",
            "Payroll Cycle: selected calendar month",
        ]:
            rl.addWidget(make_label(txt, 12, TEXT2))
        rl.addStretch()
        lay.addWidget(rule_card); lay.addSpacing(12)

        # Summary cards row (totals)
        summary_row = QHBoxLayout(); summary_row.setSpacing(10)
        self._sal_total_lbl   = make_label("₹0",  26, TEXT,    bold=True)
        self._sal_deduct_lbl  = make_label("₹0",  26, DANGER,  bold=True)
        self._sal_ot_lbl      = make_label("₹0",  26, SUCCESS, bold=True)
        self._sal_net_lbl     = make_label("₹0",  26, "#2980b9", bold=True)

        for num_lbl, caption in [
            (self._sal_total_lbl,  "Total Base Salary"),
            (self._sal_deduct_lbl, "Total Deductions"),
            (self._sal_ot_lbl,     "Gross Payroll"),
            (self._sal_net_lbl,    "Net Payroll"),
        ]:
            c = card_frame(8); cl = QVBoxLayout(c)
            cl.setContentsMargins(12,14,12,14); cl.setSpacing(4)
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(num_lbl)
            cl.addWidget(make_label(caption, 11, TEXT3), alignment=Qt.AlignmentFlag.AlignCenter)
            summary_row.addWidget(c)
        lay.addLayout(summary_row); lay.addSpacing(12)

        # Table
        SALARY_COLUMNS = [
            ("Emp ID", 70), ("Name", 150), ("Dept", 130), ("Shift", 90),
            ("Base Salary", 115), ("Days P", 70), ("Days A", 70), ("Half Day", 78),
            ("Missed Out", 86), ("Late Hrs", 78), ("Late Ded", 105), ("Early Ded", 105),
            ("Absent Ded", 110), ("Half Ded", 105), ("OT Hrs", 70), ("OT Pay", 100),
            ("Net Salary", 115),
        ]
        table_min_width = sum(width for _, width in SALARY_COLUMNS) + 22

        def _salary_cell(text, size, color, bold=False, width=90):
            l = make_label(str(text), size, color, bold=bold)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setFixedWidth(width)
            l.setMinimumHeight(28)
            l.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return l


        def _show_salary_breakdown(summary):
            dlg = QDialog(self)
            dlg.setWindowTitle("Salary Breakdown")
            dlg.setModal(True)
            dlg.setMinimumSize(460, 420)
            dlg.setStyleSheet(popup_stylesheet())
            dl = QVBoxLayout(dlg); dl.setContentsMargins(18,18,18,18); dl.setSpacing(10)
            dl.addWidget(make_label(f"Salary Breakdown - {summary.get('name', '-')}", 16, TEXT, bold=True))
            dl.addWidget(make_label(f"Employee ID: {summary.get('emp_id', '-')}    Month: {summary.get('month', '-')}", 12, TEXT3))

            def money(value):
                try:
                    return f"Rs. {float(value):,.2f}"
                except (TypeError, ValueError):
                    return "Rs. 0.00"

            def add_line(label, value, color=TEXT2, prefix=""):
                row = QHBoxLayout(); row.setSpacing(8)
                row.addWidget(make_label(label, 12, color))
                row.addStretch()
                amount = value if isinstance(value, str) else prefix + money(value)
                row.addWidget(make_label(amount, 12, color, bold=True))
                dl.addLayout(row)


            add_line("Base Salary", summary.get("basic_salary", 0), TEXT)
            add_line("Overtime Pay", summary.get("ot_pay", 0), SUCCESS, "+")

            add_line("Gross Salary", summary.get("gross_salary", summary.get("basic_salary", 0)), SUCCESS)

            if summary.get("has_basic_salary"):
                add_line("Attendance Deductions", summary.get("attendance_deductions", 0), DANGER, "-")
                add_line("Total Deductions", summary.get("total_deductions", 0), DANGER, "-")
            else:
                add_line("Attendance Deductions", "---", TEXT3)
                add_line("Total Deductions", "---", TEXT3)
            if summary.get("has_basic_salary"):
                add_line("Net Salary", summary.get("net_salary", 0), TEXT)
            else:
                add_line("Net Salary", "---", TEXT3)

            btn_row = QHBoxLayout(); btn_row.addStretch()
            close_b = make_button("Close", height=36); close_b.setFixedWidth(100)
            close_b.clicked.connect(dlg.accept)
            btn_row.addWidget(close_b)
            dl.addLayout(btn_row)
            dlg.exec()

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hdr.setMinimumWidth(table_min_width)
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(8,10,8,10); hl.setSpacing(0)
        for c, width in SALARY_COLUMNS:
            hl.addWidget(_salary_cell(c, 11, TEXT3, bold=True, width=width))

        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_w.setMinimumWidth(table_min_width)
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)

        header_scroll = make_scroll(hdr)
        header_scroll.setFixedHeight(60)
        header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(header_scroll)

        scroll = make_scroll(rows_w)
        scroll.setMinimumHeight(120)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.horizontalScrollBar().valueChanged.connect(header_scroll.horizontalScrollBar().setValue)
        header_scroll.horizontalScrollBar().valueChanged.connect(scroll.horizontalScrollBar().setValue)
        lay.addWidget(scroll, 1)

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)

            ym = _selected_year_month()
            if not ym:
                rows_l.addWidget(make_label("Enter a valid 4-digit year.", 12, DANGER))
                return
            rules = _selected_ot_rules()
            if not rules:
                rows_l.addWidget(make_label("Enter valid OT multiplier and OT minutes.", 12, DANGER))
                return
            ot_multiplier, min_ot_minutes = rules
            summaries = get_all_salary_summaries(
                ym,
                ot_multiplier=ot_multiplier,
                min_ot_minutes=min_ot_minutes,
            )
            summaries.sort(key=lambda s: int(s["emp_id"]) if str(s["emp_id"]).isdigit() else 0)
            export_lbl.setText("Preview generated. Use Export CSV to save salary records.")
            export_lbl.setStyleSheet(f"color:{TEXT3};font-size:12px;")

            total_base   = sum(s["basic_salary"] for s in summaries)
            total_deduct = sum(s.get("total_deductions", 0) for s in summaries if s.get("has_basic_salary"))
            total_ot     = sum(s.get("gross_salary", 0) for s in summaries)
            total_net    = sum(s["net_salary"] for s in summaries)

            self._sal_total_lbl.setText(f"₹{total_base:,.0f}")
            self._sal_deduct_lbl.setText(f"₹{total_deduct:,.2f}")
            self._sal_ot_lbl.setText(f"₹{total_ot:,.2f}")
            self._sal_net_lbl.setText(f"₹{total_net:,.2f}")

            for i, s in enumerate(summaries):
                net_color = SUCCESS if s["net_salary"] >= s["basic_salary"] else (DANGER if s["net_salary"] < s["basic_salary"] * 0.9 else TEXT)
                row = QWidget()
                row.setStyleSheet(f"background: {'#faf7f2' if i%2==0 else '#f5f0e8'}; border:1px solid {BORDER}; border-radius:5px;")
                row.setMinimumHeight(46)
                row.setMinimumWidth(table_min_width)
                rl = QHBoxLayout(row); rl.setContentsMargins(8,10,8,10); rl.setSpacing(0)
                has_salary = bool(s.get("has_basic_salary"))

                def _money_or_blank(field):
                    if not has_salary:
                        return "---", TEXT3
                    value = float(s.get(field, 0) or 0)
                    return f"₹{value:,.2f}", DANGER if value > 0 else TEXT3

                late_ded = _money_or_blank("late_deduction")
                early_ded = _money_or_blank("early_exit_deduction")
                absent_ded = _money_or_blank("absent_deduction")
                half_ded = _money_or_blank("halfday_deduction")
                row_values = [
                    (s["emp_id"], TEXT2),
                    (s["name"], TEXT),
                    (s["department"], TEXT2),
                    (s["shift"], TEXT2),
                    (f"₹{s['basic_salary']:,.0f}" if has_salary else "---", TEXT if has_salary else TEXT3),
                    (str(s["days_present"]), SUCCESS),
                    (str(s["days_absent"]), DANGER),
                    (str(s.get("days_halfday", 0)), "#f0a500" if s.get("days_halfday", 0) > 0 else TEXT3),
                    (str(s.get("missed_checkouts", 0)), DANGER if s.get("missed_checkouts", 0) > 0 else TEXT3),
                    (str(s.get("total_late_hours", 0)), "#f0a500" if s.get("total_late_hours", 0) > 0 else TEXT3),
                    late_ded,
                    early_ded,
                    absent_ded,
                    half_ded,
                    (str(s["total_ot_hours"]), SUCCESS if s["total_ot_hours"] > 0 else TEXT3),
                    (f"₹{s['ot_pay']:,.2f}" if has_salary else "---", SUCCESS if s["ot_pay"] > 0 else TEXT3),
                    (f"₹{s['net_salary']:,.2f}" if has_salary else "---", net_color if has_salary else TEXT3),
                ]
                for idx, ((val, clr), (_, width)) in enumerate(zip(row_values, SALARY_COLUMNS)):
                    if idx == len(SALARY_COLUMNS) - 1:
                        net_btn = QPushButton(str(val))
                        net_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                        net_btn.setFixedWidth(width)
                        net_btn.setMinimumHeight(28)
                        net_btn.setStyleSheet(f"QPushButton {{ background:transparent; color:{clr}; border:none; font-size:12px; font-weight:700; text-decoration: underline; }} QPushButton:hover {{ color:{ACCENT}; }}")
                        net_btn.clicked.connect(lambda checked=False, summary=s: _show_salary_breakdown(summary))
                        rl.addWidget(net_btn)
                    else:
                        rl.addWidget(_salary_cell(val, 12, clr, width=width))
                rows_l.addWidget(row)

        def _export_csv():
            ym = _selected_year_month()
            if not ym:
                export_lbl.setText("Error: Enter a valid 4-digit year.")
                export_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            rules = _selected_ot_rules()
            if not rules:
                export_lbl.setText("Error: Enter valid OT multiplier and OT minutes.")
                export_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            ot_multiplier, min_ot_minutes = rules
            summaries = get_all_salary_summaries(
                ym,
                ot_multiplier=ot_multiplier,
                min_ot_minutes=min_ot_minutes,
            )
            if not confirm_popup(
                self,
                "Export Salary Report",
                f"Export and save salary report for {_selected_month_label()}?"
            ):
                return

            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Salary Report",
                f"salary_report_{month_cb.currentText()}_{year_e.text().strip()}.csv",
                "CSV files (*.csv)"
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"

            fields = [
                "month", "period_start", "period_end",
                "emp_id", "name", "department", "shift",
                "has_basic_salary", "basic_salary", "gross_salary", "attendance_deductions", "total_deductions",
                "payroll_days", "working_days", "paid_leave_days", "unpaid_leave_days",
                "days_present", "days_absent", "days_halfday", "missed_checkouts",
                "days_late", "total_late_hours", "total_late_minutes", "total_early_minutes",
                "late_deduction", "early_exit_deduction", "absent_deduction",
                "halfday_deduction", "total_ot_hours", "ot_multiplier", "min_ot_minutes", "ot_pay", "net_salary",
            ]
            rows = []
            deduction_fields = {
                "basic_salary", "gross_salary", "attendance_deductions", "total_deductions",
                "late_deduction", "early_exit_deduction", "absent_deduction",
                "halfday_deduction", "ot_pay", "net_salary",
            }
            for s in summaries:
                row = {field: s.get(field, "") for field in fields}
                if not s.get("has_basic_salary"):
                    for field in deduction_fields:
                        row[field] = ""
                rows.append(row)

            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                saved_count = save_salary_summaries(ym, summaries, generated_by=self.username)
                export_lbl.setText(f"Exported {len(rows)} salary records to {os.path.basename(path)} and saved {saved_count} to database.")
                export_lbl.setStyleSheet(f"color:{SUCCESS};font-size:12px;")
            except Exception as e:
                export_lbl.setText(f"Export failed: {e}")
                export_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")

        month_cb.currentIndexChanged.connect(lambda _: _reload())
        year_e.editingFinished.connect(_reload)
        export_btn.clicked.connect(_export_csv)
        _reload()
        return page

    # Daily Report
    def _page_daily_report(self):
        import csv, os
        from auth_model import get_daily_report
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)

        hdr_row = QHBoxLayout()
        lc = QVBoxLayout()
        lc.addWidget(make_label("Daily Report", 20, TEXT, bold=True))
        selected_date_lbl = make_label("", 13, TEXT3)
        lc.addWidget(selected_date_lbl)
        hdr_row.addLayout(lc); hdr_row.addStretch()

        date_filter = QDateEdit(QDate.currentDate())
        date_filter.setCalendarPopup(True)
        date_filter.setDisplayFormat("dd/MM/yy")
        date_filter.setMaximumDate(QDate.currentDate())
        date_filter.setFixedSize(110, 36)
        date_filter.setStyleSheet(f"""
            QDateEdit {{
                background: {ENTRY_BG};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            QDateEdit:focus {{ border: 1.5px solid {ACCENT}; }}
            QDateEdit::drop-down {{
                border: none;
                width: 0;
            }}
        """)
        daily_calendar_style = f"""
            QCalendarWidget {{
                background-color: #0f1115;
                color: #f8f5ef;
                border: 1px solid #2b313d;
                border-radius: 10px;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: #111827;
                border-bottom: 1px solid #2b313d;
            }}
            QCalendarWidget QToolButton {{
                background-color: #111827;
                color: #f8f5ef;
                border: none;
                border-radius: 6px;
                padding: 6px 8px;
                font-weight: 600;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: #1f2937;
            }}
            QCalendarWidget QSpinBox {{
                background-color: #111827;
                color: #f8f5ef;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QCalendarWidget QAbstractItemView {{
                background-color: #0f1115;
                alternate-background-color: #111827;
                color: #f8f5ef;
                gridline-color: #2b313d;
                selection-background-color: #f8f5ef;
                selection-color: #0f1115;
                outline: 0;
            }}
        """
        date_calendar = date_filter.calendarWidget()
        date_calendar.setGridVisible(True)
        date_calendar.setStyleSheet(daily_calendar_style)
        hdr_row.addWidget(date_filter)
        date_filter_btn = make_calendar_button(
            height=36,
            width=40,
            tooltip="Pick report date",
        )
        hdr_row.addWidget(date_filter_btn)
        hdr_row.addSpacing(6)

        today_btn = QPushButton("Today"); today_btn.setFixedSize(72, 36)
        today_btn.setStyleSheet(f"""
            QPushButton {{ background:{BG3}; color:{TEXT}; border:1px solid {BORDER};
                           border-radius:6px; font-size:14px; font-weight:600; }}
            QPushButton:hover {{ background:{BG2}; }}
        """)
        hdr_row.addWidget(today_btn)
        hdr_row.addSpacing(6)

        export_btn = QPushButton("Export CSV"); export_btn.setFixedHeight(36)
        export_btn.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: {TEXT}; border: 1px solid {BORDER};
                           border-radius: 6px; font-size: 14px; font-weight: 600; padding: 0 14px; }}
            QPushButton:hover {{ background: {BG2}; }}
        """)
        hdr_row.addWidget(export_btn)
        lay.addLayout(hdr_row)
        lay.addSpacing(12); lay.addWidget(divider()); lay.addSpacing(12)
        export_lbl = make_label("", 12, SUCCESS); lay.addWidget(export_lbl)

        summary_title = make_label("Daily Summary", 14, TEXT, bold=True)
        lay.addWidget(summary_title)
        lay.addSpacing(8)

        DAILY_COLUMNS = [
            ("ID", 70), ("Name", 155), ("Dept", 120), ("Shift", 110), ("Status", 130),
            ("Check-In", 105), ("Check-Out", 105), ("Hours", 78), ("Late Hrs", 82),
            ("OT Hrs", 78), ("Marked By", 105),
        ]
        daily_table_width = sum(width for _, width in DAILY_COLUMNS) + 22
        STATUS_CLR = {
            "Present": SUCCESS, "present": SUCCESS,
            "Late": "#f0a500",
            "Half-Day": "#3498db",
            "Absent": DANGER, "absent": DANGER,
            "Approved Leave": "#2980b9",
            "Paid Holiday": "#2980b9",
            "Missed Checkout": DANGER,
            "Not Marked": TEXT3,
        }

        def _daily_cell(text, size, color, bold=False, width=90):
            l = make_label(str(text), size, color, bold=bold)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setFixedWidth(width)
            l.setMinimumHeight(28)
            l.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return l

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hdr.setMinimumWidth(daily_table_width)
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(8,8,8,8); hl.setSpacing(0)
        for c, width in DAILY_COLUMNS:
            hl.addWidget(_daily_cell(c, 11, TEXT3, bold=True, width=width))
        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_w.setMinimumWidth(daily_table_width)
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        table_box, _, _ = make_sticky_table_scroll(hdr, rows_w, rows_height=208, header_height=46)
        lay.addWidget(table_box)
        lay.addStretch()

        def _selected_date():
            return qdate_iso(date_filter.date())

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            selected = _selected_date()
            selected_date_lbl.setText(f"Selected date: {display_date(selected)}")
            summary_title.setText(f"Summary for {display_date(selected)}")
            export_lbl.clear()
            report = get_daily_report(selected)
            if not report:
                rows_l.addWidget(make_label("No employees found.", 12, TEXT3)); return
            report.sort(key=lambda r: int(r["id"]) if str(r["id"]).isdigit() else 0)
            for rec in report:
                status = rec["status"]
                row = QWidget()
                row.setStyleSheet(f"background: {BG3}; border: 1px solid {BORDER}; border-radius: 6px;")
                row.setMinimumWidth(daily_table_width)
                row.setMinimumHeight(46)
                rl  = QHBoxLayout(row); rl.setContentsMargins(8,8,8,8); rl.setSpacing(0)
                vals = [
                    (rec["id"], TEXT2),
                    (rec["name"], TEXT),
                    (rec.get("department", "N/A"), TEXT2),
                    (rec.get("shift", "N/A"), TEXT2),
                    (status, STATUS_CLR.get(status, TEXT)),
                    (rec.get("checkin_time", "-"), TEXT2),
                    (rec.get("checkout_time", "-"), TEXT2),
                    (rec.get("hours_worked", 0), TEXT2),
                    (rec.get("late_hours", 0), "#f0a500" if rec.get("late_hours", 0) else TEXT3),
                    (rec.get("overtime_hours", 0), SUCCESS if rec.get("overtime_hours", 0) else TEXT3),
                    (rec.get("marked_by", "-"), TEXT3),
                ]
                for (val, clr), (_, width) in zip(vals, DAILY_COLUMNS):
                    rl.addWidget(_daily_cell(val, 12, clr, width=width))
                rows_l.addWidget(row)

        def do_export():
            selected = _selected_date()
            report = get_daily_report(selected)
            if not report:
                export_lbl.setText("Error: No data to export."); export_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;"); return
            file_date = date_filter.date().toString("dd-MM-yy")
            path, _ = QFileDialog.getSaveFileName(self, "Export Daily Report", f"daily_report_{file_date}.csv", "CSV files (*.csv)")
            if not path: return
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        "id", "name", "department", "shift", "status",
                        "checkin_time", "checkout_time", "hours_worked",
                        "late_hours", "overtime_hours", "marked_by", "missed_checkout"
                    ])
                    writer.writeheader(); writer.writerows(report)
                export_lbl.setText(f"Exported {len(report)} records to {os.path.basename(path)}")
                export_lbl.setStyleSheet(f"color:{SUCCESS};font-size:12px;")
            except Exception as e:
                export_lbl.setText(f"Export failed: {e}"); export_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")

        def _show_today():
            if date_filter.date() == QDate.currentDate():
                _reload()
            else:
                date_filter.setDate(QDate.currentDate())

        def _open_date_filter_calendar():
            dlg = QDialog(self)
            dlg.setModal(True)
            dlg.setWindowTitle("Select Report Date")
            dlg.setFixedSize(360, 400)
            dlg.setStyleSheet("background-color: #0f1115; color: #f8f5ef;")

            dlay = QVBoxLayout(dlg)
            dlay.setContentsMargins(14, 14, 14, 14)
            dlay.setSpacing(10)

            cal = QCalendarWidget()
            cal.setGridVisible(True)
            cal.setMaximumDate(QDate.currentDate())
            cal.setSelectedDate(date_filter.date())
            cal.setStyleSheet(daily_calendar_style)
            dlay.addWidget(cal)

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(34)
            cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #f8f5ef;
                    border: 1px solid #374151;
                    border-radius: 7px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background: #1f2937;
                }
            """)
            select_btn = QPushButton("Select")
            select_btn.setFixedHeight(34)
            select_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            select_btn.setStyleSheet("""
                QPushButton {
                    background: #f8f5ef;
                    color: #111827;
                    border: none;
                    border-radius: 7px;
                    font-size: 13px;
                    font-weight: 700;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background: #ede8df;
                }
            """)
            cancel_btn.setFixedWidth(90)
            select_btn.setFixedWidth(90)
            cancel_btn.clicked.connect(dlg.reject)
            select_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(select_btn)
            dlay.addLayout(btn_row)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                date_filter.setDate(cal.selectedDate())

        date_filter.dateChanged.connect(lambda _: _reload())
        date_filter_btn.clicked.connect(_open_date_filter_calendar)
        today_btn.clicked.connect(_show_today)
        export_btn.clicked.connect(do_export)
        _reload()
        return page

    # Leave Requests
    def _page_leave_requests(self):
        from auth_model import get_leave_requests, update_leave_request
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Leave Requests",                       20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Approve or reject employee leave requests", 13, TEXT3))
        lay.addSpacing(10); lay.addWidget(divider()); lay.addSpacing(10)

        action_lbl = make_label("", 12, SUCCESS); lay.addWidget(action_lbl)
        lay.addSpacing(4)

        filter_row = QHBoxLayout(); filter_row.setSpacing(8)
        STATUS_CLR = {"Pending": "#f0a500", "Approved": SUCCESS, "Rejected": DANGER, "Reverted": TEXT3, "Revert Requested": "#2980b9"}
        self._lr_filter = "All"
        filter_btns = {}
        _lr_pill_colors = {"All": TEXT2, "Pending": "#f0a500", "Approved": SUCCESS, "Rejected": DANGER, "Reverted": TEXT3, "Revert Requested": "#2980b9"}
        def _lr_pill_ss(val, active):
            clr = _lr_pill_colors[val]
            return (
                f"QPushButton {{ background: {clr}; color: #fff; border: 1px solid {clr};"
                f" border-radius: 6px; font-size: 12px; font-weight: 700; padding: 2px 14px; }}"
                if active else
                f"QPushButton {{ background: {BG3}; color: {clr}; border: 1px solid {clr};"
                f" border-radius: 6px; font-size: 12px; font-weight: 600; padding: 2px 14px; }}"
                f" QPushButton:hover {{ background: {BG2}; }}"
            )
        for status_val in ["All", "Pending", "Approved", "Rejected", "Reverted", "Revert Requested"]:
            fb = QPushButton(status_val); fb.setFixedHeight(28)
            fb.setStyleSheet(_lr_pill_ss(status_val, status_val == "All"))
            fb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            filter_btns[status_val] = fb
            filter_row.addWidget(fb)
        filter_row.addStretch()
        filter_widget = QWidget(); filter_widget.setLayout(filter_row)
        lay.addWidget(filter_widget); lay.addSpacing(8)

        type_row = QWidget(); type_row.setStyleSheet("background: transparent;")
        tr = QHBoxLayout(type_row); tr.setContentsMargins(0,0,0,0); tr.setSpacing(8)
        tr.addWidget(make_label("Leave Type:", 12, TEXT2))
        self._lr_type_filter = "All"
        self._lr_type_cb = QComboBox()
        self._lr_type_cb.addItems(["All", "Sick Leave", "Casual Leave", "Annual Leave", "Other"])
        self._lr_type_cb.setFixedHeight(32)
        self._lr_type_cb.setStyleSheet(combo_box_style(13))
        tr.addWidget(self._lr_type_cb)
        tr.addStretch()
        lay.addWidget(type_row)
        lay.addSpacing(8)

        LEAVE_COLUMNS = [
            ("ID", 64), ("Name", 150), ("Type", 112), ("Duration", 100),
            ("From", 104), ("To", 104), ("Days", 62), ("Reason", 240),
            ("Submitted", 108), ("Status", 96), ("Action", 174),
        ]
        leave_table_width = sum(width for _, width in LEAVE_COLUMNS) + 22

        def _leave_cell(text, size=12, color=TEXT, bold=False, width=90, align=Qt.AlignmentFlag.AlignCenter):
            lbl = make_label(str(text), size, color, bold=bold)
            lbl.setAlignment(align)
            lbl.setFixedWidth(width)
            lbl.setMinimumHeight(30)
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            lbl.setToolTip(str(text))
            return lbl

        def _show_leave_reason(reason, employee_name):
            show_text_popup(self, "Leave Reason", f"Reason from {employee_name}", reason)

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hdr.setMinimumWidth(leave_table_width)
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(8,9,8,9); hl.setSpacing(0)
        for c, width in LEAVE_COLUMNS:
            hl.addWidget(_leave_cell(c, 11, TEXT3, bold=True, width=width))

        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_w.setMinimumWidth(leave_table_width)
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        table_box, _, _ = make_sticky_table_scroll(hdr, rows_w, rows_height=420, header_height=52)
        lay.addWidget(table_box); lay.addStretch()

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            flt     = self._lr_filter
            type_flt = self._lr_type_cb.currentText()
            records = get_leave_requests()
            if flt != "All":
                records = [r for r in records if r["status"] == flt]
            if type_flt != "All":
                records = [r for r in records if r.get("leave_type", "") == type_flt]
            if not records:
                rows_l.addWidget(make_label("No requests found.", 12, TEXT3)); return
            for i, req in enumerate(records):
                row = QWidget()
                row.setStyleSheet(f"background: {'#faf7f2' if i%2==0 else '#f5f0e8'}; border: 1px solid {BORDER}; border-radius: 5px;")
                row.setMinimumHeight(52)
                row.setMinimumWidth(leave_table_width)
                rl  = QHBoxLayout(row); rl.setContentsMargins(8,9,8,9); rl.setSpacing(0)
                status = req["status"]; s_color = STATUS_CLR.get(status, TEXT)
                leave_reason = str(req.get("reason") or "N/A")
                revert_reason = str(req.get("revert_reason") or "").strip()
                reason_text = (
                    f"Leave Reason:\n{leave_reason}\n\nRevert Reason:\n{revert_reason}"
                    if revert_reason else leave_reason
                )
                for (val, clr, align), (col_name, width) in zip([
                    (req["emp_id"], TEXT2, Qt.AlignmentFlag.AlignCenter),
                    (req["emp_name"], TEXT, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    (req["leave_type"], TEXT2, Qt.AlignmentFlag.AlignCenter),
                    (req.get("leave_duration", "Full Day"), TEXT2, Qt.AlignmentFlag.AlignCenter),
                    (display_date(req["from_date"]), TEXT, Qt.AlignmentFlag.AlignCenter),
                    (display_date(req["to_date"]), TEXT, Qt.AlignmentFlag.AlignCenter),
                    (req["days"], TEXT, Qt.AlignmentFlag.AlignCenter),
                    (leave_reason if not revert_reason else f"{leave_reason} | Revert: {revert_reason}", TEXT2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    (display_date(req["submitted_on"]), TEXT3, Qt.AlignmentFlag.AlignCenter),
                    (status, s_color, Qt.AlignmentFlag.AlignCenter),
                ], LEAVE_COLUMNS[:-1]):
                    if col_name == "Reason":
                        reason_w = QWidget()
                        reason_w.setFixedWidth(width)
                        reason_w.setMinimumHeight(30)
                        reason_w.setStyleSheet("background: transparent; border: none;")
                        rw_l = QHBoxLayout(reason_w)
                        rw_l.setContentsMargins(0, 0, 0, 0)
                        rw_l.setSpacing(4)
                        reason_lbl = _leave_cell(short_text(val, 28), 12, clr, width=width - 68, align=align)
                        reason_lbl.setToolTip(str(val))
                        rw_l.addWidget(reason_lbl)
                        rw_l.addWidget(make_detail_button(
                            self,
                            "Leave Reason",
                            f"Reasons from {req['emp_name']}" if revert_reason else f"Reason from {req['emp_name']}",
                            reason_text,
                            tooltip="View full leave reason",
                        ))
                        rl.addWidget(reason_w)
                    else:
                        cell = _leave_cell(val, 12, clr, width=width, align=align)
                        rl.addWidget(cell)

                act = QWidget()
                act.setFixedWidth(LEAVE_COLUMNS[-1][1])
                ab  = QHBoxLayout(act); ab.setContentsMargins(0,0,0,0); ab.setSpacing(6)
                ab.setAlignment(Qt.AlignmentFlag.AlignCenter)

                def _action_button(text, bg, fg="#ffffff", border=None, width=76):
                    btn = QPushButton(text)
                    btn.setFixedSize(width, 30)
                    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    border_css = border or bg
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background:{bg};
                            color:{fg};
                            border:1px solid {border_css};
                            border-radius:5px;
                            font-size:12px;
                            font-weight:800;
                        }}
                        QPushButton:hover {{ background:{BG}; color:{TEXT}; }}
                    """)
                    return btn

                if status == "Pending":
                    rid = req["request_id"]
                    r_btn = _action_button("Reject", DANGER, "#ffffff", DANGER, 72)
                    can_approve = True
                    try:
                        can_approve = _dt.strptime(str(req.get("from_date", ""))[:10], "%Y-%m-%d").date() > _dt.today().date()
                    except ValueError:
                        can_approve = False
                    if can_approve:
                        a_btn = _action_button("Approve", SUCCESS, "#ffffff", SUCCESS, 78)
                        a_btn.clicked.connect(lambda _, r=rid: _do_action(r, "Approved"))
                    else:
                        a_btn = _action_button("Expired", TEXT3, "#ffffff", TEXT3, 78)
                        a_btn.setEnabled(False)
                        a_btn.setToolTip("Past or same-day leave requests cannot be approved.")
                    r_btn.clicked.connect(lambda _, r=rid: _do_action(r, "Rejected"))
                    ab.addWidget(a_btn); ab.addWidget(r_btn)
                elif status == "Approved" and req.get("can_revert", False):
                    rid = req["request_id"]
                    rev_btn = _action_button("Revert", BG3, TEXT2, BORDER, 78)
                    rev_btn.clicked.connect(lambda _, r=rid: _do_action(r, "Reverted"))
                    ab.addWidget(rev_btn)
                elif status == "Revert Requested" and req.get("can_revert", False):
                    rid = req["request_id"]
                    approve_rev_btn = _action_button("Revert", SUCCESS, "#ffffff", SUCCESS, 78)
                    deny_rev_btn = _action_button("Deny", DANGER, "#ffffff", DANGER, 66)
                    approve_rev_btn.clicked.connect(lambda _, r=rid: _do_action(r, "Reverted"))
                    deny_rev_btn.clicked.connect(lambda _, r=rid: _do_action(r, "Revert Rejected"))
                    ab.addWidget(approve_rev_btn); ab.addWidget(deny_rev_btn)
                elif status == "Revert Requested":
                    rid = req["request_id"]
                    deny_rev_btn = _action_button("Deny", DANGER, "#ffffff", DANGER, 66)
                    deny_rev_btn.clicked.connect(lambda _, r=rid: _do_action(r, "Revert Rejected"))
                    ab.addWidget(deny_rev_btn)
                else:
                    ab.addWidget(_leave_cell("No action", 11, TEXT3, width=LEAVE_COLUMNS[-1][1]))
                rl.addWidget(act)
                rows_l.addWidget(row)

        def _do_action(req_id, action):
            if action in ("Approved", "Rejected", "Reverted", "Revert Rejected"):
                confirm = confirm_popup(
                    self,
                    f"Confirm {action}",
                    f"Are you sure you want to {action.lower()} this leave request?"
                )
                if not confirm:
                    return
            remarks = ""
            if action in ("Rejected", "Reverted", "Revert Rejected"):
                title = "Reason Required"
                label = f"Enter reason for {action.lower()} this leave request:"
                dlg = QInputDialog(self)
                dlg.setWindowTitle(title)
                dlg.setLabelText(label)
                dlg.setInputMode(QInputDialog.InputMode.TextInput)
                dlg.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput, True)
                dlg.setStyleSheet(f"""
                    QInputDialog {{
                        background-color: {BG3};
                        color: {TEXT};
                    }}
                    QLabel {{
                        color: {TEXT};
                        font-size: 13px;
                        font-weight: 700;
                        background: transparent;
                    }}
                    QTextEdit, QPlainTextEdit, QLineEdit {{
                        background: {ENTRY_BG};
                        color: {TEXT};
                        border: 1px solid {BORDER};
                        border-radius: 6px;
                        padding: 8px;
                        font-size: 13px;
                        selection-background-color: {ACCENT};
                        selection-color: #ffffff;
                    }}
                    QPushButton {{
                        background: {ACCENT};
                        color: #ffffff;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-weight: 700;
                        min-width: 72px;
                    }}
                    QPushButton:hover {{
                        background: #374151;
                    }}
                """)
                accepted = dlg.exec() == QDialog.DialogCode.Accepted
                remarks = dlg.textValue().strip()
                if not accepted:
                    return
                if not remarks:
                    action_lbl.setText("Reason is required."); action_lbl.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
                    return
            ok, msg = update_leave_request(req_id, action, remarks, reviewed_by=self.username)
            action_lbl.setText(msg); action_lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 12px;")
            _reload()

        def _set_filter(val):
            self._lr_filter = val
            for v, b in filter_btns.items():
                b.setStyleSheet(_lr_pill_ss(v, v == val))
            _reload()

        for val, fb in filter_btns.items():
            fb.clicked.connect(lambda _, v=val: _set_filter(v))
        self._lr_type_cb.currentIndexChanged.connect(lambda _: _reload())

        _reload()
        return page


# ----------------------------------------------------------------------
#  EMPLOYEE DASHBOARD
# ----------------------------------------------------------------------
class EmployeeDashboard(QWidget):
    def __init__(self, controller, username):
        super().__init__()
        self.controller = controller
        self.username   = username
        self.setStyleSheet(f"background: {BG};")
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._feature_items = [
            ("profile",       "SP_FileDialogDetailedView", "My Profile", "My Profile"),
            ("attendance",    "SP_FileDialogListView",     "My Attendance", "My Attendance"),
            ("monthly_report", "SP_FileDialogContentsView", "Monthly Report", "Monthly Report"),
            ("leaves",        "SP_DialogApplyButton",      "My Leaves",     "My Leaves"),
            ("request_leave", "SP_MessageBoxInformation",  "Request Leave", "Request Leave"),
            ("password",      "SP_DialogResetButton",      "Change Password", "Change Password"),
        ]
        nav_items = [
            ("dashboard",     "aSz", "Dashboard"),
        ]
        self._sidebar = Sidebar(nav_items, self._show_page, self.controller.show_login, "MY ACCOUNT")
        lay.addWidget(self._sidebar)

        self._stack = SlidingStack()
        self._stack.setStyleSheet(f"background: {BG2};")
        lay.addWidget(self._stack)

        self._pages = {}
        self._sidebar.select("dashboard")

    def _show_page(self, key):
        # BUG FIX: always rebuild salary_report so updated basic salaries are never stale
        if key == "salary_report" and key in self._pages:
            old = self._pages.pop(key)
            self._stack.removeWidget(old)
            old.deleteLater()
        if key not in self._pages:
            page = self._build_page(key)
            self._pages[key] = page
            self._stack.addWidget(page)
        self._stack.slide_to(self._pages[key])

    def _build_page(self, key):
        return {
            "dashboard":     self._page_dashboard,
            "profile":       self._page_profile,
            "attendance":    self._page_attendance,
            "monthly_report": self._page_monthly_report,
            "leaves":        self._page_leaves,
            "request_leave": self._page_request_leave,
            "password":      self._page_password,
        }[key]()

    # Dashboard
    def _page_dashboard(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Dashboard", 20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label(f"Welcome back, {self.username}", 13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        def feature_button(key, icon_name, short_label, full_label):
            btn = QPushButton(short_label)
            btn.setMinimumHeight(66)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            sp = getattr(QStyle.StandardPixmap, icon_name, QStyle.StandardPixmap.SP_FileIcon)
            btn.setIcon(self.style().standardIcon(sp))
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(full_label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG3};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 700;
                    text-align: left;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {BG};
                    border: 1px solid {ACCENT};
                }}
                QPushButton::icon {{
                    padding-left: 0px;
                }}
            """)
            btn.clicked.connect(lambda _, k=key: self._show_page(k))
            return btn

        for i, (key, icon_name, short_label, full_label) in enumerate(self._feature_items):
            grid.addWidget(feature_button(key, icon_name, short_label, full_label), i // 2, i % 2)

        lay.addLayout(grid)
        lay.addStretch()
        return page

    # Profile
    def _page_profile(self):
        from auth_model import get_employee_notifications, get_unread_notification_count, mark_notification_read
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("My Profile",                       20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label(f"Logged in as: {self.username}",   13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        card = card_frame()
        cl = QHBoxLayout(card); cl.setContentsMargins(20,20,20,20)
        av = QLabel("Y"); av.setFixedSize(52,52)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet(f"background: {BG}; border: 1px solid {BORDER}; border-radius: 26px; font-size: 24px;")
        cl.addWidget(av)
        cl.addSpacing(16)
        info = QVBoxLayout()
        info.addWidget(make_label(self.username, 15, TEXT, bold=True))
        info.addWidget(make_label("Employee", 12, TEXT3))
        cl.addLayout(info); cl.addStretch()
        badge = QLabel(" Active ")
        badge.setStyleSheet("background: #1a2a1a; color: #16a34a; border-radius: 4px; font-size: 13px; font-weight: 700; padding: 3px 8px;")
        cl.addWidget(badge)
        lay.addWidget(card); lay.addSpacing(16)

        try:
            emp_id = self.controller.get_emp_id_by_username(self.username)
        except AttributeError:
            emp_id = None

        notif_card = card_frame(8)
        nl = QVBoxLayout(notif_card); nl.setContentsMargins(16,14,16,14); nl.setSpacing(8)

        def _show_notification_popup(item):
            box = QMessageBox(self)
            box.setWindowTitle(item.get("title", "Notification"))
            stamp = " ".join(part for part in [display_date(item.get("created_on", "")), item.get("created_at", "")] if part)
            box.setText(item.get("title", "Notification"))
            box.setInformativeText(f"{item.get('message', '')}\n\n{stamp}")
            box.setIcon(QMessageBox.Icon.Information)
            box.setStyleSheet(popup_stylesheet())
            box.exec()
            if not item.get("read"):
                mark_notification_read(item.get("id"), emp_id)
                _reload_notifications()

        def _reload_notifications():
            while nl.count():
                item = nl.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
                elif item.layout():
                    while item.layout().count():
                        child = item.layout().takeAt(0)
                        if child.widget():
                            child.widget().setParent(None)

            header_row = QHBoxLayout()
            header_row.addWidget(make_label("Notifications", 14, TEXT, bold=True))
            header_row.addStretch()
            unread_count = get_unread_notification_count(emp_id) if emp_id is not None else 0
            unread_lbl = QLabel(f" {unread_count} unread ")
            unread_lbl.setStyleSheet(f"""
                background: {'#fee2e2' if unread_count else BG};
                color: {DANGER if unread_count else TEXT3};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-size: 12px;
                font-weight: 800;
                padding: 3px 8px;
            """)
            header_row.addWidget(unread_lbl)
            nl.addLayout(header_row)

            notifications = get_employee_notifications(emp_id, limit=5) if emp_id is not None else []
            if notifications:
                for item in notifications:
                    item_box = QFrame()
                    item_box.setStyleSheet(f"""
                        QFrame {{
                            background: {BG if not item.get('read') else BG3};
                            border: 1px solid {BORDER};
                            border-radius: 6px;
                        }}
                    """)
                    il = QHBoxLayout(item_box); il.setContentsMargins(12,8,12,8); il.setSpacing(8)
                    text_col = QVBoxLayout(); text_col.setSpacing(3)
                    title = item.get("title", "Notification")
                    if not item.get("read"):
                        title = f"Unread: {title}"
                    text_col.addWidget(make_label(title, 12, TEXT, bold=True))
                    stamp = " ".join(part for part in [display_date(item.get("created_on", "")), item.get("created_at", "")] if part)
                    text_col.addWidget(make_label(stamp, 10, TEXT3))
                    il.addLayout(text_col); il.addStretch()

                    view_btn = make_button("View", color=BG3, text_color=TEXT, hover=BG, height=30)
                    view_btn.setFixedWidth(74)
                    view_btn.clicked.connect(lambda _, n=item: _show_notification_popup(n))
                    il.addWidget(view_btn)

                    nl.addWidget(item_box)
            else:
                nl.addWidget(make_label("No notifications yet.", 12, TEXT3))

        _reload_notifications()

        lay.addWidget(notif_card); lay.addStretch()
        return page

    # Attendance
    def _page_attendance(self):
        from datetime import date as _date
    
    

        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("My Attendance", 20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label(f"Today: {display_date(_app_today_iso())}", 13, TEXT3))
        lay.addSpacing(10)



        lay.addWidget(divider()); lay.addSpacing(14)
        STATUS_CLR = {"Present": SUCCESS, "Late": "#f0a500", "Half-Day": "#3498db", "Absent": DANGER}

        try:
            emp_id = self.controller.get_emp_id_by_username(self.username)
        except AttributeError:
            emp_id = None

        # Shift info card
        SHIFTS = {}
        SHIFT_COLORS = {}
        GRACE_MINUTES = 15
        try:
            from shift_model import get_employee_shift, SHIFTS, SHIFT_COLORS, GRACE_MINUTES
            shift_name = get_employee_shift(emp_id) if emp_id else None
        except ImportError:
            shift_name = None

        shift_card = QFrame()
        shift_card.setStyleSheet(f"QFrame {{ background:{BG3}; border:1px solid {BORDER}; border-radius:8px; }}")
        sl = QHBoxLayout(shift_card); sl.setContentsMargins(16,12,16,12); sl.setSpacing(20)
        if shift_name and shift_name in SHIFTS:
            s = SHIFTS[shift_name]
            color = SHIFT_COLORS.get(shift_name, TEXT2)
            sl.addWidget(make_label(f"Your Shift:", 12, TEXT2))
            sl.addWidget(make_label(f"  {shift_name}", 14, color, bold=True))
            sl.addWidget(make_label(f"{s['start']} to {s['end']}", 13, TEXT))
            sl.addWidget(make_label(f"{s.get('hours', '?')} hrs/day", 12, TEXT2))
            sl.addWidget(make_label(f"Grace: {GRACE_MINUTES} min", 12, TEXT3))
        else:
            sl.addWidget(make_label("Warning: No shift assigned yet. Contact your admin.", 13, "#f0a500"))
        sl.addStretch()
        lay.addWidget(shift_card); lay.addSpacing(12)

        card = card_frame()
        fl = QVBoxLayout(card); fl.setContentsMargins(20,16,20,16); fl.setSpacing(6)
        rows_data = [("Status","N/A",TEXT3),("Check-In","N/A",TEXT),("Check-Out","N/A",TEXT),("Hours Worked","N/A",TEXT),("Late Minutes","0",TEXT)]
        labels = {}
        for lbl_txt, default, clr in rows_data:
            row = QWidget(); row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
            lbl_key = QLabel(lbl_txt); lbl_key.setFixedWidth(140)
            lbl_key.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            val_lbl = make_label(default, 13, clr, bold=True)
            rl.addWidget(lbl_key); rl.addWidget(val_lbl); rl.addStretch()
            fl.addWidget(row)
            labels[lbl_txt] = val_lbl
        lay.addWidget(card); lay.addSpacing(10)

        msg_lbl = make_label("", 12, SUCCESS); lay.addWidget(msg_lbl)

        action_card = card_frame(8)
        al = QVBoxLayout(action_card); al.setContentsMargins(16,12,16,14); al.setSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        btn_in  = make_button("Check In",  color=SUCCESS,   text_color="#111", hover="#388a3c", height=40)
        btn_out = make_button("Check Out", color="#2980b9", text_color=TEXT,   hover="#1f6391", height=40)
        btn_in.setFixedWidth(190); btn_out.setFixedWidth(190)
        btn_row.addWidget(btn_in); btn_row.addWidget(btn_out); btn_row.addStretch()
        al.addLayout(btn_row)
        lay.addWidget(action_card); lay.addStretch()

        def _refresh():
            if emp_id is None:
                labels["Status"].setText("Could not resolve Employee ID")
                labels["Status"].setStyleSheet(f"color: {DANGER}; font-size: 13px; font-weight: 700;"); return
            rec = attendance.get_today_record(emp_id)
            if rec:
                st  = rec.get("status","N/A"); arr = rec.get("arrival_time") or "N/A"
                co  = rec.get("checkout_time") or "N/A"; hrs = rec.get("hours_worked"); lte = rec.get("late_minutes",0)
                labels["Status"].setText(st);           labels["Status"].setStyleSheet(f"color:{STATUS_CLR.get(st,TEXT)};font-size:13px;font-weight:700;")
                labels["Check-In"].setText(arr);        labels["Check-In"].setStyleSheet(f"color:{TEXT};font-size:13px;font-weight:700;")
                labels["Check-Out"].setText(co);        labels["Check-Out"].setStyleSheet(f"color:{TEXT};font-size:13px;font-weight:700;")
                labels["Hours Worked"].setText(f"{hrs}h" if hrs else "N/A")
                labels["Late Minutes"].setText(str(lte))
                btn_in.setEnabled(arr == "N/A")
                btn_out.setEnabled(co == "N/A" and arr != "N/A")
            else:
                labels["Status"].setText("Not marked yet"); labels["Status"].setStyleSheet(f"color:{TEXT3};font-size:13px;")
                for k in ("Check-In","Check-Out","Hours Worked"): labels[k].setText("N/A")
                labels["Late Minutes"].setText("0")
                btn_in.setEnabled(True); btn_out.setEnabled(False)

        def do_checkin():
            if emp_id is None: return
            ok, msg = attendance.mark_arrival(emp_id)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color:{SUCCESS if ok else DANGER};font-size:12px;")
            _refresh()

        def do_checkout():
            if emp_id is None: return
            ok, msg = attendance.mark_checkout(emp_id)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color:{SUCCESS if ok else DANGER};font-size:12px;")
            _refresh()

        btn_in.clicked.connect(do_checkin); btn_out.clicked.connect(do_checkout)
        _refresh()
        return page

    # Monthly Report
    def _page_monthly_report(self):
        from datetime import datetime as _dt

        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)

        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

        hdr_row = QHBoxLayout()
        lc = QVBoxLayout()
        lc.addWidget(make_label("Monthly Report", 20, TEXT, bold=True))
        lc.addWidget(make_label("Your attendance summary for a selected month", 13, TEXT3))
        hdr_row.addLayout(lc); hdr_row.addStretch()

        month_cb = QComboBox()
        month_cb.addItems(month_names)
        month_cb.setCurrentIndex(_dt.today().month - 1)
        month_cb.setFixedHeight(38)
        month_cb.setFixedWidth(132)
        month_cb.setStyleSheet(combo_box_style(14))

        year_e = make_entry("Year", width=82)
        year_e.setText(str(_dt.today().year))
        hdr_row.addWidget(make_label("Month:", 12, TEXT2))
        hdr_row.addSpacing(6); hdr_row.addWidget(month_cb)
        hdr_row.addSpacing(6); hdr_row.addWidget(year_e)
        lay.addLayout(hdr_row)
        lay.addSpacing(14); lay.addWidget(divider()); lay.addSpacing(12)

        emp_id = self.controller.get_emp_id_by_username(self.username)
        if emp_id is None:
            lay.addWidget(make_label("Error: Could not resolve your Employee ID. Contact admin.", 13, DANGER))
            lay.addStretch()
            return page

        msg_lbl = make_label("", 12, TEXT2)
        lay.addWidget(msg_lbl)
        lay.addSpacing(8)

        summary_row = QHBoxLayout(); summary_row.setSpacing(10)
        present_lbl = make_label("0", 26, SUCCESS, bold=True)
        halfday_lbl = make_label("0", 26, "#3498db", bold=True)
        absent_lbl = make_label("0", 26, DANGER, bold=True)
        pct_lbl = make_label("0%", 26, "#2980b9", bold=True)
        for num_lbl, caption in [
            (present_lbl, "Full Attendance"),
            (halfday_lbl, "Half Days"),
            (absent_lbl, "Absent/Missed"),
            (pct_lbl, "Attendance"),
        ]:
            c = card_frame(8)
            cl = QVBoxLayout(c); cl.setContentsMargins(12,14,12,14); cl.setSpacing(4)
            num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(num_lbl)
            cl.addWidget(make_label(caption, 11, TEXT3), alignment=Qt.AlignmentFlag.AlignCenter)
            summary_row.addWidget(c)
        lay.addLayout(summary_row)
        lay.addSpacing(12)

        COLS = [
            ("Date", 112), ("Status", 110), ("Check-In", 110), ("Check-Out", 110),
            ("Hours", 86), ("Late Hrs", 86), ("OT Hrs", 86),
        ]
        table_min_width = sum(width for _, width in COLS) + 22

        def _cell(text, size, color, bold=False, width=90):
            l = make_label(str(text), size, color, bold=bold)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setFixedWidth(width)
            l.setMinimumHeight(28)
            l.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return l

        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hdr.setMinimumWidth(table_min_width)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(8,10,8,10); hl.setSpacing(0)
        for c, width in COLS:
            hl.addWidget(_cell(c, 11, TEXT3, bold=True, width=width))

        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_w.setMinimumWidth(table_min_width)
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        table_box, _, _ = make_sticky_table_scroll(hdr, rows_w, rows_height=330, header_height=52)
        lay.addWidget(table_box)
        lay.addStretch()

        def _selected_month_year():
            year = year_e.text().strip()
            if not (year.isdigit() and len(year) == 4):
                return None, None
            return month_cb.currentIndex() + 1, int(year)

        def _reload():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)

            month, year = _selected_month_year()
            if month is None:
                msg_lbl.setText("Error: Enter a valid 4-digit year.")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return

            prefix = f"{year}-{month:02d}"
            report_rows = attendance.get_monthly_attendance_report(month, year)
            summary = next((r for r in report_rows if r.get("emp_id") == emp_id), None)
            if not summary:
                summary = {
                    "recorded_days": 0, "present": 0, "late": 0,
                    "half_day": 0, "absent": 0, "missed_checkout": 0,
                    "attendance_percentage": 0,
                }

            present_lbl.setText(str(summary.get("present", 0) + summary.get("late", 0)))
            halfday_lbl.setText(str(summary.get("half_day", 0)))
            absent_lbl.setText(str(
                summary.get("absent", 0) + summary.get("missed_checkout", 0)
            ))
            pct = summary.get("attendance_percentage", 0)
            pct_lbl.setText(f"{pct}%")
            pct_lbl.setStyleSheet(f"color:{SUCCESS if pct >= 90 else ('#f0a500' if pct >= 75 else DANGER)};font-size:26px;font-weight:700;background:transparent;border:none;")

            records = [
                r for r in attendance.get_attendance_by_employee(emp_id)
                if str(r.get("date", "")).startswith(prefix)
            ]
            records.sort(key=lambda r: r.get("date", ""), reverse=True)
            msg_lbl.setText(f"Showing {len(records)} records for {month_cb.currentText()} {year}.")
            msg_lbl.setStyleSheet(f"color:{TEXT2};font-size:12px;")

            if not records:
                rows_l.addWidget(make_label("No attendance records found for this month.", 12, TEXT3))
                return

            status_colors = {"Present": SUCCESS, "Late": "#f0a500", "Half-Day": "#3498db", "Absent": DANGER}
            for i, rec in enumerate(records):
                status = rec.get("status", "N/A")
                display_status = "Missed Checkout" if attendance.is_missed_checkout(rec) else status
                status_color = DANGER if display_status == "Missed Checkout" else status_colors.get(status, TEXT2)
                row = QWidget()
                row.setStyleSheet(f"background: {'#faf7f2' if i%2==0 else '#f5f0e8'}; border:1px solid {BORDER}; border-radius:5px;")
                row.setMinimumHeight(46)
                row.setMinimumWidth(table_min_width)
                rl = QHBoxLayout(row); rl.setContentsMargins(8,10,8,10); rl.setSpacing(0)
                late_hours = round(float(rec.get("late_minutes") or 0) / 60, 2)
                values = [
                    (display_date(rec.get("date", "")), TEXT2),
                    (display_status, status_color),
                    (rec.get("arrival_time") or "N/A", TEXT2),
                    (rec.get("checkout_time") or "N/A", TEXT2),
                    (rec.get("hours_worked") or 0, TEXT2),
                    (late_hours, "#f0a500" if late_hours else TEXT3),
                    (rec.get("overtime_hours") or 0, SUCCESS if rec.get("overtime_hours") else TEXT3),
                ]
                for (val, clr), (_, width) in zip(values, COLS):
                    rl.addWidget(_cell(val, 12, clr, width=width))
                rows_l.addWidget(row)

        month_cb.currentIndexChanged.connect(lambda _: _reload())
        year_e.editingFinished.connect(_reload)
        _reload()
        return page

    # Leaves
    def _page_leaves(self):
        from auth_model import get_employee_leaves, get_emp_id_by_username
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("My Leaves",         20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Your leave balance", 13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        emp_id = self.controller.get_emp_id_by_username(self.username)
        if emp_id is None:
            lay.addWidget(make_label("Error: Could not resolve your Employee ID.", 13, DANGER))
            lay.addStretch(); return page

        ok, info = get_employee_leaves(emp_id)
        total     = info["total"]     if ok else "N/A"
        used      = info["used"]      if ok else "N/A"
        remaining = info["remaining"] if ok else "N/A"
        rem_color = SUCCESS if ok and info["remaining"] > 0 else DANGER

        cards_row = QHBoxLayout(); cards_row.setSpacing(10)
        for num, lbl_text, clr in [(total,"Total Leaves",TEXT),(used,"Used Leaves",TEXT2),(remaining,"Remaining Leaves",rem_color)]:
            card = card_frame(10)
            cl = QVBoxLayout(card); cl.setContentsMargins(16,18,16,18); cl.setSpacing(4)
            cl.addWidget(make_label(str(num), 34, clr, bold=True), alignment=Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(make_label(lbl_text, 11, TEXT3),           alignment=Qt.AlignmentFlag.AlignCenter)
            cards_row.addWidget(card)
        lay.addLayout(cards_row); lay.addSpacing(16)

        note = card_frame(8)
        nl = QVBoxLayout(note); nl.setContentsMargins(16,14,16,14)
        if ok and remaining == 0:
            nl.addWidget(make_label("Warning: You have no remaining leaves. Any future absence will be unpaid.", 12, DANGER))
        elif not ok:
            nl.addWidget(make_label("Info: No leave record found. Ask your admin to set your leave balance.", 12, TEXT3))
        else:
            nl.addWidget(make_label(f"Info: You have used {used} out of {total} leaves. {remaining} remaining.", 12, TEXT2))
        lay.addWidget(note); lay.addSpacing(16)

        lay.addStretch()
        return page

    # Request Leave
    def _page_request_leave(self):
        from auth_model import submit_leave_request, get_leave_requests, request_leave_revert
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        outer_lay = QVBoxLayout(page); outer_lay.setContentsMargins(0,0,0,0); outer_lay.setSpacing(0)
        inner = QWidget(); inner.setStyleSheet("background: transparent;")
        lay  = QVBoxLayout(inner); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Request Leave",                20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Submit a new leave application", 13, TEXT3))
        lay.addSpacing(14); lay.addWidget(divider()); lay.addSpacing(14)

        emp_id = self.controller.get_emp_id_by_username(self.username)
        if emp_id is None:
            lay.addWidget(make_label("Error: Could not resolve your Employee ID. Contact admin.", 13, DANGER))
            lay.addStretch()
            outer_lay.addWidget(make_scroll(inner))
            return page

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,20,20,20); fl.setSpacing(8)
        fl.addWidget(make_label("Leave Type", 12, TEXT2))
        type_cb = QComboBox()
        type_cb.addItems(["Sick Leave", "Casual Leave", "Annual Leave", "Other"])
        type_cb.setMinimumHeight(38)
        type_cb.setStyleSheet(combo_box_style(15))
        fl.addWidget(type_cb)

        fl.addWidget(make_label("Leave Duration", 12, TEXT2))
        duration_cb = QComboBox()
        duration_cb.addItems(["Full Day", "Half Day", "Quarter Leave"])
        duration_cb.setMinimumHeight(38)
        duration_cb.setStyleSheet(combo_box_style(15))
        fl.addWidget(duration_cb)

        duration_rules = {
            "Sick Leave": ["Full Day", "Half Day", "Quarter Leave"],
            "Casual Leave": ["Full Day", "Half Day"],
            "Annual Leave": ["Full Day"],
            "Other": ["Full Day", "Half Day"],
        }

        def _refresh_duration_options():
            current = duration_cb.currentText()
            duration_cb.blockSignals(True)
            duration_cb.clear()
            options = duration_rules.get(type_cb.currentText(), ["Full Day"])
            duration_cb.addItems(options)
            if current in options:
                duration_cb.setCurrentText(current)
            duration_cb.blockSignals(False)

        type_cb.currentIndexChanged.connect(_refresh_duration_options)
        _refresh_duration_options()

        def _make_calendar_picker(title):
            state = {"date": QDate.currentDate().addDays(1)}

            box = QWidget()
            bl = QHBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(8)

            date_e = QLineEdit(qdate_display(state["date"]))
            date_e.setReadOnly(True)
            date_e.setMinimumHeight(42)
            date_e.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            date_e.setStyleSheet(f"""
                QLineEdit {{
                    background: {ENTRY_BG};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    font-size: 15px;
                    font-weight: 700;
                    padding: 0 14px;
                }}
            """)

            btn = make_calendar_button(height=42, width=42, tooltip=f"Pick {title.lower()}")
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            def _open_calendar():
                dlg = QDialog(self)
                dlg.setModal(True)
                dlg.setWindowTitle(title)
                dlg.setFixedSize(360, 400)
                dlg.setStyleSheet("background-color: #0f1115; color: #f8f5ef;")

                dlay = QVBoxLayout(dlg)
                dlay.setContentsMargins(14, 14, 14, 14)
                dlay.setSpacing(10)

                cal = QCalendarWidget()
                cal.setGridVisible(True)
                cal.setMinimumDate(QDate.currentDate().addDays(1))
                cal.setSelectedDate(state["date"])
                cal.setStyleSheet("""
                    QCalendarWidget {
                        background-color: #0f1115;
                        color: #f8f5ef;
                        border: 1px solid #2b313d;
                        border-radius: 10px;
                    }
                    QCalendarWidget QWidget#qt_calendar_navigationbar {
                        background-color: #111827;
                        border-bottom: 1px solid #2b313d;
                    }
                    QCalendarWidget QToolButton {
                        background-color: #111827;
                        color: #f8f5ef;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 8px;
                        font-weight: 600;
                    }
                    QCalendarWidget QToolButton:hover {
                        background-color: #1f2937;
                    }
                    QCalendarWidget QSpinBox {
                        background-color: #111827;
                        color: #f8f5ef;
                        border: 1px solid #374151;
                        border-radius: 6px;
                        padding: 2px 6px;
                    }
                    QCalendarWidget QAbstractItemView {
                        selection-background-color: #f8f5ef;
                        selection-color: #0f1115;
                        background-color: #0f1115;
                        color: #f8f5ef;
                    }
                """)
                dlay.addWidget(cal)

                btn_row = QHBoxLayout()
                btn_row.addStretch()
                cancel_btn = QPushButton("Cancel")
                cancel_btn.setFixedHeight(34)
                cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                cancel_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: #f8f5ef;
                        border: 1px solid #374151;
                        border-radius: 7px;
                        font-size: 13px;
                        font-weight: 600;
                        padding: 0 14px;
                    }}
                    QPushButton:hover {{
                        background: #1f2937;
                    }}
                """)
                ok_btn = QPushButton("Select")
                ok_btn.setFixedHeight(34)
                ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                ok_btn.setStyleSheet("""
                    QPushButton {
                        background: #f8f5ef;
                        color: #111827;
                        border: none;
                        border-radius: 7px;
                        font-size: 13px;
                        font-weight: 700;
                        padding: 0 14px;
                    }
                    QPushButton:hover {
                        background: #ede8df;
                    }
                """)
                btn_row.addWidget(cancel_btn)
                btn_row.addWidget(ok_btn)
                dlay.addLayout(btn_row)

                cancel_btn.clicked.connect(dlg.reject)
                ok_btn.clicked.connect(lambda: dlg.accept())
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    state["date"] = cal.selectedDate()
                    picked = qdate_display(state["date"])
                    date_e.setText(picked)

            btn.clicked.connect(_open_calendar)
            bl.addWidget(date_e)
            bl.addWidget(btn)
            return box, lambda: qdate_iso(state["date"])

        date_row = QVBoxLayout(); date_row.setSpacing(8)
        dc1 = QVBoxLayout(); dc1.addWidget(make_label("From Date", 12, TEXT2))
        from_box, get_from_date = _make_calendar_picker("From Date")
        dc1.addWidget(from_box)
        dc2 = QVBoxLayout(); dc2.addWidget(make_label("To Date", 12, TEXT2))
        to_box, get_to_date = _make_calendar_picker("To Date")
        dc2.addWidget(to_box)
        date_row.addLayout(dc1); date_row.addLayout(dc2)
        fl.addLayout(date_row)

        fl.addWidget(make_label("Reason", 12, TEXT2))
        reason_e = QTextEdit(); reason_e.setFixedHeight(70)
        reason_e.setStyleSheet(f"""
            QTextEdit {{ background: {ENTRY_BG}; border: 1px solid {BORDER}; border-radius: 6px;
                         padding: 8px 12px; font-size: 15px; color: {TEXT}; }}
            QTextEdit:focus {{ border: 1.5px solid {ACCENT}; }}
        """)
        fl.addWidget(reason_e)
        msg_lbl = make_label("", 12, SUCCESS); fl.addWidget(msg_lbl)
        btn = make_button("Submit Leave Request"); fl.addWidget(btn)
        lay.addWidget(form); lay.addSpacing(16)

        revert_card = card_frame()
        rv = QVBoxLayout(revert_card); rv.setContentsMargins(20,18,20,18); rv.setSpacing(8)
        rv.addWidget(make_label("Request Leave Revert", 14, TEXT, bold=True))
        rv.addWidget(make_label("Ask admin to revert an approved leave request", 12, TEXT3))
        revert_cb = QComboBox()
        revert_cb.setMinimumHeight(38)
        revert_cb.setStyleSheet(combo_box_style(14))
        rv.addWidget(revert_cb)
        revert_reason_e = QTextEdit()
        revert_reason_e.setPlaceholderText("Reason for reverting this approved leave")
        revert_reason_e.setFixedHeight(64)
        revert_reason_e.setStyleSheet(f"""
            QTextEdit {{ background: {ENTRY_BG}; border: 1px solid {BORDER}; border-radius: 6px;
                         padding: 8px 12px; font-size: 14px; color: {TEXT}; }}
            QTextEdit:focus {{ border: 1.5px solid {ACCENT}; }}
        """)
        rv.addWidget(revert_reason_e)
        revert_btn = make_button("Send Revert Request", color="#2980b9", hover="#1f6391", height=38)
        rv.addWidget(revert_btn)
        lay.addWidget(revert_card); lay.addSpacing(16)

        lay.addWidget(make_label("My Leave History", 14, TEXT, bold=True))
        lay.addSpacing(8)
        STATUS_CLR = {"Pending":"#f0a500","Approved":SUCCESS,"Rejected":DANGER,"Reverted":TEXT3,"Revert Requested":"#2980b9"}
        COLS = ["Type","Duration","From","To","Days","Submitted","Status","Remarks","Action"]
        hdr = QWidget(); hdr.setStyleSheet(f"background: {BG}; border-radius: 6px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(6,7,6,7)
        for c in COLS:
            l = make_label(c, 11, TEXT3, bold=True); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hl.addWidget(l, 3 if c in ("Type","Remarks") else 1)
        lay.addWidget(hdr)
        rows_w = QWidget(); rows_w.setStyleSheet("background: transparent;")
        rows_l = QVBoxLayout(rows_w); rows_l.setContentsMargins(0,0,0,0); rows_l.setSpacing(6)
        scroll = make_scroll(rows_w); scroll.setFixedHeight(200); lay.addWidget(scroll); lay.addStretch()

        def _reload_revert_options(records=None):
            records = records if records is not None else get_leave_requests(emp_id=emp_id)
            approved = [r for r in records if r["status"] == "Approved" and r.get("can_revert", False)]
            revert_cb.clear()
            if not approved:
                revert_cb.addItem("No approved leave available to request revert", "")
                revert_btn.setEnabled(False)
                return
            revert_btn.setEnabled(True)
            for req in approved:
                label = (
                    f"{display_date(req['from_date'])} to {display_date(req['to_date'])} | "
                    f"{req['leave_type']} | {req['days']} day(s)"
                )
                revert_cb.addItem(label, req["request_id"])

        def _reload_history():
            while rows_l.count():
                item = rows_l.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            records = get_leave_requests(emp_id=emp_id)
            _reload_revert_options(records)
            if not records:
                rows_l.addWidget(make_label("No leave requests yet.", 12, TEXT3)); return
            for i, req in enumerate(records):
                row = QWidget()
                row.setStyleSheet(f"background: {'#faf7f2' if i%2==0 else '#f5f0e8'}; border: 1px solid {BORDER}; border-radius: 5px;")
                rl = QHBoxLayout(row); rl.setContentsMargins(6,8,6,8)
                status = req["status"]; s_color = STATUS_CLR.get(status, TEXT)
                leave_reason = str(req.get("reason") or "N/A")
                revert_reason = str(req.get("revert_reason") or "").strip()
                remarks = str(req.get("remarks") or "N/A")
                details = f"Leave: {leave_reason}"
                if revert_reason:
                    details += f" | Revert: {revert_reason}"
                if remarks != "N/A":
                    details += f" | Remarks: {remarks}"
                for val, stretch, clr in [
                    (req["leave_type"],3,TEXT2),(req.get("leave_duration", "Full Day"),1,TEXT2),
                    (display_date(req["from_date"]),1,TEXT),(display_date(req["to_date"]),1,TEXT),
                    (req["days"],1,TEXT),(display_date(req["submitted_on"]),1,TEXT3),(status,1,s_color),(details,3,TEXT3)
                ]:
                    l = make_label(str(val), 12, clr); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    rl.addWidget(l, stretch)
                if status == "Approved" and req.get("can_revert", False):
                    rid = req["request_id"]
                    revert_btn = QPushButton("Request")
                    revert_btn.setFixedSize(78, 28)
                    revert_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    revert_btn.setToolTip("Request admin to revert this approved leave")
                    revert_btn.setStyleSheet(f"""
                        QPushButton {{
                            background:{BG3};
                            color:{ACCENT};
                            border:1px solid {BORDER};
                            border-radius:5px;
                            font-size:12px;
                            font-weight:800;
                        }}
                        QPushButton:hover {{ background:{BG}; }}
                    """)
                    revert_btn.clicked.connect(lambda _, r=rid: _request_revert(r))
                    rl.addWidget(revert_btn, 1)
                else:
                    l = make_label("—", 12, TEXT3)
                    l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    rl.addWidget(l, 1)
                rows_l.addWidget(row)

        def _request_revert(request_id):
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Request Leave Revert")
            dlg.setLabelText("Enter reason for requesting this approved leave to be reverted:")
            dlg.setInputMode(QInputDialog.InputMode.TextInput)
            dlg.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput, True)
            dlg.setStyleSheet(popup_stylesheet())
            accepted = dlg.exec() == QDialog.DialogCode.Accepted
            reason = dlg.textValue().strip()
            if not accepted:
                return
            ok2, msg = request_leave_revert(request_id, emp_id, reason)
            msg_lbl.setText(msg)
            msg_lbl.setStyleSheet(f"color:{SUCCESS if ok2 else DANGER};font-size:12px;")
            if ok2:
                _reload_history()

        def _send_revert_request():
            request_id = revert_cb.currentData()
            reason = revert_reason_e.toPlainText().strip()
            if not request_id:
                msg_lbl.setText("No approved leave is available for revert request.")
                msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;")
                return
            ok2, msg = request_leave_revert(request_id, emp_id, reason)
            msg_lbl.setText(msg)
            msg_lbl.setStyleSheet(f"color:{SUCCESS if ok2 else DANGER};font-size:12px;")
            if ok2:
                revert_reason_e.clear()
                _reload_history()

        def do_submit():
            lt = type_cb.currentText()
            duration = duration_cb.currentText()
            frm = get_from_date()
            to = get_to_date()
            reason = reason_e.toPlainText().strip()
            if not frm or not to or not reason:
                msg_lbl.setText("All fields are required."); msg_lbl.setStyleSheet(f"color:{DANGER};font-size:12px;"); return
            ok2, msg = submit_leave_request(emp_id, lt, frm, to, reason, duration)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color:{SUCCESS if ok2 else DANGER};font-size:12px;")
            if ok2:
                reason_e.clear()
                duration_cb.setCurrentIndex(0)
                _reload_history()

        btn.clicked.connect(do_submit)
        revert_btn.clicked.connect(_send_revert_request)
        _reload_history()
        outer_lay.addWidget(make_scroll(inner))
        return page

    # Change Password
    def _page_password(self):
        page = QWidget(); page.setStyleSheet(f"background: {BG2};")
        lay  = QVBoxLayout(page); lay.setContentsMargins(28,28,28,28); lay.setSpacing(0)
        lay.addWidget(make_label("Change Password",             20, TEXT, bold=True))
        lay.addSpacing(4)
        lay.addWidget(make_label("Update your account password", 13, TEXT3))
        lay.addSpacing(16); lay.addWidget(divider()); lay.addSpacing(16)

        form = card_frame()
        fl = QVBoxLayout(form); fl.setContentsMargins(20,20,20,20); fl.setSpacing(8)
        fl.addWidget(make_label("Current Password", 12, TEXT2))
        old_e = make_entry("Enter current password", password=True); fl.addWidget(old_e)
        fl.addWidget(make_label("New Password", 12, TEXT2))
        new_e = make_entry("Enter new password", password=True); fl.addWidget(new_e)
        fl.addWidget(make_label("Confirm New Password", 12, TEXT2))
        con_e = make_entry("Re-enter new password", password=True); fl.addWidget(con_e)
        msg_lbl = make_label("", 12, DANGER); fl.addWidget(msg_lbl)
        btn = make_button("Update Password"); fl.addWidget(btn)
        lay.addWidget(form); lay.addStretch()

        def do_change():
            old = old_e.text().strip(); new = new_e.text().strip(); con = con_e.text().strip()
            if not old or not new or not con:
                msg_lbl.setText("All fields required."); return
            if new != con:
                msg_lbl.setText("New passwords do not match."); return
            ok2, msg = self.controller.change_password(self.username, old, new)
            msg_lbl.setText(msg); msg_lbl.setStyleSheet(f"color:{SUCCESS if ok2 else DANGER};font-size:12px;")
            if ok2: old_e.clear(); new_e.clear(); con_e.clear()

        btn.clicked.connect(do_change)
        return page


# ----------------------------------------------------------------------
#  MAIN APPLICATION WINDOW
# ----------------------------------------------------------------------
class App(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet((app.styleSheet() or "") + popup_stylesheet())
        controller.set_app(self)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1200, 700)
        self.setMinimumSize(960, 580)
        self.setStyleSheet(f"background: {BG};")

        # Outer frame - no border, no radius: full-bleed login look
        outer = QWidget()
        outer.setStyleSheet(f"background: {BG};")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        self.setCentralWidget(outer)

        self._titlebar = TitleBar(self)
        outer_lay.addWidget(self._titlebar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BG};")
        outer_lay.addWidget(self._stack)

        self._show_login()
        self._center()

    def _center(self):
        screen = desktop_work_area(self)
        x = screen.x() + (screen.width()  - self.width())  // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _clear(self):
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
            w.deleteLater()

    def _show_login(self):
        self._clear()
        login = LoginScreen(self.controller)
        self._stack.addWidget(login)
        self._stack.setCurrentWidget(login)

    def load_dashboard(self, role, username):
        self._clear()
        if role == "admin":
            if not self.controller.is_admin():
                self._show_login()
                return
            dash = AdminDashboard(self.controller, username)
        else:
            if not self.controller.is_employee() or str(username) != str(self.controller.current_user()):
                self._show_login()
                return
            dash = EmployeeDashboard(self.controller, username)
        self._stack.addWidget(dash)
        self._stack.setCurrentWidget(dash)
        fade_in(dash, 300)


# ----------------------------------------------------------------------
#  ENTRY POINT
# ----------------------------------------------------------------------
def run(controller):
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 13))
    window = App(controller)
    window.show()
    QTimer.singleShot(0, window._titlebar.maximize_to_screen)
    sys.exit(app.exec())

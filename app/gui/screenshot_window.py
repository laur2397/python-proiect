"""Fereastra Screenshot Reader (faza 15, pasul 15.2): V-001, V-003…V-009,
V-020…V-022, V-026, V-100…V-104.

O fereastra mica, plutitoare (V-100), cu `Capture:`, `Language:`, `Send:` (V-101)
si doua butoane mari: unul porneste captura, celalalt trimite rezultatul (V-102).
Zona se alege pe ecran (`AreaSelector`): se trage dreptunghiul, se poate trage din
nou sau muta, apoi `Capture` / Enter; `Esc` sau clic dreapta anuleaza (V-007).
Recunoasterea se opreste cu `Stop` / `Esc` (V-008). Iconul din bara de sistem are
`Always on Top`, `Run at Startup`, `Enable Sounds` (V-020…V-022, V-104).

Ruleaza ca proces separat (`--screenshot-reader`, V-001; faza_15_pasi.md decizia 5).
Capturile le face `QtGrabber`; regulile sunt in `app.core.screenshot`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.model import Rect
from app.core.screenshot import (
    CAPTURE_MODES,
    SEND_TARGETS,
    TIMED_DELAY_S,
    ScreenshotReader,
    rows_to_tsv,
)
from app.gui import icons
from app.gui.i18n import tr

FILE_FILTERS = {"text_file": "screenshot.filter.text", "table_file": "screenshot.filter.table",
                "image_file": "screenshot.filter.image"}


# --- capturarea ecranului cu Qt --------------------------------------------------------------

def qimage_to_pil(image: QImage) -> Image.Image:
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    data = bytes(rgb.constBits())
    return Image.frombuffer("RGB", (rgb.width(), rgb.height()), data, "raw", "RGB",
                            rgb.bytesPerLine(), 1).copy()


class QtGrabber:
    """`ScreenGrabber` cu Qt: coordonate logice ale desktopului virtual; o zona
    peste mai multe monitoare se compune din bucati (V-025)."""

    def screens(self) -> list[Rect]:
        return [Rect(g.x(), g.y(), g.width(), g.height())
                for g in (s.geometry() for s in QGuiApplication.screens())]

    def grab(self, rect: Rect) -> Image.Image:
        out = Image.new("RGB", (rect.w, rect.h), "white")
        want = QRect(rect.x, rect.y, rect.w, rect.h)
        for screen in QGuiApplication.screens():
            part = screen.geometry().intersected(want)
            if part.isEmpty():
                continue
            geo = screen.geometry()
            pixmap = screen.grabWindow(0, part.x() - geo.x(), part.y() - geo.y(),
                                       part.width(), part.height())
            image = pixmap.toImage().scaled(part.width(), part.height())
            out.paste(qimage_to_pil(image), (part.x() - rect.x, part.y() - rect.y))
        return out

    def window_rect(self, window_id: int) -> Rect:  # V-004
        if not sys.platform.startswith("win"):
            raise ValueError("captura unei ferestre e disponibila pe Windows")
        import ctypes
        from ctypes import wintypes

        box = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(window_id, ctypes.byref(box))  # type: ignore[attr-defined]
        ratio = QGuiApplication.primaryScreen().devicePixelRatio() or 1
        return Rect(int(box.left / ratio), int(box.top / ratio),
                    int((box.right - box.left) / ratio), int((box.bottom - box.top) / ratio))

    @staticmethod
    def window_at(point: QPoint) -> int | None:
        """Fereastra principala de sub cursor (Windows)."""
        if not sys.platform.startswith("win"):
            return None
        import ctypes
        from ctypes import wintypes

        ratio = QGuiApplication.primaryScreen().devicePixelRatio() or 1
        pt = wintypes.POINT(int(point.x() * ratio), int(point.y() * ratio))
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.WindowFromPoint(pt)
        return int(user32.GetAncestor(hwnd, 2)) or None  # GA_ROOT


# --- alegerea zonei pe ecran (V-003, V-004, V-007) ---------------------------------------------

class AreaSelector(QWidget):
    """Ecranul inghetat peste tot desktopul; se trage zona (sau, in modul fereastra,
    se da clic pe cadrul evidentiat). Enter / dublu clic / `Capture` = gata;
    `Esc` / clic dreapta = anulare."""

    chosen = Signal(object)
    """`Rect` (zona) sau `int` (fereastra, V-004)."""
    cancelled = Signal()

    def __init__(self, grabber: Any, *, window_mode: bool = False) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setObjectName("screenshot_selector")
        self.grabber = grabber
        self.window_mode = window_mode
        screens = grabber.screens()
        x0 = min(r.x for r in screens)
        y0 = min(r.y for r in screens)
        x1 = max(r.x + r.w for r in screens)
        y1 = max(r.y + r.h for r in screens)
        self.origin = QPoint(x0, y0)
        self.setGeometry(x0, y0, x1 - x0, y1 - y0)
        self.background: QPixmap | None = None
        self.selection = QRect()
        self.window_id: int | None = None
        self._start: QPoint | None = None
        self._moving: QPoint | None = None
        self.capture_button = QPushButton(tr("screenshot.capture_now"), self)
        self.capture_button.setObjectName("screenshot_capture_now")
        self.capture_button.clicked.connect(self.confirm)
        self.capture_button.hide()
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def freeze(self) -> None:
        image = self.grabber.grab(Rect(self.origin.x(), self.origin.y(), self.width(),
                                       self.height()))
        data = image.convert("RGB").tobytes()
        qimage = QImage(data, image.width, image.height, image.width * 3,
                        QImage.Format.Format_RGB888)
        self.background = QPixmap.fromImage(qimage.copy())

    def set_selection(self, rect: QRect) -> None:
        self.selection = rect.normalized()
        if self.selection.width() > 0:
            pos = self.selection.bottomRight() - QPoint(self.capture_button.sizeHint().width(),
                                                        -6)
            self.capture_button.move(pos)
            self.capture_button.show()
        self.update()

    def global_rect(self) -> Rect:
        r = self.selection
        return Rect(r.x() + self.origin.x(), r.y() + self.origin.y(), r.width(), r.height())

    def confirm(self) -> None:
        if self.window_mode and self.window_id is not None:
            self.chosen.emit(self.window_id)
        elif self.selection.width() > 0 and self.selection.height() > 0:
            self.chosen.emit(self.global_rect())
        else:
            return
        self.close()

    def cancel(self) -> None:
        self.cancelled.emit()
        self.close()

    # --- evenimente ---

    def keyPressEvent(self, event: QKeyEvent) -> None:  # API Qt
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirm()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # API Qt
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel()
            return
        point = event.position().toPoint()
        if self.window_mode:
            self.confirm()
            return
        if self.selection.contains(point):
            self._moving = point - self.selection.topLeft()  # zona se muta
        else:
            self._start = point
            self.set_selection(QRect(point, point))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # API Qt
        point = event.position().toPoint()
        if self.window_mode:
            hwnd = QtGrabber.window_at(point + self.origin)
            if hwnd and hwnd != int(self.winId()):
                self.window_id = hwnd
                r = self.grabber.window_rect(hwnd)
                self.set_selection(QRect(r.x - self.origin.x(), r.y - self.origin.y(), r.w, r.h))
            return
        if self._moving is not None:
            self.set_selection(QRect(point - self._moving, self.selection.size()))
        elif self._start is not None:
            self.set_selection(QRect(self._start, point))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # API Qt
        self._start = None
        self._moving = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # API Qt
        self.confirm()

    def paintEvent(self, event: QPaintEvent) -> None:  # API Qt
        painter = QPainter(self)
        if self.background is not None:
            painter.drawPixmap(0, 0, self.background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if not self.selection.isEmpty():
            if self.background is not None:
                painter.drawPixmap(self.selection, self.background, self.selection)
            painter.setPen(QColor("#2f6df6"))
            painter.drawRect(self.selection.adjusted(0, 0, -1, -1))
        painter.end()


# --- fereastra (V-100…V-104) ----------------------------------------------------------------

class ScreenshotWindow(QWidget):
    """V-100: mica, plutitoare, cu titlul produsului, `?` si `X`."""

    ocr_editor_requested = Signal(object, bool)
    """V-018, V-103: imaginea si `True` = proiectul curent, `False` = proiect nou."""

    def __init__(self, context: Any, *, grabber: Any = None, engine: Any = None,
                 registry: Any = None) -> None:
        super().__init__(None, Qt.WindowType.Tool)
        self.setObjectName("screenshot_window")
        self.setWindowTitle(tr("screenshot.title"))
        self.context = context
        self.reader = ScreenshotReader(context, grabber or QtGrabber(), engine=engine,
                                       sleep=lambda _s: None)
        self.registry = registry
        self.image: Any = None
        """Ultima captura (`LoadedImage`)."""
        self.messages: list[str] = []
        self.opened: list[Path] = []
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        form = QFormLayout()
        self.capture = QComboBox()  # V-101
        self.capture.setObjectName("screenshot_capture")
        for mode in CAPTURE_MODES:
            self.capture.addItem(tr(f"screenshot.capture.{mode}"), mode)
        self.capture.setCurrentIndex(max(self.capture.findData(
            context.settings.get("screenshot.capture")), 0))
        self.capture.currentIndexChanged.connect(
            lambda _i: context.settings.set("screenshot.capture", self.capture.currentData()))
        form.addRow(tr("screenshot.label.capture"), self.capture)
        self.language = QComboBox()  # V-009
        self.language.setObjectName("screenshot_language")
        self._fill_languages(list(context.settings.get("screenshot.languages") or ["ron"]))
        self.language.activated.connect(self._language_chosen)
        form.addRow(tr("screenshot.label.language"), self.language)
        self.send = QComboBox()
        self.send.setObjectName("screenshot_send")
        for target in SEND_TARGETS:
            self.send.addItem(tr(f"screenshot.send.{target}"), target)
        self.send.setCurrentIndex(max(self.send.findData(
            context.settings.get("screenshot.send")), 0))
        self.send.currentIndexChanged.connect(
            lambda _i: context.settings.set("screenshot.send", self.send.currentData()))
        form.addRow(tr("screenshot.label.send"), self.send)
        top.addLayout(form, 1)
        buttons = QVBoxLayout()  # V-102: in dreapta, cu iconuri
        self.capture_button = QToolButton()
        self.capture_button.setObjectName("screenshot_capture_button")
        self.capture_button.setIcon(icons.icon("scan"))
        self.capture_button.setText(tr("screenshot.button.capture"))
        self.capture_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.capture_button.clicked.connect(self.start_capture)
        self.send_button = QToolButton()
        self.send_button.setObjectName("screenshot_send_button")
        self.send_button.setIcon(icons.icon("send"))
        self.send_button.setText(tr("screenshot.button.send"))
        self.send_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.send_button.clicked.connect(lambda: self.deliver())
        buttons.addWidget(self.capture_button)
        buttons.addWidget(self.send_button)
        top.addLayout(buttons)
        layout.addLayout(top)
        bottom = QHBoxLayout()
        self.repeat_button = QPushButton(tr("screenshot.repeat"))  # V-026
        self.repeat_button.setObjectName("screenshot_repeat")
        self.repeat_button.clicked.connect(self.repeat_capture)
        bottom.addWidget(self.repeat_button)
        bottom.addStretch(1)
        self.help_button = QToolButton()
        self.help_button.setObjectName("screenshot_help")
        self.help_button.setText("?")
        self.help_button.clicked.connect(lambda: QMessageBox.information(
            self, tr("screenshot.title"), tr("screenshot.help_text")))
        bottom.addWidget(self.help_button)
        layout.addLayout(bottom)
        self.options: dict[str, QAction] = {}
        self.tray: QSystemTrayIcon | None = None
        self._build_tray()
        self.apply_always_on_top()
        self._refresh()
        from app.gui.accessibility import ensure_accessible

        ensure_accessible(self)  # Y-019

    # --- puncte de inlocuire pentru teste ---

    def open_path(self, path: Path) -> None:
        self.opened.append(Path(path))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)) if Path(path).exists()
                                 else QUrl(str(path)))

    def pick_save(self, target: str) -> Path | None:
        chosen, _ = QFileDialog.getSaveFileName(self, tr(f"screenshot.send.{target}"), "",
                                                tr(FILE_FILTERS[target]))
        return Path(chosen) if chosen else None

    def ask_current_project(self) -> bool | None:
        """V-103: proiectul curent (True), unul nou (False) sau renuntare (None)."""
        box = QMessageBox(self)
        box.setWindowTitle(tr("screenshot.title"))
        box.setText(tr("screenshot.ocr_project.question"))
        current = box.addButton(tr("screenshot.ocr_project.current"),
                                QMessageBox.ButtonRole.AcceptRole)
        new = box.addButton(tr("screenshot.ocr_project.new"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        return True if clicked is current else False if clicked is new else None

    def run_recognition(self, operation: Any) -> Any:
        """V-008: recunoasterea se opreste cu `Stop` sau `Esc`."""
        from app.gui.progress import ProgressRunner

        runner = ProgressRunner(tr("screenshot.recognizing"), self)
        runner.dialog.setCancelButtonText(tr("screenshot.stop"))
        return runner.run(lambda _progress, cancel: operation(cancel))

    # --- limba (V-009) ---

    def _fill_languages(self, recent: list[str]) -> None:
        from app.gui.options_dialog import language_name

        self.language.clear()
        for code in recent:
            self.language.addItem(language_name(code), code)
        self.language.addItem(tr("screenshot.more_languages"), "")

    def _language_chosen(self, index: int) -> None:
        if self.language.itemData(index):
            self._remember(self.language.itemData(index))
            return
        from app.core.ocr.languages import LanguageRegistry
        from app.gui.options_dialog import language_name

        codes = LanguageRegistry(con=self.context.app_db).all()
        names = [language_name(c) for c in codes]
        name, ok = QInputDialog.getItem(self, tr("screenshot.more_languages"),
                                        tr("screenshot.label.language"), names, 0, False)
        if ok and name:
            self._remember(codes[names.index(name)])
        else:
            self.language.setCurrentIndex(0)

    def _remember(self, code: str) -> None:
        recent = [code] + [c for c in self.languages_recent() if c != code]
        self.context.settings.set("screenshot.languages", recent[:8])
        self._fill_languages(recent[:8])
        self.language.setCurrentIndex(0)

    def languages_recent(self) -> list[str]:
        return list(self.context.settings.get("screenshot.languages") or ["ron"])

    def current_language(self) -> str:
        return self.language.currentData() or self.languages_recent()[0]

    # --- captura (V-003…V-007, V-026) ---

    def _refresh(self) -> None:
        self.repeat_button.setEnabled(self.reader.last_region() is not None)  # V-026
        self.send_button.setEnabled(self.image is not None)

    def start_capture(self) -> AreaSelector | None:
        mode = self.capture.currentData()
        self.hide()  # fereastra utilitarului nu apare in captura
        QApplication.processEvents()
        if mode in ("area", "window"):
            selector = AreaSelector(self.reader._grabber, window_mode=mode == "window")
            selector.freeze()
            selector.chosen.connect(self._chosen)
            selector.cancelled.connect(self._restore)
            self.selector = selector
            selector.showFullScreen() if len(self.reader._grabber.screens()) == 1 \
                else selector.show()
            selector.activateWindow()
            return selector
        if mode == "timed":  # V-006: 5 secunde
            QTimer.singleShot(TIMED_DELAY_S * 1000,
                              lambda: self._captured(self.reader.capture_timed(TIMED_DELAY_S)))
            return None
        self._captured(self.reader.capture_screen())
        return None

    def _chosen(self, choice: Any) -> None:
        try:
            image = self.reader.capture_window(choice) if isinstance(choice, int) \
                else self.reader.capture_area(choice)
        except ValueError as exc:
            self._restore()
            self._say(str(exc))
            return
        self._captured(image)

    def repeat_capture(self) -> None:
        if self.reader.last_region() is None:
            return
        self.hide()
        QApplication.processEvents()
        self._captured(self.reader.repeat_last())

    def _restore(self) -> None:
        self.show()
        self.raise_()
        self._refresh()

    def _captured(self, image: Any) -> None:
        self.image = image
        if self.context.settings.get("screenshot.sounds"):  # V-022
            QApplication.beep()
        self._restore()
        self.deliver()

    # --- trimiterea (V-010…V-019) ---

    def _say(self, text: str) -> None:
        self.messages.append(text)
        if self.tray is not None and self.tray.isVisible():
            self.tray.showMessage(tr("screenshot.title"), text)

    def deliver(self, target: str | None = None) -> Any:
        """Trimite ultima captura dupa `Send:`."""
        if self.image is None:
            return None
        target = target or self.send.currentData()
        image, lang = self.image, [self.current_language()]
        r = self.reader
        clipboard = QApplication.clipboard()
        if target == "text_clipboard":  # V-010
            text = self.run_recognition(lambda cancel: r.to_text(image, lang, cancel=cancel))
            if text is not None:
                clipboard.setText(text)
                self._say(tr("screenshot.done.clipboard"))
            return text
        if target == "table_clipboard":  # V-011
            rows = self.run_recognition(lambda cancel: r.to_table(image, lang, cancel=cancel))
            if rows is not None:
                clipboard.setText(rows_to_tsv(rows))
                self._say(tr("screenshot.done.clipboard"))
            return rows
        if target == "image_clipboard":  # V-012
            small = r.image_to_file(image, r.temp_path(".png"))
            clipboard.setImage(QImage(str(small)))
            self._say(tr("screenshot.done.clipboard"))
            return small
        if target in ("text_word", "table_excel"):  # V-013, V-014 (decizia 4)
            path = r.temp_path(".docx" if target == "text_word" else ".xlsx")
            save = r.text_to_file if target == "text_word" else r.table_to_file
            done = self.run_recognition(lambda _cancel: save(image, lang, path))
            if done is not None:
                self.open_path(done)
            return done
        if target in FILE_FILTERS:  # V-015…V-017
            path = self.pick_save(target)
            if path is None:
                return None
            if target == "image_file":
                done = r.image_to_file(image, path)
            else:
                save = r.text_to_file if target == "text_file" else r.table_to_file
                try:
                    done = self.run_recognition(lambda _cancel: save(image, lang, path))
                except ValueError as exc:
                    self._say(str(exc))
                    return None
            if done is not None:
                self._say(tr("screenshot.done.file", path=str(done)))
            return done
        if target == "image_ocr_editor":  # V-018, V-103
            current = self.ask_current_project()
            if current is None:
                return None
            self.ocr_editor_requested.emit(Path(image.path), current)
            return Path(image.path)
        if target == "image_email":  # V-019: BMP
            bmp = r.image_for_email(image)
            self.open_path(Path("mailto:"))
            self.open_path(bmp.parent)
            return bmp
        return None

    # --- bara de sistem si optiunile (V-001, V-020…V-022, V-104) ---

    def _build_tray(self) -> None:
        menu = QMenu(self)
        menu.setObjectName("screenshot_tray_menu")
        show = menu.addAction(tr("screenshot.tray.capture"))
        show.triggered.connect(self.show_window)
        options = menu.addMenu(tr("screenshot.tray.options"))
        for key in ("always_on_top", "run_at_startup", "sounds"):
            action = options.addAction(tr(f"screenshot.option.{key}"))
            action.setObjectName(f"screenshot_option_{key}")
            action.setCheckable(True)
            action.setChecked(bool(self.context.settings.get(f"screenshot.{key}")))
            action.toggled.connect(lambda on, k=key: self.set_option(k, on))
            self.options[key] = action
        menu.addSeparator()
        quit_action = menu.addAction(tr("screenshot.tray.exit"))
        quit_action.triggered.connect(self.quit)
        self.tray_menu = menu
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icons.icon("scan"), self)
            self.tray.setObjectName("screenshot_tray")
            self.tray.setToolTip(tr("screenshot.title"))
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda *_: self.show_window())
            self.tray.show()

    def set_option(self, key: str, on: bool) -> None:
        self.context.settings.set(f"screenshot.{key}", bool(on))
        if key == "always_on_top":  # V-020
            self.apply_always_on_top()
        elif key == "run_at_startup":  # V-021
            from app.core.integration import default_registry, set_run_at_startup

            set_run_at_startup(self.registry or default_registry(), bool(on))

    def apply_always_on_top(self) -> None:
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,
                           bool(self.context.settings.get("screenshot.always_on_top")))
        if visible:
            self.show()

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit(self) -> None:
        if self.tray is not None:
            self.tray.hide()
        self.close()
        QApplication.quit()


def run(context: Any) -> int:
    """`DocuLens --screenshot-reader` (V-001): utilitarul singur, in proces propriu.
    `Image to OCR Editor` merge la DocuLens (aplicatia deschisa sau una noua)."""
    from app.core.integration import launch_command

    window = ScreenshotWindow(context)

    def to_ocr_editor(path: Path, current: bool) -> None:
        from app.gui.instance import send_to_running

        args = ["--action", "ocr_current" if current else "ocr", str(path)]
        if not send_to_running(args):
            from PySide6.QtCore import QProcess

            command = launch_command(args)
            QProcess.startDetached(command[0], command[1:])
    window.ocr_editor_requested.connect(to_ocr_editor)
    QApplication.instance().setQuitOnLastWindowClosed(window.tray is None)
    window.show_window()
    return int(QApplication.instance().exec())

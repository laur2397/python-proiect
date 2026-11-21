"""Scanarea in interfata (faza 6d, pasul 6d.3).

- `ScanDialog` — `Scan Pages...` (K-002, `Ctrl+K`) si pasii comuni ai
  scanarii din Lansator (A-081): dispozitivul (reinterogat la fiecare
  deschidere, K-003), `Preview` (K-012), modul de culoare (K-005),
  luminozitatea cu avertisment (K-006), rezolutia cu avertisment (K-007),
  formatul hartiei (K-008), duplex si ADF numai cand dispozitivul le are
  (K-009, K-010), pauza pe geam (K-011), interfata driverului din Options
  (K-004), apoi `Scan` si dupa fiecare foaie `Scan Again` / `Finish Scanning`
  (A-082). Cu proiect, paginile intra direct in el; fara proiect, dialogul
  aduna imaginile pentru formatul ales in Lansator.
- `DeviceDialog` — `Select Device...` din Options (X-404, X-407).

Regulile sunt in nucleu (`app.core.images.scanner`). INCOMPLET, marcat: zona de
scanare trasa manual pe previzualizare (K-008) — se folosesc formatele de hartie.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.images.scanner import (
    STANDARD_DPI,
    ScanSession,
    ScanSettings,
    scan_warnings,
)
from app.core.model import ColorMode, Progress
from app.gui.i18n import tr, tr_error

PAPER_SIZES = ("A4", "A5", "Letter", "Legal")
"""K-008: dimensiunile predefinite."""

COLOR_MODES = (ColorMode.COLOR, ColorMode.GRAY, ColorMode.BW)


def warning_texts(keys: list[str]) -> list[str]:
    return [tr(key) for key in keys]


class ScanDialog(QDialog):
    """K-002, A-081, A-082."""

    def __init__(self, context: Any, service: Any, *, project: Any = None,
                 auto_process: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scan_dialog")
        self.setWindowTitle(tr("scan.title"))
        self.context = context
        self.project = project
        self.session = ScanSession(service, project)
        self.show_auto = auto_process
        self.images: list[Path] = []
        """Fara proiect: imaginile scanate, in ordine."""
        self.pages_added = 0
        self.warnings: list[str] = []
        self.capabilities: dict[str, Any] = {}
        self.device = QComboBox()
        self.device.setObjectName("scan_device")
        self.device.currentIndexChanged.connect(self._device_changed)
        self.preview_label = QLabel()
        self.preview_label.setObjectName("scan_preview")
        self.preview_label.setMinimumSize(220, 300)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.color = QComboBox()  # K-005
        self.color.setObjectName("scan_color")
        for mode in COLOR_MODES:
            self.color.addItem(tr(f"color_mode.{mode.value}"), mode.value)
        self.color.setCurrentIndex(COLOR_MODES.index(ColorMode.GRAY))
        self.color.setToolTip(tr("scan.color_hint"))
        self.brightness = QSlider(Qt.Orientation.Horizontal)  # K-006
        self.brightness.setObjectName("scan_brightness")
        self.brightness.setRange(0, 100)
        self.brightness.setValue(50)
        self.dpi = QComboBox()  # K-007
        self.dpi.setObjectName("scan_dpi")
        self.paper = QComboBox()  # K-008
        self.paper.setObjectName("scan_paper")
        self.paper.addItems(list(PAPER_SIZES))
        self.duplex = QCheckBox(tr("scan.duplex"))  # K-009
        self.duplex.setObjectName("scan_duplex")
        self.adf = QCheckBox(tr("scan.adf"))  # K-010
        self.adf.setObjectName("scan_adf")
        self.pause = QSpinBox()  # K-011
        self.pause.setObjectName("scan_pause")
        self.pause.setRange(0, 600)
        self.pause.setSuffix(" s")
        self.passes = QSpinBox()
        self.passes.setObjectName("scan_passes")
        self.passes.setRange(1, 500)
        self.adf.toggled.connect(self._update)
        self.brightness.valueChanged.connect(self._update)
        self.dpi.currentIndexChanged.connect(self._update)
        self.color.currentIndexChanged.connect(self._update)
        self.auto_box = QWidget()  # A-083: numai la scanarea in OCR Editor
        auto = QHBoxLayout(self.auto_box)
        auto.setContentsMargins(0, 0, 0, 0)
        self.auto_process = QCheckBox(tr("setting.image.auto_process"))
        self.auto_process.setObjectName("scan_auto_process")
        self.auto_mode = QComboBox()
        self.auto_mode.setObjectName("scan_auto_mode")
        for mode in ("recognize", "analyze", "preprocess"):
            self.auto_mode.addItem(tr(f"setting.image.auto_mode.{mode}"), mode)
        auto.addWidget(self.auto_process)
        auto.addWidget(self.auto_mode)
        store = project.settings() if project is not None else context.settings
        self.auto_process.setChecked(bool(store.get("image.auto_process")))
        self.auto_mode.setCurrentIndex(max(0, self.auto_mode.findData(
            store.get("image.auto_mode"))))
        self.auto_box.setVisible(auto_process)
        self.message = QLabel()
        self.message.setObjectName("scan_message")
        self.message.setWordWrap(True)
        self.preview_button = QPushButton(tr("scan.preview"))
        self.preview_button.setObjectName("scan_preview_button")
        self.preview_button.clicked.connect(lambda: self.preview())
        self.scan_button = QPushButton(tr("scan.scan"))  # A-082: apoi `Scan Again`
        self.scan_button.setObjectName("scan_start")
        self.scan_button.setDefault(True)
        self.scan_button.clicked.connect(lambda: self.scan())
        self.finish_button = QPushButton(tr("scan.finish"))
        self.finish_button.setObjectName("scan_finish")
        self.finish_button.clicked.connect(self.accept)
        form = QFormLayout()
        form.addRow(tr("scan.device"), self.device)
        form.addRow(tr("scan.color"), self.color)
        form.addRow(tr("scan.brightness"), self.brightness)
        form.addRow(tr("scan.dpi"), self.dpi)
        form.addRow(tr("scan.paper"), self.paper)
        form.addRow(self.duplex)
        form.addRow(self.adf)
        form.addRow(tr("scan.pause"), self.pause)
        form.addRow(tr("scan.passes"), self.passes)
        form.addRow(self.auto_box)
        buttons = QHBoxLayout()
        for button in (self.preview_button, self.scan_button, self.finish_button):
            buttons.addWidget(button)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(self.message)
        left.addStretch(1)
        left.addLayout(buttons)
        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addWidget(self.preview_label)
        self.refresh_devices()

    # --- dispozitivul (K-003) ------------------------------------------------------------

    def refresh_devices(self) -> bool:
        self.device.blockSignals(True)
        self.device.clear()
        try:
            devices = self.session.devices()
        except CoreError as exc:  # niciun scaner → mesaj si trimitere la Options (A-081)
            self.device.blockSignals(False)
            self.message.setText(f"{tr_error(exc)} {tr('scan.check_options')}")
            for widget in (self.scan_button, self.preview_button):
                widget.setEnabled(False)
            return False
        for device_id, name in devices:
            self.device.addItem(name, device_id)
        chosen = self.context.settings.get("general.capture_device")
        self.device.setCurrentIndex(max(0, self.device.findData(chosen)))
        self.device.blockSignals(False)
        self._device_changed()
        return True

    def _device_changed(self, *_: Any) -> None:
        device_id = self.device.currentData()
        if device_id is None:
            return
        try:
            self.capabilities = dict(self.session.service.capabilities(device_id))
        except CoreError as exc:
            self.message.setText(tr_error(exc))
            return
        self.dpi.blockSignals(True)
        self.dpi.clear()
        for dpi in self.capabilities.get("resolutions") or STANDARD_DPI:
            self.dpi.addItem(f"{dpi} dpi", int(dpi))
        self.dpi.setCurrentIndex(max(0, self.dpi.findData(300)))
        self.dpi.blockSignals(False)
        self.duplex.setEnabled(bool(self.capabilities.get("duplex")))  # K-009
        self.adf.setEnabled(bool(self.capabilities.get("adf")))  # K-010
        if not self.duplex.isEnabled():
            self.duplex.setChecked(False)
        if not self.adf.isEnabled():
            self.adf.setChecked(False)
        self._update()

    def _update(self, *_: Any) -> None:
        on_glass = not self.adf.isChecked()
        self.pause.setEnabled(on_glass)  # K-011: pentru scanerele plate
        self.passes.setEnabled(on_glass)
        if self.device.count():
            self.warnings = scan_warnings(self.settings())
            self.message.setText("\n".join(warning_texts(self.warnings)))

    def settings(self) -> ScanSettings:
        driver_ui = self.context.settings.get("general.scan_interface") == "driver"
        return ScanSettings(
            device_id=str(self.device.currentData() or ""),
            color_mode=ColorMode(self.color.currentData()),
            dpi=int(self.dpi.currentData() or 300), brightness=self.brightness.value(),
            page_size=self.paper.currentText(), duplex=self.duplex.isChecked(),
            use_adf=self.adf.isChecked(), flatbed_delay_s=self.pause.value() or None,
            use_driver_ui=driver_ui)

    # --- previzualizarea si scanarea --------------------------------------------------------

    def preview(self) -> bool:
        """K-012: o scanare rapida, afisata in dreapta."""
        try:
            image = self.session.preview(self.settings())
        except (CoreError, ValueError) as exc:
            self._error(exc)
            return False
        pixmap = QPixmap(str(image.path))
        self.preview_label.setPixmap(pixmap.scaled(
            self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio))
        return True

    def _error(self, exc: Exception) -> None:
        self.message.setText(tr_error(exc) if isinstance(exc, CoreError)
                             else tr("scan.invalid"))

    def _remember_auto(self) -> None:
        """A-083: modul de prelucrare automata ales in dialog."""
        if self.show_auto and self.project is not None:
            settings = self.project.settings()
            settings.set("image.auto_process", self.auto_process.isChecked())
            settings.set("image.auto_mode", self.auto_mode.currentData())

    def scan(self) -> int:
        """Foile scanate; dupa ele butonul devine `Scan Again` (A-082)."""
        settings = self.settings()

        def progress(report: Progress) -> None:
            self.message.setText(tr("scan.progress", n=report.current))
            QApplication.processEvents()

        try:
            if self.project is not None:
                self._remember_auto()
                result = self.session.scan_into_project(settings,
                                                        passes=self.passes.value(),
                                                        progress=progress)
                count = len(result.pages)
                self.pages_added += count
                warnings = result.warnings
            else:
                images, warnings = self.session.acquire(settings, passes=self.passes.value(),
                                                        progress=progress)
                self.images += [img.path for img in images]
                count = len(images)
        except (CoreError, ValueError) as exc:
            self._error(exc)
            return 0
        self.context.settings.set("general.capture_device", settings.device_id)
        self.scan_button.setText(tr("scan.again"))
        self.message.setText("\n".join([tr("scan.done", n=count),
                                        *warning_texts(warnings)]))
        return count


class DeviceDialog(QDialog):
    """X-407: `Select a scanner or a camera:`, lista si textul de ajutor."""

    def __init__(self, service: Any, current: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("device_dialog")
        self.setWindowTitle(tr("options.general.select_device"))
        self.devices = QListWidget()
        self.devices.setObjectName("device_list")
        for device_id, name in service.list_devices():  # reinterogat (K-003)
            item = QListWidgetItem(f"{name}  ({tr('scan.technology.wia')})")
            item.setData(Qt.ItemDataRole.UserRole, device_id)
            self.devices.addItem(item)
            if device_id == current:
                self.devices.setCurrentItem(item)
        if self.devices.currentRow() < 0 and self.devices.count():
            self.devices.setCurrentRow(0)
        help_text = QLabel(tr("scan.device_help"))
        help_text.setObjectName("device_help")
        help_text.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("scan.select_device")))
        layout.addWidget(self.devices, 1)
        layout.addWidget(help_text)
        layout.addWidget(buttons)

    def chosen(self) -> tuple[str, str] | None:
        item = self.devices.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole), item.text()


class ImageFilesDialog(QDialog):
    """A-087, A-088: formatul imaginilor si compresia TIFF."""

    def __init__(self, parent: QWidget | None = None) -> None:
        from app.core.convert import SCAN_TIFF_COMPRESSIONS

        super().__init__(parent)
        self.setObjectName("image_files_dialog")
        self.setWindowTitle(tr("scan.task.images"))
        self.format = QComboBox()
        self.format.setObjectName("images_format")
        for fmt in ("tiff", "jpeg", "png"):
            self.format.addItem(fmt.upper(), fmt)
        self.compression = QComboBox()  # A-088: numai pentru TIFF
        self.compression.setObjectName("images_compression")
        for key in SCAN_TIFF_COMPRESSIONS:
            self.compression.addItem(tr(f"scan.compression.{key}"), key)
        self.multipage = QCheckBox(tr("send.multipage"))
        self.multipage.setObjectName("images_multipage")
        self.format.currentIndexChanged.connect(self._update)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow(tr("save.type"), self.format)
        form.addRow(tr("scan.compression"), self.compression)
        form.addRow(self.multipage)
        form.addRow(buttons)
        self._update()

    def _update(self, *_: Any) -> None:
        tiff = self.format.currentData() == "tiff"
        self.compression.setEnabled(tiff)
        self.multipage.setEnabled(tiff)

    def choice(self) -> dict[str, Any]:
        tiff = self.format.currentData() == "tiff"
        return {"format": self.format.currentData(),
                "compression": self.compression.currentData() if tiff else None,
                "multipage": tiff and self.multipage.isChecked()}

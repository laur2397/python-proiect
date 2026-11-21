"""Image Editor (faza 6b, pasul 6b.4): L-001…L-004, L-100…L-108.

Interfata peste uneltele de preprocesare din faza 2 (`OcrProject.
preprocess_pages`, `PreprocessPipeline`): antetul cu `< Exit Image Editor`
(L-100), cele 14 unelte in ordinea din L-101, fiecare expandata inline sub
numele ei (L-102), combo-ul `Selection` (L-003), bifa `Show next page after
operation completes` (L-004, L-104), fundalul gri inchis (L-105), selectia cu
manere si zona taiata marcata punctat (L-106), grila trapezului cu patru
colturi si butonul `Correct` (L-107), histograma uneltei `Levels` (L-108).

Parametrii si validarea lor sunt in nucleu; editorul doar ii aduna. Operatiile
ruleaza pe firul interfetei (INCOMPLET, marcat: firul de lucru cu progres si
anulare vine cu fluxurile din 6b.6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CoreError
from app.core.images.preprocess import PAPER_SIZES_MM, crop_params
from app.core.model import PageData, PreprocessOp, Rect
from app.gui import zones
from app.gui.i18n import tr, tr_error

TOOLS = ("recommended", "deskew", "straighten", "photo", "trapezoid", "rotate_flip", "split",
         "crop", "invert", "resolution", "brightness_contrast", "levels", "eraser",
         "remove_color_marks")
"""L-101: cele 14 unelte, in ordinea din panou."""

SELECTIONS = ("current", "odd", "even", "selected")
"""L-003: valorile combo-ului `Selection` (cheile din `OcrProject.select_pages`)."""

BACKGROUND = QColor(64, 64, 64)
"""L-105: fundalul gri inchis al imaginii (culoare de lucru, nu identitate)."""

_SIMPLE = {"deskew": PreprocessOp.DESKEW, "straighten": PreprocessOp.STRAIGHTEN_LINES,
           "photo": PreprocessOp.PHOTO_CORRECTION, "invert": PreprocessOp.INVERT}

_APPLY_LABEL = {"trapezoid": "editor.correct", "crop": "editor.apply.crop"}
"""L-107: `Correct`; L-103: `Crop`; celelalte: `Apply`."""


class EditorCanvas(QGraphicsView):
    """Imaginea paginii, cu selectia (Crop, Eraser) sau grila trapezului."""

    crop_changed = Signal(object)
    """Rect: dreptunghiul tras cu mouse-ul (L-106)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("editor_canvas")
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(BACKGROUND))  # L-105
        self._pixmap = QGraphicsPixmapItem()
        self.scene().addItem(self._pixmap)
        self.mode: str | None = None
        """`crop`, `erase`, `trapezoid` sau None."""
        self.crop: Rect | None = None
        self.corners: list[list[float]] = []
        self.erase_path: list[list[int]] = []
        self._drag: dict[str, Any] | None = None

    def set_image(self, path: Any) -> None:
        pixmap = QPixmap(str(path))
        self._pixmap.setPixmap(pixmap)
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.crop = None
        self.erase_path = []
        self.viewport().update()

    @property
    def size_px(self) -> tuple[int, int]:
        rect = self.scene().sceneRect()
        return int(rect.width()), int(rect.height())

    def set_mode(self, mode: str | None) -> None:
        self.mode = mode
        self.viewport().update()

    def set_corners(self, corners: list[list[float]]) -> None:
        self.corners = [[float(c[0]), float(c[1])] for c in corners]
        self.viewport().update()

    def _scale(self) -> float:
        return 1 / max(self.transform().m11(), 1e-6)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        point = self.mapToScene(event.position().toPoint())
        if self.mode == "trapezoid" and self.corners:  # L-107: coltul cel mai apropiat
            index = min(range(4), key=lambda i: (self.corners[i][0] - point.x()) ** 2
                        + (self.corners[i][1] - point.y()) ** 2)
            self._drag = {"corner": index}
        elif self.mode == "crop":
            handle = (zones.hit_handle(self.crop, point.x(), point.y(), 8 * self._scale())
                      if self.crop else None)
            self._drag = {"handle": handle, "start": point}
        elif self.mode == "erase":
            self.erase_path = [[round(point.x()), round(point.y())]]
            self._drag = {"erase": True}
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag is None:
            super().mouseMoveEvent(event)
            return
        point = self.mapToScene(event.position().toPoint())
        width, height = self.size_px
        x = min(max(point.x(), 0), width)
        y = min(max(point.y(), 0), height)
        if "corner" in self._drag:
            self.corners[self._drag["corner"]] = [x, y]
        elif "erase" in self._drag:
            self.erase_path.append([round(x), round(y)])
        elif self._drag.get("handle") and self.crop is not None:
            self.crop = zones.clamp(zones.resize(self.crop, self._drag["handle"], x, y),
                                    width, height)
            self.crop_changed.emit(self.crop)
        else:
            start = self._drag["start"]
            self.crop = zones.clamp(zones.normalize(start.x(), start.y(), x, y), width, height)
            self.crop_changed.emit(self.crop)
        self.viewport().update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag = None
        super().mouseReleaseEvent(event)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        scale = self._scale()
        accent = self.palette().highlight().color()  # L-106, L-107: albastru
        if self.mode == "crop" and self.crop is not None:
            box = QRectF(self.crop.x, self.crop.y, self.crop.w, self.crop.h)
            whole = self.scene().sceneRect()
            outside = QColor(0, 0, 0, 90)
            for part in (QRectF(whole.left(), whole.top(), whole.width(), box.top()),
                         QRectF(whole.left(), box.bottom(), whole.width(),
                                whole.bottom() - box.bottom()),
                         QRectF(whole.left(), box.top(), box.left(), box.height()),
                         QRectF(box.right(), box.top(), whole.right() - box.right(),
                                box.height())):
                painter.fillRect(part, outside)
            painter.setPen(QPen(accent, 2 * scale, Qt.PenStyle.DotLine))
            painter.drawRect(box)
            half = 4 * scale
            for hx, hy in zones.handles(self.crop).values():
                painter.fillRect(QRectF(hx - half, hy - half, 2 * half, 2 * half), accent)
        if self.mode == "trapezoid" and len(self.corners) == 4:
            quad = [QPointF(c[0], c[1]) for c in self.corners]
            painter.setPen(QPen(accent, 2 * scale))
            painter.drawPolygon(QPolygonF(quad))
            painter.setPen(QPen(accent, scale))
            for t in (1 / 3, 2 / 3):  # grila: liniile interioare
                painter.drawLine(quad[0] + (quad[1] - quad[0]) * t,
                                 quad[3] + (quad[2] - quad[3]) * t)
                painter.drawLine(quad[0] + (quad[3] - quad[0]) * t,
                                 quad[1] + (quad[2] - quad[1]) * t)
            half = 6 * scale
            for c in quad:
                painter.fillRect(QRectF(c.x() - half, c.y() - half, 2 * half, 2 * half), accent)
        if self.mode == "erase" and len(self.erase_path) > 1:
            painter.setPen(QPen(QColor(255, 255, 255, 160), 3 * scale))
            for a, b in zip(self.erase_path, self.erase_path[1:], strict=False):
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))


class LevelsWidget(QWidget):
    """L-108: histograma, cursoarele de intrare (negru, gri, alb) si cel de iesire."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("levels")
        self.histogram = np.zeros(256)
        self.chart = QLabel()
        self.chart.setObjectName("levels_histogram")
        self.chart.setMinimumHeight(80)
        self.sliders: dict[str, QSlider] = {}
        form = QFormLayout()
        for key, low, high, value in (("black", 0, 254, 0), ("gray", 10, 1000, 100),
                                      ("white", 1, 255, 255), ("output", 0, 255, 255)):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setObjectName(f"levels_{key}")
            slider.setRange(low, high)
            slider.setValue(value)
            self.sliders[key] = slider
            form.addRow(tr(f"editor.levels.{key}"), slider)
        self.sliders["black"].valueChanged.connect(self._keep_order)
        self.sliders["white"].valueChanged.connect(self._keep_order)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart)
        layout.addLayout(form)

    def _keep_order(self) -> None:
        """Punctul negru ramane sub cel alb (regula din `LevelsTool`)."""
        black, white = self.sliders["black"], self.sliders["white"]
        if black.value() >= white.value():
            black.setValue(white.value() - 1)

    def set_image(self, path: Any) -> None:
        from PIL import Image

        with Image.open(path) as img:
            gray = np.asarray(img.convert("L"))
        self.histogram = np.bincount(gray.ravel(), minlength=256).astype(float)
        self._draw()

    def _draw(self) -> None:
        width, height = 256, 80
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(Qt.GlobalColor.white))
        painter = QPainter(pixmap)
        peak = self.histogram.max() or 1.0
        painter.setPen(QColor(Qt.GlobalColor.black))
        for x, count in enumerate(self.histogram):
            painter.drawLine(x, height, x, height - int(count / peak * (height - 2)))
        painter.end()
        self.chart.setPixmap(pixmap)

    def params(self) -> dict[str, Any]:
        return {"black": self.sliders["black"].value(), "white": self.sliders["white"].value(),
                "gamma": self.sliders["gray"].value() / 100,
                "out_black": 0, "out_white": self.sliders["output"].value()}


class ImageEditor(QWidget):
    exited = Signal()
    """L-002: `Exit Image Editor`; modificarile raman aplicate."""
    changed = Signal()
    message = Signal(str)
    next_page = Signal()
    """L-004: dupa operatie, fereastra trece la pagina urmatoare."""

    def __init__(self, project: Any, selected: Callable[[], list[int]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_editor")
        self.project = project
        self.selected = selected
        """Paginile alese in panoul Pages (pentru `Selection: selected`)."""
        self.page: PageData | None = None
        self.canvas = EditorCanvas()
        self.canvas.crop_changed.connect(self._crop_drawn)
        self.selections: dict[str, QComboBox] = {}
        self.buttons: dict[str, QPushButton] = {}
        header = QHBoxLayout()  # L-100
        title = QLabel(tr("editor.title"))
        title.setObjectName("editor_title")
        self.exit_button = QPushButton(tr("editor.exit"))
        self.exit_button.setObjectName("editor_exit")
        self.exit_button.clicked.connect(self.exited.emit)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.exit_button)
        self.toolbox = QToolBox()  # L-101, L-102
        self.toolbox.setObjectName("editor_tools")
        for key in TOOLS:
            self.toolbox.addItem(self._page(key), tr(f"editor.tool.{key}"))
        self.toolbox.currentChanged.connect(self._tool_changed)
        self.show_next = QCheckBox(tr("editor.show_next"))  # L-004, L-104
        self.show_next.setObjectName("editor_show_next")
        right = QVBoxLayout()
        right.addWidget(self.toolbox, 1)
        right.addWidget(self.show_next)
        body = QHBoxLayout()
        body.addWidget(self.canvas, 1)
        body.addLayout(right)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(body, 1)

    # --- paginile uneltelor ------------------------------------------------------

    def _page(self, key: str) -> QWidget:
        page = QWidget()
        page.setObjectName(f"editor_{key}")
        form = QFormLayout(page)
        builder = getattr(self, f"_build_{key}", None)
        if builder is not None:
            builder(form)
        selection = QComboBox()  # L-003: in fiecare unealta
        selection.setObjectName(f"selection_{key}")
        for kind in SELECTIONS:
            selection.addItem(tr(f"editor.selection.{kind}"), kind)
        self.selections[key] = selection
        form.addRow(tr("editor.selection"), selection)
        if key != "rotate_flip":
            button = QPushButton(tr(_APPLY_LABEL.get(key, "editor.apply")))
            button.setObjectName(f"apply_{key}")
            button.clicked.connect(lambda _=False, k=key: self.apply(k))
            self.buttons[key] = button
            form.addRow(button)
        return page

    def _build_rotate_flip(self, form: QFormLayout) -> None:
        row = QHBoxLayout()
        for key, op, params in (("rotate_left", PreprocessOp.ROTATE, {"angle": -90}),
                                ("rotate_right", PreprocessOp.ROTATE, {"angle": 90}),
                                ("rotate_180", PreprocessOp.ROTATE, {"angle": 180}),
                                ("flip_horizontal", PreprocessOp.FLIP, {"axis": "horizontal"}),
                                ("flip_vertical", PreprocessOp.FLIP, {"axis": "vertical"})):
            button = QPushButton(tr(f"editor.{key}"))
            button.setObjectName(f"apply_{key}")
            button.clicked.connect(
                lambda _=False, o=op, p=params: self.apply("rotate_flip", [(o, p)]))
            self.buttons[key] = button
            row.addWidget(button)
        form.addRow(row)

    def _build_split(self, form: QFormLayout) -> None:
        self.split_mode = QComboBox()
        self.split_mode.setObjectName("split_mode")
        for mode in ("vertical", "horizontal"):
            self.split_mode.addItem(tr(f"editor.split.{mode}"), mode)
        form.addRow(tr("editor.split.mode"), self.split_mode)

    def _build_crop(self, form: QFormLayout) -> None:
        """L-103: hartia, marimea, decalajul, unitatea."""
        self.paper = QComboBox()
        self.paper.setObjectName("crop_paper")
        self.paper.addItem(tr("editor.crop.custom"), None)
        for name in PAPER_SIZES_MM:
            self.paper.addItem(name.upper() if len(name) <= 2 else name.capitalize(), name)
        self.paper.currentIndexChanged.connect(self._paper_chosen)
        form.addRow(tr("editor.crop.paper"), self.paper)
        self.crop_fields: dict[str, QDoubleSpinBox] = {}
        for row_key, keys in (("size", ("width", "height")), ("offset", ("x", "y"))):
            row = QHBoxLayout()
            for key in keys:
                spin = QDoubleSpinBox()
                spin.setObjectName(f"crop_{key}")
                spin.setRange(0, 10_000)
                spin.setDecimals(1)
                self.crop_fields[key] = spin
                row.addWidget(spin)
            form.addRow(tr(f"editor.crop.{row_key}"), row)
        units = QHBoxLayout()
        self.units = QButtonGroup(self)
        self.unit_buttons: dict[str, QRadioButton] = {}
        for unit in ("in", "mm"):
            button = QRadioButton(tr(f"editor.crop.{unit}"))
            button.setObjectName(f"crop_{unit}")
            self.units.addButton(button)
            self.unit_buttons[unit] = button
            units.addWidget(button)
        self.unit_buttons["mm"].setChecked(True)
        form.addRow(units)

    def _build_resolution(self, form: QFormLayout) -> None:
        self.dpi = QSpinBox()
        self.dpi.setObjectName("resolution_dpi")
        self.dpi.setRange(50, 2400)
        self.dpi.setValue(300)
        form.addRow(tr("editor.resolution.dpi"), self.dpi)

    def _build_brightness_contrast(self, form: QFormLayout) -> None:
        self.bc: dict[str, QSlider] = {}
        for key in ("brightness", "contrast"):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setObjectName(key)
            slider.setRange(-100, 100)
            self.bc[key] = slider
            form.addRow(tr(f"editor.{key}"), slider)

    def _build_levels(self, form: QFormLayout) -> None:
        self.levels = LevelsWidget()
        form.addRow(self.levels)

    def _build_eraser(self, form: QFormLayout) -> None:
        self.brush = QSpinBox()
        self.brush.setObjectName("eraser_brush")
        self.brush.setRange(1, 2000)
        self.brush.setValue(20)
        form.addRow(tr("editor.eraser.brush"), self.brush)

    def _build_remove_color_marks(self, form: QFormLayout) -> None:
        self.saturation = QSpinBox()
        self.saturation.setObjectName("color_marks_saturation")
        self.saturation.setRange(0, 255)
        self.saturation.setValue(60)
        form.addRow(tr("editor.color_marks.saturation"), self.saturation)

    # --- pagina si unealta curenta -------------------------------------------------

    def set_page(self, page: PageData | None) -> None:
        self.page = page
        if page is None:
            return
        self.canvas.set_image(page.image_path)
        self.dpi.setValue(page.dpi_x)
        self.levels.set_image(page.image_path)
        self._tool_changed(self.toolbox.currentIndex())

    def open_tool(self, key: str) -> None:
        self.toolbox.setCurrentIndex(TOOLS.index(key))

    def _tool_changed(self, index: int) -> None:
        key = TOOLS[index]
        mode = {"crop": "crop", "eraser": "erase", "trapezoid": "trapezoid"}.get(key)
        self.canvas.set_mode(mode)
        if key == "trapezoid" and self.page is not None:
            self.canvas.set_corners(self._initial_corners())

    def _initial_corners(self) -> list[list[float]]:
        """Colturile paginii gasite in imagine; altfel colturile imaginii."""
        from PIL import Image

        from app.core.images.preprocess import detect_page_corners, to_array

        with Image.open(self.page.image_path) as img:
            found = detect_page_corners(to_array(img))
        w, h = self.page.width_px, self.page.height_px
        return found or [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]

    # --- Crop (L-103, L-106) -----------------------------------------------------------

    def _unit(self) -> str:
        return "in" if self.unit_buttons["in"].isChecked() else "mm"

    def _to_unit(self, px: int, dpi: int) -> float:
        inches = px / dpi
        return inches if self._unit() == "in" else inches * 25.4

    def _crop_drawn(self, rect: Rect) -> None:
        if self.page is None:
            return
        self.paper.setCurrentIndex(0)
        for key, value, dpi in (("x", rect.x, self.page.dpi_x), ("y", rect.y, self.page.dpi_y),
                                ("width", rect.w, self.page.dpi_x),
                                ("height", rect.h, self.page.dpi_y)):
            self.crop_fields[key].setValue(self._to_unit(value, dpi))

    def _paper_chosen(self) -> None:
        name = self.paper.currentData()
        if name is not None:
            width, height = PAPER_SIZES_MM[name]
            if self._unit() == "in":
                width, height = width / 25.4, height / 25.4
            self.crop_fields["width"].setValue(width)
            self.crop_fields["height"].setValue(height)

    def crop_chain(self) -> list[tuple[PreprocessOp, dict[str, Any]]]:
        page = self.page
        fields = {k: f.value() for k, f in self.crop_fields.items()}
        params = crop_params(dpi=(page.dpi_x, page.dpi_y), unit=self._unit(),
                             paper=self.paper.currentData(),
                             width=fields["width"] or None, height=fields["height"] or None,
                             x=fields["x"], y=fields["y"])
        return [(PreprocessOp.CROP, params)]

    # --- aplicarea -----------------------------------------------------------------------

    def chain_for(self, key: str) -> list[tuple[PreprocessOp, dict[str, Any]]] | None:
        """Lantul uneltei; None = preprocesarea recomandata (L-010)."""
        if key == "recommended":
            return None
        if key in _SIMPLE:
            return [(_SIMPLE[key], {})]
        if key == "trapezoid":
            return [(PreprocessOp.TRAPEZOID, {"corners": self.canvas.corners})]
        if key == "split":
            return [(PreprocessOp.SPLIT, {"mode": self.split_mode.currentData()})]
        if key == "crop":
            return self.crop_chain()
        if key == "resolution":
            return [(PreprocessOp.RESOLUTION, {"dpi": self.dpi.value(),
                                               "from_dpi": self.page.dpi_x})]
        if key == "brightness_contrast":
            return [(PreprocessOp.BRIGHTNESS_CONTRAST,
                     {k: s.value() for k, s in self.bc.items()})]
        if key == "levels":
            return [(PreprocessOp.LEVELS, self.levels.params())]
        if key == "eraser":
            return [(PreprocessOp.ERASE, {"path": self.canvas.erase_path,
                                          "brush": self.brush.value()})]
        if key == "remove_color_marks":
            return [(PreprocessOp.REMOVE_COLOR_MARKS, {"saturation": self.saturation.value()})]
        raise ValueError(f"unealta necunoscuta: {key!r}")

    def apply(self, key: str,
              chain: list[tuple[PreprocessOp, dict[str, Any]]] | None = None) -> bool:
        """Unealta pe paginile din `Selection` (L-003); un singur pas de undo."""
        if self.page is None:
            return False
        try:
            if chain is None:
                chain = self.chain_for(key)
            kind = self.selections[key].currentData()
            numbers = self.project.select_pages(kind, current=self.page.page_number,
                                                selected=self.selected())
            self.project.preprocess_pages(numbers, chain)
        except CoreError as exc:
            self.message.emit(tr_error(exc))
            return False
        except ValueError:
            self.message.emit(tr("editor.invalid"))
            return False
        self.changed.emit()
        if self.show_next.isChecked():
            self.next_page.emit()
        return True

"""Stampilele in interfata PDF Editor-ului (faza 7, pasul 7.9c): D-045…D-050,
D-107…D-110, Z-013."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image
from test_pdf_search import text_pdf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.context import AppContext
from app.core.model import AnnotationType, Rect
from app.core.paths import AppPaths
from app.gui.pdf_editor import PdfEditorWindow
from app.gui.pdf_stamps import ImageStampDialog, ManageStampsDialog, TextStampDialog


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.background_recognition_pdf", False)
    c.settings.set("pdf_editor.default_author", "Ana")
    yield c
    c.close()


@pytest.fixture
def window(qtbot, ctx, tmp_path):
    w = PdfEditorWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    entry = w.open_path(text_pdf(tmp_path / "dosar.pdf", [["Cerere de finantare"]]))
    entry.view.set_zoom(75)
    QApplication.processEvents()
    yield w
    w.close()


def png(color=(0, 0, 200, 255), size=(120, 60)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, color).save(out, "PNG")
    return out.getvalue()


def click(view, x, y):
    box = view.page_to_view(1, Rect(x, y, 0, 0))
    point = box.topLeft() - QPointF(view.horizontalScrollBar().value(),
                                    view.verticalScrollBar().value())
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     pos=QPoint(int(point.x()), int(point.y())))


def stamps(window):
    return [a for a in window.current().document.annotations()
            if a.annot_type is AnnotationType.STAMP]


# --- D-045, D-107 ---------------------------------------------------------------------


def test_T_D045_1_stamp_menu_and_placement(window):
    texts = [a.text() for a in window.stamp_menu.actions() if a.text()]
    assert texts[:3] == ["Aprobat", "Respins", "Final"]
    assert texts[-3:] == ["Creează ștampilă din imagine...", "Creează ștampilă de text...",
                          "Gestionează ștampilele..."]
    window.choose_stamp("final")
    assert window.annotation_tool is AnnotationType.STAMP
    assert not window.style_bar.isVisible()
    click(window.current().view, 300, 200)
    [stamp] = stamps(window)
    assert stamp.content.startswith("FINAL\n")  # D-107: cu data si ora
    assert (stamp.bbox.x, stamp.bbox.y) == pytest.approx((300, 200), abs=2)
    assert stamp.author == "Ana"
    assert window.annotation_tool is None
    window.undo()
    assert stamps(window) == []


# --- D-047, D-108 ---------------------------------------------------------------------


def test_T_D108_1_image_stamp_dialog(window, tmp_path, monkeypatch):
    dialog = ImageStampDialog(window)
    assert not dialog.save_button.isEnabled()
    path = tmp_path / "sigla.png"
    path.write_bytes(png())
    dialog.open_file(str(path))
    dialog.name.setText("Sigla")
    dialog.slider.setValue(50)
    assert dialog.save_button.isEnabled() and dialog.scale == 0.5
    QApplication.clipboard().setImage(QImage.fromData(png((200, 0, 0, 255))))
    dialog.paste()  # `Paste from Clipboard`
    assert Image.open(io.BytesIO(dialog.image)).getpixel((5, 5))[0] == 200

    def fill(self, d):
        d.name.setText("Sigla")
        d.set_image(png())
        d.slider.setValue(50)
        return True

    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", fill)
    window.create_image_stamp()
    stamp = window.stamps.get("Sigla")
    assert stamp.kind == "image"
    assert Image.open(io.BytesIO(stamp.image)).size == (60, 30)
    assert window.pending_stamp.name == "Sigla"  # gata de pus pe pagina


# --- D-048, D-109, D-110, Z-013 -------------------------------------------------------


def test_T_D110_1_tags_go_to_the_cursor(window):
    dialog = TextStampDialog(window)
    dialog.text.setPlainText("Primit")
    cursor = dialog.text.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    dialog.text.setTextCursor(cursor)
    dialog.insert_tag(dialog.date_combo.findData("<d/>"))
    assert dialog.text.toPlainText() == "<d/>Primit"
    assert dialog.date_combo.currentIndex() == 0


def test_T_D109_Z013_text_stamp_dialog_and_preview(window, monkeypatch):
    dialog = TextStampDialog(window)
    dialog.name.setText("Inregistrare")
    dialog.text.setPlainText("ÎNREGISTRAT <d/>")
    assert "ÎNREGISTRAT" in dialog.preview.text() and "<d/>" not in dialog.preview.text()
    dialog.border.setChecked(False)
    assert dialog.border_value() == "none"
    assert dialog.save_button.isEnabled()

    def fill(self, d):
        d.name.setText("Inregistrare")
        d.text.setPlainText("ÎNREGISTRAT <d/>")
        d.size.setValue(14)
        d.border_style.setCurrentIndex(d.border_style.findData("double"))
        return True

    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", fill)
    window.create_text_stamp()
    stamp = window.stamps.get("Inregistrare")
    assert (stamp.text, stamp.font_size, stamp.border_style) == \
        ("ÎNREGISTRAT <d/>", 14.0, "double")


# --- D-050 ----------------------------------------------------------------------------


def test_T_D050_1_manage_stamps(window, monkeypatch):
    window.stamps.create_text("Proprie", "PROPRIE")
    messages = []
    monkeypatch.setattr(PdfEditorWindow, "show_message",
                        lambda self, text: messages.append(text))
    dialog = ManageStampsDialog(window.stamps, window)
    dialog.select("approved")
    dialog.delete_selected()  # cele livrate nu se sterg
    assert messages and window.stamps.get("approved")

    def edit(self, d):
        d.text.setPlainText("PROPRIE 2")
        return True

    monkeypatch.setattr(PdfEditorWindow, "exec_dialog", edit)
    dialog.select("Proprie")
    dialog.edit_selected()
    assert window.stamps.get("Proprie").text == "PROPRIE 2"
    dialog.select("Proprie")
    dialog.use_selected()
    assert dialog.chosen.name == "Proprie"
    dialog.select("Proprie")
    dialog.delete_selected()
    assert "Proprie" not in [s.name for s in window.stamps.stamps()]

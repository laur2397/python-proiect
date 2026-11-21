"""Faza 6d, pasul 6d.1: regulile scanarii, cu un dispozitiv simulat
(K-002…K-013)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.context import AppContext
from app.core.errors import NoScannerError, ScannerError
from app.core.images.loader import LoadedImage
from app.core.images.scanner import (
    WARNING_BRIGHTNESS,
    WARNING_DPI_HIGH,
    WARNING_DPI_LOW,
    WARNING_DPI_ODD,
    WARNING_DPI_UNEQUAL,
    WARNING_DRIVER_UI,
    ScannerService,
    ScanSession,
    ScanSettings,
    scan_warnings,
    validate,
)
from app.core.model import ColorMode, PageStatus
from app.core.paths import AppPaths
from app.core.project import OcrProject


class FakeScanner:
    """Dispozitiv simulat: un scaner cu ADF si duplex, unul plat."""

    def __init__(self, folder, *, sheets=3, devices=None):
        self.folder = folder
        self.sheets = sheets
        self.devices = devices if devices is not None else [
            ("adf", "Scaner birou (ADF)"), ("flat", "Scaner plat")]
        self.jam_after = None
        self.driver_ui_fails = False
        self.dpi_y = None
        self.list_calls = 0
        self.scans: list[ScanSettings] = []
        self.counter = 0

    def list_devices(self):
        self.list_calls += 1
        return list(self.devices)

    def capabilities(self, device_id):
        if device_id == "adf":
            return {"duplex": True, "adf": True, "resolutions": [150, 200, 300, 600],
                    "color_modes": ["bw", "gray", "color"]}
        return {"duplex": False, "adf": False, "resolutions": [75, 150, 300, 600, 1200]}

    def _image(self, settings):
        self.counter += 1
        path = self.folder / f"scan{self.counter}.png"
        Image.new("L", (300, 400), 255).save(path, dpi=(settings.dpi, settings.dpi))
        return LoadedImage(path, 300, 400, settings.dpi, self.dpi_y or settings.dpi,
                           ColorMode(settings.color_mode))

    def preview(self, settings):
        self.scans.append(settings)
        return self._image(settings)

    def scan(self, settings, *, progress=None, cancel=None):
        self.scans.append(settings)
        if settings.use_driver_ui and self.driver_ui_fails:
            raise ScannerError("driverul nu porneste", driver_ui=True)
        count = self.sheets * (2 if settings.duplex else 1) if settings.use_adf else 1
        for n in range(count):
            if self.jam_after is not None and n == self.jam_after:
                raise ScannerError("hartie blocata", detail="paper_jam")
            yield self._image(settings)


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    c.settings.set("image.auto_process", False)
    yield c
    c.close()


@pytest.fixture
def project(ctx):
    p = OcrProject.create(context=ctx)
    yield p
    p.close()


@pytest.fixture
def scanner(tmp_path):
    folder = tmp_path / "scanari"
    folder.mkdir()
    return FakeScanner(folder)


def test_fake_scanner_follows_the_contract(scanner):
    assert isinstance(scanner, ScannerService)


def test_T_K003_1_devices_are_queried_every_time(scanner):
    session = ScanSession(scanner)
    session.devices()
    session.devices()
    assert scanner.list_calls == 2
    with pytest.raises(NoScannerError):  # niciun scaner → mesaj
        ScanSession(FakeScanner(scanner.folder, devices=[])).devices()


def test_T_K005_1_gray_is_the_default():
    settings = ScanSettings("adf")
    assert settings.color_mode is ColorMode.GRAY
    assert settings.dpi == 300 and settings.brightness == 50


def test_T_K006_1_brightness_warning_and_range():
    assert scan_warnings(ScanSettings("x", brightness=50)) == []
    assert scan_warnings(ScanSettings("x", brightness=15)) == [WARNING_BRIGHTNESS]
    assert scan_warnings(ScanSettings("x", brightness=90)) == [WARNING_BRIGHTNESS]
    with pytest.raises(ValueError):
        validate(ScanSettings("x", brightness=120), {})


def test_T_K007_1_resolution_warnings():
    assert scan_warnings(ScanSettings("x", dpi=300)) == []
    assert scan_warnings(ScanSettings("x", dpi=200)) == [WARNING_DPI_LOW]
    assert scan_warnings(ScanSettings("x", dpi=1200)) == [WARNING_DPI_HIGH]
    assert scan_warnings(ScanSettings("x", dpi=333)) == [WARNING_DPI_ODD]


def test_T_K007_2_unequal_horizontal_and_vertical_dpi(scanner, project):
    scanner.dpi_y = 200
    result = ScanSession(scanner, project).scan_into_project(ScanSettings("flat"))
    assert WARNING_DPI_UNEQUAL in result.warnings


def test_T_K009_1_and_K010_1_only_reported_capabilities(scanner):
    session = ScanSession(scanner)
    with pytest.raises(ValueError):
        session.acquire(ScanSettings("flat", duplex=True))
    with pytest.raises(ValueError):
        session.acquire(ScanSettings("flat", use_adf=True))
    with pytest.raises(ValueError):
        session.acquire(ScanSettings("adf", dpi=1200))  # rezolutie neraportata


def test_T_K010_2_adf_scans_the_whole_feeder_with_duplex(scanner, project):
    result = ScanSession(scanner, project).scan_into_project(
        ScanSettings("adf", use_adf=True, duplex=True))
    assert len(result.pages) == 6 and len(project.pages) == 6
    assert all(p.status is PageStatus.IMPORTED for p in project.pages)


def test_T_K010_3_paper_jam_stops_with_a_message(scanner, project):
    scanner.jam_after = 2
    with pytest.raises(ScannerError) as info:
        ScanSession(scanner, project).scan_into_project(ScanSettings("adf", use_adf=True))
    assert info.value.params["detail"] == "paper_jam"
    assert len(project.pages) == 0


def test_T_K011_1_flatbed_pause_between_scans(scanner, project):
    pauses = []
    session = ScanSession(scanner, project, sleep=pauses.append)
    result = session.scan_into_project(ScanSettings("flat", flatbed_delay_s=5), passes=3)
    assert len(result.pages) == 3 and pauses == [5.0, 5.0]


def test_cancel_keeps_the_sheets_already_scanned(scanner, project):
    session = ScanSession(scanner, project, sleep=lambda s: None)
    result = session.scan_into_project(ScanSettings("flat", flatbed_delay_s=1), passes=5,
                                       cancel=lambda: len(scanner.scans) >= 2)
    assert result.cancelled and len(result.pages) == 2


def test_T_K012_1_preview_is_low_resolution(scanner):
    image = ScanSession(scanner).preview(ScanSettings("flat", dpi=600))
    assert image.dpi_x == 75 and scanner.scans[-1].dpi == 75


def test_T_K004_1_driver_ui_falls_back_to_our_interface(scanner, project):
    scanner.driver_ui_fails = True
    result = ScanSession(scanner, project).scan_into_project(
        ScanSettings("flat", use_driver_ui=True))
    assert len(result.pages) == 1 and WARNING_DRIVER_UI in result.warnings
    assert scanner.scans[-1].use_driver_ui is False


def test_T_K002_1_scanned_pages_follow_auto_processing(scanner, project):
    project.settings().set("image.auto_process", True)
    project.settings().set("image.auto_mode", "preprocess")
    result = ScanSession(scanner, project).scan_into_project(ScanSettings("flat"))
    assert result.pages and project.page(1).status is PageStatus.PREPROCESSED


def test_device_that_disappeared(scanner):
    session = ScanSession(scanner)
    scanner.devices = [("adf", "Scaner birou (ADF)")]
    with pytest.raises(NoScannerError):
        session.acquire(ScanSettings("flat"))

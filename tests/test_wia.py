"""Faza 6d, pasul 6d.2: scanarea prin WIA, cu obiecte COM simulate
(K-003, K-005…K-010, K-012)."""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.errors import NoScannerError, ScannerError
from app.core.images.scanner import ScannerService, ScanSession, ScanSettings
from app.core.images.wia import (
    DUPLEX,
    FEEDER,
    FLATBED,
    INTENT,
    PAPER_EMPTY,
    PAPER_JAM,
    PROP_BRIGHTNESS,
    PROP_CURRENT_INTENT,
    PROP_DOCUMENT_HANDLING_CAPABILITIES,
    PROP_DOCUMENT_HANDLING_SELECT,
    PROP_HORIZONTAL_RESOLUTION,
    PROP_VERTICAL_RESOLUTION,
    WiaScanner,
    wia_brightness,
)
from app.core.model import ColorMode


class Collection:
    def __init__(self, items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]


class Prop:
    def __init__(self, pid, name, value, sub=None):
        self.PropertyID = pid
        self.Name = name
        self.Value = value
        self.SubTypeValues = Collection(sub) if sub is not None else None


class ComError(Exception):
    def __init__(self, hresult):
        super().__init__(hresult)
        self.hresult = hresult


class ImageFile:
    def __init__(self, dpi):
        self.Width, self.Height = 200, 300
        self.HorizontalResolution = self.VerticalResolution = float(dpi)

    def SaveFile(self, path):
        Image.new("L", (self.Width, self.Height), 255).save(path)


class Item:
    def __init__(self, sheets):
        self.sheets = sheets
        self.transfers = 0
        self.jam_at = None
        self.Properties = Collection([
            Prop(PROP_CURRENT_INTENT, "Current Intent", 0),
            Prop(PROP_HORIZONTAL_RESOLUTION, "Horizontal Resolution", 150,
                 sub=[75, 150, 300, 600]),
            Prop(PROP_VERTICAL_RESOLUTION, "Vertical Resolution", 150),
            Prop(PROP_BRIGHTNESS, "Brightness", 0)])

    def value(self, pid):
        return next(p.Value for p in self.Properties.items if p.PropertyID == pid)

    def Transfer(self, fmt):
        if self.jam_at is not None and self.transfers == self.jam_at:
            raise ComError(PAPER_JAM)
        if self.transfers >= self.sheets:
            raise ComError(PAPER_EMPTY)
        self.transfers += 1
        return ImageFile(self.value(PROP_HORIZONTAL_RESOLUTION))


class Device:
    def __init__(self, handling, sheets):
        self.item = Item(sheets)
        self.Items = Collection([self.item])
        self.Properties = Collection([
            Prop(PROP_DOCUMENT_HANDLING_CAPABILITIES, "Capabilities", handling),
            Prop(PROP_DOCUMENT_HANDLING_SELECT, "Select", FLATBED),
            Prop(3096, "Pages", 1)])


class DeviceInfo:
    def __init__(self, device_id, name, kind, device):
        self.DeviceID, self.Type, self.device = device_id, kind, device
        self.Properties = Collection([Prop("Name", "Name", name)])

    def Connect(self):
        return self.device


class Manager:
    def __init__(self, infos):
        self.DeviceInfos = Collection(infos)


@pytest.fixture
def devices():
    return {"adf": Device(FEEDER | FLATBED | DUPLEX, sheets=3),
            "flat": Device(FLATBED, sheets=1)}


@pytest.fixture
def wia(devices, tmp_path):
    infos = [DeviceInfo("adf", "Scaner birou", 1, devices["adf"]),
             DeviceInfo("cam", "Camera web", 2, None),
             DeviceInfo("flat", "Scaner plat", 1, devices["flat"])]
    return WiaScanner(lambda prog_id: Manager(infos), temp_dir=tmp_path)


def test_follows_the_contract(wia):
    assert isinstance(wia, ScannerService)
    assert wia.available() == (True, "")


def test_T_K003_2_only_scanners_are_listed(wia):
    assert wia.list_devices() == [("adf", "Scaner birou"), ("flat", "Scaner plat")]


def test_unavailable_outside_windows(tmp_path, monkeypatch):
    import app.core.images.wia as module

    monkeypatch.setattr(module.sys, "platform", "darwin")
    scanner = WiaScanner(temp_dir=tmp_path)
    assert scanner.available() == (False, "wia_windows_only")
    assert scanner.list_devices() == []
    with pytest.raises(NoScannerError):
        ScanSession(scanner).devices()


def test_T_K009_2_capabilities_from_the_driver(wia):
    adf = wia.capabilities("adf")
    assert adf["adf"] and adf["duplex"] and adf["resolutions"] == [75, 150, 300, 600]
    flat = wia.capabilities("flat")
    assert not flat["adf"] and not flat["duplex"] and flat["flatbed"]


def test_T_K005_2_settings_are_mapped_to_wia_properties(wia, devices):
    settings = ScanSettings("flat", color_mode=ColorMode.COLOR, dpi=300, brightness=75)
    (image,) = list(wia.scan(settings))
    item = devices["flat"].item
    assert item.value(PROP_CURRENT_INTENT) == INTENT[ColorMode.COLOR]
    assert item.value(PROP_HORIZONTAL_RESOLUTION) == 300
    assert item.value(PROP_VERTICAL_RESOLUTION) == 300
    assert item.value(PROP_BRIGHTNESS) == wia_brightness(75) == 500
    assert image.path.is_file() and image.dpi_x == 300


def test_T_K010_4_feeder_until_empty_with_duplex(wia, devices):
    images = list(wia.scan(ScanSettings("adf", use_adf=True, duplex=True)))
    assert len(images) == 3
    select = next(p.Value for p in devices["adf"].Properties.items
                  if p.PropertyID == PROP_DOCUMENT_HANDLING_SELECT)
    assert select == FEEDER | DUPLEX


def test_paper_jam_and_empty_feeder(wia, devices):
    devices["adf"].item.jam_at = 1
    with pytest.raises(ScannerError) as info:
        list(wia.scan(ScanSettings("adf", use_adf=True)))
    assert info.value.params["detail"] == "paper_jam"
    devices["adf"].item.sheets = 0
    devices["adf"].item.jam_at = None
    devices["adf"].item.transfers = 0
    with pytest.raises(ScannerError) as info:
        list(wia.scan(ScanSettings("adf", use_adf=True)))
    assert info.value.params["detail"] == "paper_empty"


def test_T_K012_2_preview_at_low_resolution(wia, devices):
    image = wia.preview(ScanSettings("flat", dpi=600))
    assert devices["flat"].item.value(PROP_HORIZONTAL_RESOLUTION) == 75
    assert image.dpi_x == 75


def test_T_K004_2_driver_ui_failure_falls_back(devices, tmp_path):
    infos = [DeviceInfo("flat", "Scaner plat", 1, devices["flat"])]

    def factory(prog_id):
        if prog_id == "WIA.CommonDialog":
            raise ComError(-1)
        return Manager(infos)

    scanner = WiaScanner(factory, temp_dir=tmp_path)
    images, warnings = ScanSession(scanner).acquire(ScanSettings("flat", use_driver_ui=True))
    assert len(images) == 1 and "warning.scan_driver_ui" in warnings


def test_brightness_mapping_bounds():
    assert wia_brightness(0) == -1000 and wia_brightness(50) == 0
    assert wia_brightness(100) == 1000 and wia_brightness(150) == 1000

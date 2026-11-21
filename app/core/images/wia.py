"""Scanarea prin WIA (faza 6d, pasul 6d.2): K-002, K-003, K-005…K-010.

`WiaScanner` implementeaza `ScannerService` peste obiectele de automatizare
WIA din Windows (`WIA.DeviceManager`, `WIA.CommonDialog`), prin `comtypes`
(MIT). Pe alte sisteme nu exista WIA: lista de dispozitive e goala si
`available()` spune de ce.

Obiectele COM se obtin printr-o fabrica injectabila, ca maparea setarilor pe
proprietatile WIA sa se poata verifica in teste pe orice sistem. Scanarea cu un
aparat real o verifica utilizatorul (docs/plan/faza_6d_pasi.md, decizia 3).
"""

from __future__ import annotations

import sys
import tempfile
import uuid
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

from app.core.errors import NoScannerError, OperationCancelledError, ScannerError
from app.core.images.loader import LoadedImage
from app.core.images.scanner import ScanSettings
from app.core.model import CancelToken, ColorMode, Progress, ProgressCallback

# --- constantele WIA (wiadef.h, Windows SDK) --------------------------------------------

SCANNER_DEVICE_TYPE = 1
"""WiaDeviceType.ScannerDeviceType."""

PROP_NAME = "Name"
PROP_DOCUMENT_HANDLING_CAPABILITIES = 3086
PROP_DOCUMENT_HANDLING_SELECT = 3088
PROP_PAGES = 3096
PROP_CURRENT_INTENT = 6146
PROP_HORIZONTAL_RESOLUTION = 6147
PROP_VERTICAL_RESOLUTION = 6148
PROP_BRIGHTNESS = 6154

FEEDER, FLATBED, DUPLEX = 0x001, 0x002, 0x004
"""WIA_DPS_DOCUMENT_HANDLING_*."""

INTENT = {ColorMode.COLOR: 0x1, ColorMode.GRAY: 0x2, ColorMode.BW: 0x4}
"""WIA_INTENT_IMAGE_TYPE_COLOR / GRAYSCALE / TEXT (K-005)."""

FORMAT_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
"""wiaFormatPNG."""

PAPER_EMPTY = -2145320957  # 0x80210003, WIA_ERROR_PAPER_EMPTY
PAPER_JAM = -2145320958  # 0x80210002, WIA_ERROR_PAPER_JAM
OFFLINE = -2145320955  # 0x80210005, WIA_ERROR_OFFLINE
"""Codurile HRESULT ale erorilor de hartie si de dispozitiv."""


def _hresult(exc: Exception) -> int | None:
    for value in (getattr(exc, "hresult", None), *(getattr(exc, "args", ()) or ())):
        if isinstance(value, int):
            return value
    return None


def wia_brightness(percent: int) -> int:
    """K-006: 0-100 in interfata → -1000…1000 in WIA (50 = 0)."""
    return round((max(0, min(percent, 100)) - 50) * 20)


def _com_factory(prog_id: str) -> Any:  # pragma: no cover - numai pe Windows
    import comtypes.client

    return comtypes.client.CreateObject(prog_id)


class WiaScanner:
    """`ScannerService` peste WIA."""

    def __init__(self, factory: Callable[[str], Any] | None = None, *,
                 temp_dir: Path | None = None) -> None:
        self._factory = factory or (_com_factory if sys.platform == "win32" else None)
        self._temp = Path(temp_dir or tempfile.gettempdir()) / "doculens-scan"

    # --- disponibilitatea -------------------------------------------------------------

    def available(self) -> tuple[bool, str]:
        """(da/nu, motivul): WIA exista numai pe Windows, cu `comtypes`."""
        if self._factory is None:
            return False, "wia_windows_only"
        try:
            self._manager()
        except Exception:  # noqa: BLE001 - orice eroare COM inseamna „indisponibil”
            return False, "wia_unavailable"
        return True, ""

    def _manager(self) -> Any:
        if self._factory is None:
            raise NoScannerError("WIA exista numai pe Windows")
        return self._factory("WIA.DeviceManager")

    def _infos(self) -> list[Any]:
        infos = self._manager().DeviceInfos
        return [infos.Item(i) for i in range(1, infos.Count + 1)]

    @staticmethod
    def _prop(holder: Any, key: int | str) -> Any:
        props = holder.Properties
        for i in range(1, props.Count + 1):
            prop = props.Item(i)
            if prop.PropertyID == key or prop.Name == key:
                return prop
        return None

    def _value(self, holder: Any, key: int | str, default: Any = None) -> Any:
        prop = self._prop(holder, key)
        return default if prop is None else prop.Value

    def _set(self, holder: Any, key: int, value: Any) -> None:
        prop = self._prop(holder, key)
        if prop is not None:
            prop.Value = value

    # --- ScannerService ------------------------------------------------------------

    def list_devices(self) -> list[tuple[str, str]]:
        """K-003: reinterogat la fiecare apel; numai scanerele."""
        if self._factory is None:
            return []
        try:
            infos = self._infos()
        except Exception:  # noqa: BLE001 - WIA oprit: nicio lista
            return []
        return [(str(info.DeviceID), str(self._value(info, PROP_NAME, info.DeviceID)))
                for info in infos if int(info.Type) == SCANNER_DEVICE_TYPE]

    def _connect(self, device_id: str) -> Any:
        for info in self._infos():
            if str(info.DeviceID) == device_id:
                return info.Connect()
        raise NoScannerError("dispozitivul ales nu mai e disponibil", device=device_id)

    def capabilities(self, device_id: str) -> Mapping[str, Any]:
        """K-009, K-010: duplex si ADF numai daca driverul le raporteaza."""
        device = self._connect(device_id)
        handling = int(self._value(device, PROP_DOCUMENT_HANDLING_CAPABILITIES, FLATBED) or 0)
        item = device.Items.Item(1)
        prop = self._prop(item, PROP_HORIZONTAL_RESOLUTION)
        resolutions: list[int] = []
        sub = getattr(prop, "SubTypeValues", None) if prop is not None else None
        if sub is not None:
            resolutions = sorted({int(sub.Item(i)) for i in range(1, sub.Count + 1)})
        return {"duplex": bool(handling & DUPLEX), "adf": bool(handling & FEEDER),
                "flatbed": bool(handling & FLATBED),
                "resolutions": resolutions or None,
                "color_modes": [m.value for m in INTENT]}

    def _configure(self, device: Any, settings: ScanSettings) -> Any:
        handling = FEEDER if settings.use_adf else FLATBED
        if settings.duplex:
            handling |= DUPLEX
        self._set(device, PROP_DOCUMENT_HANDLING_SELECT, handling)
        if settings.use_adf:
            self._set(device, PROP_PAGES, 0)  # 0 = cat are alimentatorul
        item = device.Items.Item(1)
        self._set(item, PROP_CURRENT_INTENT, INTENT[ColorMode(settings.color_mode)])
        self._set(item, PROP_HORIZONTAL_RESOLUTION, settings.dpi)
        self._set(item, PROP_VERTICAL_RESOLUTION, settings.dpi)
        self._set(item, PROP_BRIGHTNESS, wia_brightness(settings.brightness))
        return item

    def _save(self, image: Any, settings: ScanSettings) -> LoadedImage:
        self._temp.mkdir(parents=True, exist_ok=True)
        path = self._temp / f"scan-{uuid.uuid4().hex}.png"
        image.SaveFile(str(path))
        return LoadedImage(path, int(image.Width), int(image.Height),
                           round(image.HorizontalResolution),
                           round(image.VerticalResolution),
                           ColorMode(settings.color_mode))

    def preview(self, settings: ScanSettings) -> LoadedImage:
        """K-012: o scanare rapida, la rezolutie mica, de pe geam."""
        device = self._connect(settings.device_id)
        quick = ScanSettings(settings.device_id, settings.color_mode, min(settings.dpi, 75),
                             settings.brightness)
        return self._save(self._configure(device, quick).Transfer(FORMAT_PNG), quick)

    def scan(self, settings: ScanSettings, *, progress: ProgressCallback | None = None,
             cancel: CancelToken | None = None) -> Iterator[LoadedImage]:
        """Cu ADF, foile pana se goleste alimentatorul; pe geam, o foaie."""
        if settings.use_driver_ui:  # K-004: interfata driverului
            yield from self._driver_ui(settings)
            return
        device = self._connect(settings.device_id)
        item = self._configure(device, settings)
        n = 0
        while True:
            if cancel is not None and cancel():
                raise OperationCancelledError("scanarea a fost anulata")
            try:
                image = item.Transfer(FORMAT_PNG)
            except Exception as exc:
                code = _hresult(exc)
                if code == PAPER_EMPTY and n:
                    return  # alimentatorul s-a golit
                if code == PAPER_JAM:
                    raise ScannerError("hartie blocata", detail="paper_jam") from exc
                if code == PAPER_EMPTY:
                    raise ScannerError("alimentatorul e gol", detail="paper_empty") from exc
                if code == OFFLINE:
                    raise NoScannerError("scanerul nu raspunde",
                                         device=settings.device_id) from exc
                raise ScannerError("scanarea a esuat", detail=str(code)) from exc
            n += 1
            if progress is not None:
                progress(Progress(n, 0, "stage.scanning", ""))
            yield self._save(image, settings)
            if not settings.use_adf:
                return

    def _driver_ui(self, settings: ScanSettings) -> Iterator[LoadedImage]:
        try:
            dialog = self._factory("WIA.CommonDialog")
            image = dialog.ShowAcquireImage(SCANNER_DEVICE_TYPE, 0, 0, FORMAT_PNG,
                                            False, True, False)
        except Exception as exc:
            raise ScannerError("interfata driverului nu porneste", driver_ui=True) from exc
        if image is not None:  # None: utilizatorul a renuntat
            yield self._save(image, settings)


def default_scanner() -> WiaScanner:
    """Serviciul de scanare al aplicatiei. INCOMPLET, marcat: TWAIN vine cu o
    legatura proprie, verificata pe un scaner real (faza_6d_pasi.md, decizia 2)."""
    return WiaScanner()

"""Scanarea (faza 6d, pasul 6d.1): K-002…K-013.

Contractul din SPEC_05 sectiunea 5: `ScanSettings` si `ScannerService`
(singurul loc din nucleu care vorbeste cu hardware). Aici sunt regulile
independente de aparat: validarea setarilor dupa ce raporteaza dispozitivul
(duplex si ADF numai daca exista, K-009, K-010), avertismentele pentru
luminozitate si rezolutie (K-006, K-007), sesiunea care adauga paginile in
proiect (K-002), pauza dintre scanarile pe geam (K-011), revenirea la
interfata proprie cand interfata driverului nu merge (K-004).

Dispozitivele reale sunt in backenduri (WIA in 6d.2); testele folosesc un
dispozitiv simulat.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from app.core.errors import NoScannerError, OperationCancelledError, ScannerError
from app.core.images.loader import LoadedImage
from app.core.model import CancelToken, ColorMode, PageData, ProgressCallback, Rect

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

STANDARD_DPI = (150, 200, 240, 300, 400, 500, 600)
"""K-007: rezolutiile obisnuite; altele sunt „nestandard”."""

BRIGHTNESS_RANGE = (0, 100)
BRIGHTNESS_OK = (30, 70)
"""K-006: 50% merge aproape mereu; in afara intervalului apare un avertisment."""

DPI_LOW, DPI_HIGH = 250, 600
"""K-007: sub 250 sau peste 600 se recomanda ajustarea."""

WARNING_BRIGHTNESS = "warning.scan_brightness"
WARNING_DPI_LOW = "warning.scan_dpi_low"
WARNING_DPI_HIGH = "warning.scan_dpi_high"
WARNING_DPI_ODD = "warning.scan_dpi_nonstandard"
WARNING_DPI_UNEQUAL = "warning.scan_dpi_unequal"
WARNING_DRIVER_UI = "warning.scan_driver_ui"
"""Cheile avertismentelor (textele sunt in interfata)."""


# SPEC_05 sect. 5. K-003..K-002
@dataclass(slots=True)
class ScanSettings:
    """K-003..K-002."""

    device_id: str
    color_mode: ColorMode = ColorMode.GRAY
    """K-007: gri e recomandarea implicita pentru OCR."""
    dpi: int = 300
    """K-009: peste 600 se avertizeaza."""
    brightness: int = 50
    page_size: str = "A4"
    scan_area: Rect | None = None
    duplex: bool = False
    use_adf: bool = False
    flatbed_delay_s: int | None = None
    use_driver_ui: bool = False
    image_format: str = "png"


# SPEC_05 sect. 5. K-003..K-002, A-040
@runtime_checkable
class ScannerService(Protocol):
    """K-003..K-002, A-040. Singurul loc din nucleu care vorbeste cu hardware."""

    def list_devices(self) -> list[tuple[str, str]]:
        """(id, nume afisabil). Lista se reinterogheaza la fiecare apel (K-004)."""
        ...

    def capabilities(self, device_id: str) -> Mapping[str, Any]:
        """Ce raporteaza driverul: duplex, ADF, rezolutii, moduri de culoare.
        Interfata dezactiveaza ce nu e raportat (K-012, K-013)."""
        ...

    def preview(self, settings: ScanSettings) -> LoadedImage:
        """K-015: scanare rapida, la rezolutie mica."""
        ...

    def scan(
        self,
        settings: ScanSettings,
        *,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> Iterator[LoadedImage]:
        """Generator: cu ADF produce pagini pana se goleste alimentatorul.

        Erori: `NoScannerError`, `ScannerError`.
        """
        ...


# --- regulile ------------------------------------------------------------------------


# K-006, K-007
def scan_warnings(settings: ScanSettings) -> list[str]:
    """Avertismentele pentru setarile alese (nu opresc scanarea)."""
    out: list[str] = []
    low, high = BRIGHTNESS_OK
    if not low <= settings.brightness <= high:
        out.append(WARNING_BRIGHTNESS)
    if settings.dpi < DPI_LOW:
        out.append(WARNING_DPI_LOW)
    elif settings.dpi > DPI_HIGH:
        out.append(WARNING_DPI_HIGH)
    elif settings.dpi not in STANDARD_DPI:
        out.append(WARNING_DPI_ODD)
    return out


def image_warnings(image: LoadedImage) -> list[str]:
    """K-007: rezolutia orizontala si cea verticala trebuie sa coincida."""
    return [WARNING_DPI_UNEQUAL] if image.dpi_x != image.dpi_y else []


def validate(settings: ScanSettings, capabilities: Mapping[str, Any]) -> None:
    """Setarile pe care dispozitivul nu le poate face sunt refuzate (ValueError)."""
    low, high = BRIGHTNESS_RANGE
    if not low <= settings.brightness <= high:
        raise ValueError(f"luminozitatea trebuie sa fie intre {low} si {high} (K-006)")
    if settings.dpi <= 0:
        raise ValueError("rezolutia trebuie sa fie pozitiva (K-007)")
    if settings.duplex and not capabilities.get("duplex"):  # K-009
        raise ValueError("dispozitivul nu raporteaza scanare duplex")
    if settings.use_adf and not capabilities.get("adf"):  # K-010
        raise ValueError("dispozitivul nu raporteaza alimentator automat")
    modes = capabilities.get("color_modes")
    if modes and ColorMode(settings.color_mode).value not in {ColorMode(m).value
                                                               for m in modes}:
        raise ValueError(f"modul de culoare {settings.color_mode} nu e suportat")
    resolutions = capabilities.get("resolutions")
    if resolutions and settings.dpi not in resolutions:
        raise ValueError(f"rezolutia {settings.dpi} nu e suportata; permise: {resolutions}")
    if settings.flatbed_delay_s is not None and settings.flatbed_delay_s < 0:
        raise ValueError("pauza dintre scanari nu poate fi negativa (K-011)")


# --- sesiunea --------------------------------------------------------------------------


@dataclass
class ScanResult:
    pages: list[PageData]
    warnings: list[str]
    cancelled: bool = False


class ScanSession:
    """Scanarea in proiectul OCR: dispozitivele, verificarile, paginile adaugate."""

    def __init__(self, service: ScannerService, project: OcrProject | None = None, *,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.service = service
        self.project = project
        self._sleep = sleep

    def devices(self) -> list[tuple[str, str]]:
        """K-003: lista se reinterogheaza la fiecare deschidere; goala → mesaj."""
        found = self.service.list_devices()
        if not found:
            raise NoScannerError("niciun dispozitiv de scanare")
        return found

    def preview(self, settings: ScanSettings) -> LoadedImage:
        """K-012: scanare rapida, la rezolutie mica."""
        self._check(settings)
        return self.service.preview(replace(settings, dpi=min(settings.dpi, 75)))

    def _check(self, settings: ScanSettings) -> Mapping[str, Any]:
        if settings.device_id not in {d for d, _ in self.service.list_devices()}:
            raise NoScannerError("dispozitivul ales nu mai e disponibil",
                                 device=settings.device_id)
        capabilities = self.service.capabilities(settings.device_id)
        validate(settings, capabilities)
        return capabilities

    def acquire(self, settings: ScanSettings, *, passes: int = 1,
                progress: ProgressCallback | None = None,
                cancel: CancelToken | None = None) -> tuple[list[LoadedImage], list[str]]:
        """Imaginile scanate. Pe geam, cu pauza (K-011), se scaneaza `passes` foi,
        cu pauza intre ele; cu ADF, cate are alimentatorul (K-010)."""
        self._check(settings)
        warnings = scan_warnings(settings)
        images: list[LoadedImage] = []
        rounds = 1 if settings.use_adf else max(1, passes)
        for n in range(rounds):
            if n and settings.flatbed_delay_s:
                self._sleep(float(settings.flatbed_delay_s))
            if cancel is not None and cancel():
                if images:
                    break
                raise OperationCancelledError("scanarea a fost anulata")
            images += self._scan_once(settings, warnings, progress, cancel)
        for image in images:
            warnings += [w for w in image_warnings(image) if w not in warnings]
        return images, warnings

    def _scan_once(self, settings: ScanSettings, warnings: list[str],
                   progress: ProgressCallback | None, cancel: CancelToken | None
                   ) -> list[LoadedImage]:
        try:
            return list(self.service.scan(settings, progress=progress, cancel=cancel))
        except ScannerError as exc:
            if settings.use_driver_ui and exc.params.get("driver_ui"):
                # K-004: driver incompatibil → interfata proprie
                warnings.append(WARNING_DRIVER_UI)
                return list(self.service.scan(replace(settings, use_driver_ui=False),
                                              progress=progress, cancel=cancel))
            raise

    def scan_into_project(self, settings: ScanSettings, *, passes: int = 1,
                          at: int | None = None,
                          progress: ProgressCallback | None = None,
                          cancel: CancelToken | None = None) -> ScanResult:
        """K-002: paginile scanate se adauga in proiect; prelucrarea automata
        (J-051) o face proiectul dupa setari. Anularea inainte de prima foaie nu
        adauga nimic; foile deja scanate raman."""
        if self.project is None:
            raise ValueError("sesiunea nu are proiect")
        try:
            images, warnings = self.acquire(settings, passes=passes, progress=progress,
                                            cancel=cancel)
        except OperationCancelledError:
            return ScanResult([], [], cancelled=True)
        cancelled = cancel is not None and cancel()
        pages = self._add(images, at) if images else []
        return ScanResult(pages, warnings, cancelled)

    def _add(self, images: Sequence[LoadedImage], at: int | None) -> list[PageData]:
        added, errors = self.project.add_images([img.path for img in images], at=at)
        if errors:
            path, error = errors[0]
            raise ScannerError("imaginea scanata nu s-a putut adauga",
                               detail=str(path)) from error
        return list(added)

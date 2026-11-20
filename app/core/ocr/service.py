"""Serviciul de recunoastere: paginile, ordinea pasilor, paralelizarea.

Implementeaza `RecognitionService` din SPEC_05 sectiunea 7, pasul 4.3 din
docs/plan/faza_4_pasi.md. PDF-urile cu strat de text (evaluate_text_layer,
choose_mode, pull_and_recognize: N-008..N-012) vin in pasul 4.4.

INCOMPLET, marcat (mutat in 4.5): recunoasterea tabelelor pe celule si
mutarea paginilor intre proiecte impreuna cu textul lor.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from app.core.errors import OperationCancelledError
from app.core.model import (
    CancelToken,
    PageStatus,
    PageWarning,
    Progress,
    ProgressCallback,
)
from app.core.ocr.engine import OcrEngine, RecognitionResult, TesseractEngine
from app.core.ocr.store import save_result

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

LOW_DPI = 250
"""N-100, N-023: sub 250 dpi se cere rescanarea la o rezolutie mai mare."""


def default_workers(setting: int | None) -> int:
    """N-027, X-141: None = toate nucleele minus unul."""
    if setting:
        return max(1, int(setting))
    return max(1, (os.cpu_count() or 2) - 1)


# SPEC_05 sect. 7. N-001..N-028
class RecognitionService:
    def __init__(self, project: OcrProject, engine: OcrEngine | None = None,
                 analyzer: Any = None) -> None:
        self._project = project
        settings = project.settings()
        self._engine = engine or TesseractEngine(
            keep_cedilla=bool(settings.get("ocr.keep_cedilla_diacritics")))
        self._analyzer = analyzer

    # N-003, N-004, N-022, N-023, N-027, N-028
    def recognize_pages(
        self,
        numbers: Sequence[int] | None = None,
        skip_recognized: bool = True,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[int]:
        """Recunoaste paginile (implicit toate). Paginile deja recunoscute se
        sar (N-003). O pagina fara zone se analizeaza intai (N-004).
        Paginile se recunosc in paralel (N-027); textul se scrie pe rand.
        Anularea opreste dupa paginile in lucru; cele terminate raman (N-028).
        Un singur pas de undo. Intoarce paginile recunoscute."""
        project = self._project
        all_numbers = list(numbers) if numbers is not None else [
            pg.page_number for pg in project.pages]
        todo = [n for n in all_numbers if not (
            skip_recognized and project.page(n).status in (PageStatus.RECOGNIZED,
                                                           PageStatus.VERIFIED))]
        if not todo:
            return []
        empty = [n for n in todo if not project.page(n).areas]
        if empty:
            project.analyze_pages(empty, analyzer=self._analyzer, cancel=cancel)
        settings = project.settings().ocr_settings()
        ids = [project.page(n).id for n in todo]
        done: list[int] = []
        total = len(ids)
        workers = default_workers(settings.max_threads)
        with project._history("recognize_pages", {"pages": todo}), \
                ThreadPoolExecutor(max_workers=workers) as pool:
            pending: dict[Future[RecognitionResult], int] = {}
            queue = list(ids)

            def submit() -> None:
                pid = queue.pop(0)
                page = next(p for p in project.pages if p.id == pid)
                pending[pool.submit(self._engine.recognize_page, page, settings)] = pid

            for _ in range(min(len(queue), workers)):
                submit()
            cancelled = False
            while pending:
                future = next(iter(pending))
                pid = pending.pop(future)
                result = future.result()
                page = next(p for p in project.pages if p.id == pid)
                result.warnings += self._warnings(page)
                save_result(project, page.page_number, result, record=False)
                done.append(page.page_number)
                if progress is not None:
                    progress(Progress(len(done), total, "stage.recognizing",
                                      str(page.page_number)))
                if cancel is not None and cancel():
                    cancelled = True
                    queue.clear()
                if queue:
                    submit()
        if cancelled:
            raise OperationCancelledError(done=len(done), total=total)
        return sorted(done)

    # N-023
    def _warnings(self, page: Any) -> list[PageWarning]:
        if min(page.dpi_x, page.dpi_y) < LOW_DPI:
            return [PageWarning("warning", "LOW_RESOLUTION", "warning.low_resolution",
                                {"dpi": min(page.dpi_x, page.dpi_y)})]
        return []

    # N-024, N-025 (SPEC_05: N-022, N-023, O-002)
    def mark_uncertain(self, result: RecognitionResult, threshold: float) -> None:
        """Recalculeaza cuvintele nesigure dupa un prag nou."""
        for block in result.blocks:
            for line in block.lines:
                for word in line.words:
                    word.is_uncertain = word.confidence < threshold
        result.uncertain_count = sum(
            w.is_uncertain for b in result.blocks for line in b.lines for w in line.words)

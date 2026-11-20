"""Serviciul de recunoastere: paginile, ordinea pasilor, paralelizarea.

Implementeaza `RecognitionService` din SPEC_05 sectiunea 7: pasul 4.3
(paginile, paralelizarea) si 4.4 (PDF-urile cu strat de text: N-008..N-012)
din docs/plan/faza_4_pasi.md.

INCOMPLET, marcat (mutat in 4.5): recunoasterea tabelelor pe celule si
mutarea paginilor intre proiecte impreuna cu textul lor.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.errors import OperationCancelledError
from app.core.model import (
    AreaType,
    CancelToken,
    PageStatus,
    PageWarning,
    PdfRecognitionMode,
    Progress,
    ProgressCallback,
)
from app.core.ocr import textlayer
from app.core.ocr.engine import OcrEngine, RecognitionResult, TesseractEngine
from app.core.ocr.store import save_result

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

SAMPLE_PX = 1500
"""Latura mostrei pe care se alege limba (P-001)."""

DISTINCT_MIN = 1.0
"""P-001: litere proprii unei limbi la 100 de litere, sub care nu conteaza."""

DISTINCT_WEIGHT = 5.0
"""P-001: cate puncte de incredere valoreaza o litera proprie la 100."""

MANY_LANGUAGES = 3
"""P-009: peste 3 limbi, recunoasterea devine mai lenta: mesaj informativ."""

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
        auto_lang = project.settings().get("lang.mode") == "auto" and len(settings.languages) > 1
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
                # stratul de text se citeste pe firul principal: SQLite nu
                # permite conexiunea proiectului din firele de lucru
                layer = self._text_layer(page)
                pending[pool.submit(self._recognize_one, page, settings, layer, auto_lang)] = pid

            for _ in range(min(len(queue), workers)):
                submit()
            cancelled = False
            while pending:
                future = next(iter(pending))
                pid = pending.pop(future)
                result = future.result()
                page = next(p for p in project.pages if p.id == pid)
                result.warnings += self._warnings(page, None if auto_lang else settings)
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

    def _recognize_one(self, page: Any, settings: Any, text: textlayer.PdfPageText | None,
                       auto_lang: bool = False) -> RecognitionResult:
        """N-008..N-012: o pagina dintr-un PDF digital isi foloseste stratul de
        text; restul (scanari, imagini, PDF-uri cu text stricat) trec prin OCR.
        Ruleaza pe un fir de lucru: nu atinge baza de date."""
        if text is not None and textlayer.choose_mode(
                text, settings.pdf_mode) is PdfRecognitionMode.TEXT_ONLY:
            return self.pull_and_recognize(page, settings, text=text, auto_lang=auto_lang)
        if auto_lang:
            settings = self._with_language(page, settings)
        return self._engine.recognize_page(page, settings)

    def _with_language(self, page: Any, settings: Any) -> Any:
        return replace(settings, languages=(self.choose_language(page, settings),))

    def _text_layer(self, page: Any) -> textlayer.PdfPageText | None:
        """Stratul de text, numai daca imaginea paginii corespunde inca PDF-ului.
        INCOMPLET, marcat: o pagina rotita sau preprocesata trece pe OCR;
        coordonatele stratului s-ar putea transforma odata cu imaginea."""
        if page.source_file is None or page.source_file.suffix.lower() != ".pdf":
            return None
        if page.rotation or self._project.applied_operations(page.page_number):
            return None
        if not page.source_file.is_file():
            return None
        return textlayer.read_page(page.source_file, page.source_page or 1)

    # N-011 (SPEC_05 il numeste N-009)
    def evaluate_text_layer(self, path: Path, page: int) -> float:
        """Calitatea stratului de text existent, 0..1."""
        text = textlayer.read_page(path, page)
        return 0.0 if text is None else textlayer.evaluate(text)

    # N-008, N-009
    def choose_mode(self, path: Path, page: int, settings: Any) -> PdfRecognitionMode:
        return textlayer.choose_mode(textlayer.read_page(path, page), settings.pdf_mode)

    # N-012 (SPEC_05 il numeste N-010)
    def pull_and_recognize(self, page: Any, settings: Any, cancel: CancelToken | None = None,
                           *, text: textlayer.PdfPageText | None = None,
                           auto_lang: bool = False) -> RecognitionResult:
        """Documentele mixte: textul digital se ia din strat, iar zonele de text
        fara niciun cuvant digital (imagini scanate in pagina) se recunosc."""
        start = time.perf_counter()
        text = text or self._text_layer(page)
        language = settings.languages[0] if settings.languages else None
        result = RecognitionResult(page.page_number)
        targets = [a for a in page.areas if a.area_type in (AreaType.TEXT, AreaType.RECOGNITION)]
        words = text.words if text is not None else []
        sx = page.width_px / text.width_pt if text else 1.0
        sy = page.height_px / text.height_pt if text else 1.0
        for area in targets:
            mine = [(w, b) for w, b in words if area.bbox.contains(
                (round((b[0] + b[2]) / 2 * sx), round((text.height_pt - (b[1] + b[3]) / 2) * sy)))]
            if mine:
                part = textlayer.PdfPageText(mine, text.width_pt, text.height_pt, [])
                blocks = textlayer.to_blocks(part, page.width_px, page.height_px, language)
                result.area_blocks[area.id] = blocks
                result.blocks += blocks
            else:
                if auto_lang:  # P-001: limba se alege doar daca e nevoie de OCR
                    settings, auto_lang = self._with_language(page, settings), False
                ocr = self._engine.recognize_area(page, area, settings, cancel)
                result.area_blocks.update(ocr.area_blocks)
                result.blocks += ocr.blocks
        all_words = [w for b in result.blocks for ln in b.lines for w in ln.words]
        result.avg_confidence = (round(sum(w.confidence for w in all_words) / len(all_words), 2)
                                 if all_words else 0.0)
        result.uncertain_count = sum(w.is_uncertain for w in all_words)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        return result

    # P-001: „Automatically select OCR languages from the following list”
    def choose_language(self, page: Any, settings: Any) -> str:
        """Limba din lista care citeste cel mai bine o mostra a paginii
        (zonele de text, cel mult SAMPLE_PX x SAMPLE_PX/2).
        Recunoasterea cu toate limbile deodata pierde diacriticele romanesti
        (docs/plan/faza_4_pasi.md, constatarea din 4.1); de aceea se alege una.

        [DECIZIE] Increderea medie singura nu ajunge: modelul `eng` citeste
        textul romanesc aproape la fel de sigur, doar fara diacritice. Se
        adauga dovada din text: literele non-ASCII pe care numai un model le
        produce (ș, ă, î la `ron`; ä, ö la `deu`), daca sunt cel putin
        DISTINCT_MIN la 100 de litere (o litera ratacita nu conteaza)."""
        from collections import Counter

        from app.core.model import AreaData, Rect

        candidates = list(settings.languages)
        texts = [a.bbox for a in page.areas
                 if a.area_type in (AreaType.TEXT, AreaType.RECOGNITION)]
        if texts:
            x0, y0 = min(b.x for b in texts), min(b.y for b in texts)
            x1 = max(b.x + b.w for b in texts)
            y1 = max(b.y + b.h for b in texts)
        else:
            x0, y0, x1, y1 = 0, 0, page.width_px, page.height_px
        sample = Rect(x0, y0, min(x1 - x0, SAMPLE_PX), min(y1 - y0, SAMPLE_PX // 2))
        probe = AreaData(None, AreaType.TEXT, [], 0, bbox=sample)
        outputs: dict[str, tuple[float, str]] = {}
        for code in candidates:
            result = self._engine.recognize_area(page, probe, replace(settings, languages=(code,)))
            text = " ".join(w.text for b in result.blocks for ln in b.lines for w in ln.words)
            outputs[code] = (result.avg_confidence if text else 0.0, text)

        def special(text: str) -> Counter[str]:
            return Counter(c for c in text if c.isalpha() and not c.isascii())

        best, best_score = candidates[0], -1.0
        for code, (confidence, text) in outputs.items():
            others: Counter[str] = Counter()
            for other, (_, t) in outputs.items():
                if other != code:
                    others |= special(t)
            letters = sum(c.isalpha() for c in text) or 1
            rate = 100 * sum((special(text) - others).values()) / letters
            score = confidence + (DISTINCT_WEIGHT * rate if rate >= DISTINCT_MIN else 0.0)
            if score > best_score:
                best, best_score = code, score
        return best

    # N-023, P-009
    def _warnings(self, page: Any, settings: Any = None) -> list[PageWarning]:
        out = []
        if min(page.dpi_x, page.dpi_y) < LOW_DPI:
            out.append(PageWarning("warning", "LOW_RESOLUTION", "warning.low_resolution",
                                   {"dpi": min(page.dpi_x, page.dpi_y)}))
        if settings is not None and len(settings.languages) > MANY_LANGUAGES:
            out.append(PageWarning("info", "MANY_LANGUAGES", "warning.many_languages",
                                   {"count": len(settings.languages)}))
        return out

    # N-024, N-025 (SPEC_05: N-022, N-023, O-002)
    def mark_uncertain(self, result: RecognitionResult, threshold: float) -> None:
        """Recalculeaza cuvintele nesigure dupa un prag nou."""
        for block in result.blocks:
            for line in block.lines:
                for word in line.words:
                    word.is_uncertain = word.confidence < threshold
        result.uncertain_count = sum(
            w.is_uncertain for b in result.blocks for line in b.lines for w in line.words)

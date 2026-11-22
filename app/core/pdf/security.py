"""Securitatea documentelor PDF: redactarea (faza 7, pasul 7.2b), parolele si
permisiunile, stergerea datelor (faza 10, pasul 10.1).

`SecurityService` din SPEC_05: `apply` si `remove_protection` (G-001…G-012),
`redact_regions` (G-020, G-021), `redact_by_keywords` (C-025, C-026),
`delete_objects_and_data` (G-022…G-024, G-111).

Protectia se scrie la urmatoarea salvare a documentului (G-012: peste fisierul
deschis sau intr-unul nou). Criptarea e AES-128 sau AES-256; RC4 se citeste,
dar nu se scrie niciodata (G-010).

CLAUDE.md §6.7: dupa fiecare redactare se extrage textul si se verifica
absenta lui; daca mai apare, operatia se anuleaza (documentul revine la starea
dinainte) si se ridica `RedactionVerificationError`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pikepdf

from app.core.errors import SamePasswordError, WrongPasswordError
from app.core.model import EncryptionLevel, PrintPermission, Rect
from app.core.pdf.redact import PageEdit, rebuild_page, verify_removed
from app.core.pdf.text import SOURCE_TEXT, SearchHit

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

DEFAULT_REDACTION_COLOR = "#000000"
"""G-101: culoarea implicita a redactarii."""
REDACTION_COLORS = ("#e53935", "#fb8c00", "#fdd835", "#43a047", "#00acc1", "#1e88e5",
                    "#8e24aa", "#000000")
"""G-100: culorile barei (rosu, portocaliu, galben, verde, turcoaz, albastru, mov,
negru); lista e o setare (`pdf_editor.redaction_colors`), nu un numar fix."""


@dataclass
class SecurityOptions:
    """G-001…G-011."""

    open_password: str | None = None
    permissions_password: str | None = None
    print_permission: PrintPermission = PrintPermission.HIGH_RES
    allow_editing: bool = True
    allow_copying: bool = True
    allow_annotations: bool = True
    allow_form_filling: bool = True
    allow_screen_readers: bool = True
    allow_assembly: bool = True
    encryption: EncryptionLevel = EncryptionLevel.AES_256
    encrypt_metadata: bool = True
    """G-011: False = `All document contents except metadata`."""

    def validate(self) -> None:
        """G-004: `SamePasswordError` cand cele doua parole coincid; cel putin
        una trebuie data."""
        if not self.open_password and not self.permissions_password:
            raise ValueError("nicio parola: documentul nu se protejeaza")
        if self.open_password and self.open_password == self.permissions_password:
            raise SamePasswordError("parola de permisiuni trebuie sa fie diferita")
        EncryptionLevel(self.encryption)
        PrintPermission(self.print_permission)

    def encryption_object(self) -> pikepdf.Encryption:
        """G-005: parola de permisiuni e parola de proprietar, deci deschide si
        ea documentul. Fara parola de permisiuni, permisiunile raman toate."""
        self.validate()
        restricted = bool(self.permissions_password)
        printing = PrintPermission(self.print_permission)
        allow = pikepdf.Permissions(
            accessibility=self.allow_screen_readers or not restricted,
            extract=self.allow_copying or not restricted,
            modify_annotation=self.allow_annotations or not restricted,
            modify_assembly=self.allow_assembly or not restricted,
            modify_form=self.allow_form_filling or not restricted,
            modify_other=self.allow_editing or not restricted,
            print_lowres=printing is not PrintPermission.NONE or not restricted,
            print_highres=printing is PrintPermission.HIGH_RES or not restricted)
        user = self.open_password or ""
        owner = self.permissions_password or self.open_password or ""
        aes256 = EncryptionLevel(self.encryption) is EncryptionLevel.AES_256
        return pikepdf.Encryption(user=user, owner=owner, allow=allow, aes=True,
                                  R=6 if aes256 else 4, metadata=self.encrypt_metadata)


def _group(regions: Sequence[tuple[int, Rect]], total: int) -> dict[int, list[Rect]]:
    pages: dict[int, list[Rect]] = {}
    for number, rect in regions:
        if not 1 <= number <= total:
            raise ValueError(f"pagina {number} nu exista (1..{total})")
        if rect.w <= 0 or rect.h <= 0:
            raise ValueError("zona de redactat e goala")
        pages.setdefault(number, []).append(rect)
    return pages


class SecurityService:
    """G-001…G-024, C-025, C-026."""

    # G-001…G-012
    def apply(self, document: PdfDocument, options: SecurityOptions) -> None:
        """Protectia se scrie la urmatoarea salvare (peste fisier sau `Save As`)."""
        document._security = options.encryption_object()
        document._security_password = options.open_password or options.permissions_password
        document.is_modified = True
        document._revision += 1

    def remove_protection(self, document: PdfDocument, password: str) -> None:
        """Fara protectie la urmatoarea salvare; cere parola de permisiuni (sau,
        pe un fisier fara ea, parola de deschidere). Parola gresita →
        `WrongPasswordError`."""
        if document.path is None or not document.is_encrypted:
            document._security = False
            document.is_modified = True
            return
        try:
            with pikepdf.open(document.path, password=password) as pdf:
                owner = pdf.owner_password_matched
        except pikepdf.PasswordError as exc:
            raise WrongPasswordError("parola nu e corecta", path=str(document.path)) from exc
        if not owner:
            raise WrongPasswordError("e nevoie de parola de permisiuni",
                                     path=str(document.path))
        document._security = False
        document._security_password = None
        document.is_modified = True
        document._revision += 1

    # G-022…G-024, G-111
    def delete_objects_and_data(self, document: PdfDocument, *,
                                hidden_text_and_objects: bool = False,
                                comments_and_markup: bool = False,
                                links_media_actions_scripts_form_data: bool = False,
                                bookmarks: bool = False, attachments: bool = False,
                                metadata: bool = False) -> dict[str, int]:
        """Obiectele alese dispar. `hidden_text_and_objects` **converteste
        documentul in PDF imagine** (G-024); apelantul avertizeaza intai.
        Intoarce cate obiecte s-au sters, pe categorii."""
        from app.core.pdf import cleanup

        pdf = document._pike()
        counts: dict[str, int] = {}
        if comments_and_markup:
            counts["comments"] = cleanup.remove_comments(pdf)
        if links_media_actions_scripts_form_data:
            counts["links"] = cleanup.remove_links_actions_forms(pdf)
        if bookmarks:
            counts["bookmarks"] = cleanup.remove_bookmarks(pdf)
        if attachments:
            counts["attachments"] = cleanup.remove_attachments(pdf)
        if metadata:
            counts["metadata"] = cleanup.remove_metadata(pdf)
        document._changed()
        if hidden_text_and_objects:
            counts["pages"] = cleanup.to_image_only(document)
            document._changed()
        document._ocr_layer.clear()
        return counts

    # G-020, G-021
    def redact_regions(self, document: PdfDocument, regions: Sequence[tuple[int, Rect]],
                       color: str = DEFAULT_REDACTION_COLOR, *,
                       words: Sequence[tuple[str, bool, bool]] = ()) -> None:
        """Continutul zonelor dispare din pagina si din stratul de text; zonele
        se acopera cu `color`, iar adnotarile care le ating se sterg. Dupa
        operatie textul se extrage din nou: daca mai apare ceva in zone (sau
        unul din `words`: text, majuscule, cuvant intreg), documentul revine la
        starea dinainte si se ridica `RedactionVerificationError`.
        `words` e adaugat fata de SPEC_05, pentru verificarea dupa cuvinte."""
        pages = _group(regions, document.page_count)
        if not pages:
            return
        snapshot = document._snapshot()
        try:
            for number, rects in pages.items():
                rebuild_page(document, number, [PageEdit(r, color) for r in rects],
                             remove_annotations=True)
            document._changed()
            for number, rects in pages.items():
                verify_removed(document, number, rects, words)
        except BaseException:
            document._restore(snapshot)
            raise

    # C-025, C-026
    def redact_by_keywords(self, document: PdfDocument, keywords: Sequence[str], *,
                           match_case: bool = False, whole_word: bool = False,
                           color: str = DEFAULT_REDACTION_COLOR) -> int:
        """Redacteaza toate aparitiile cuvintelor in textul paginilor si intoarce
        cate au fost. Verificarea G-021 cauta din nou fiecare cuvant."""
        hits: list[SearchHit] = []
        for keyword in keywords:
            hits += document.search(keyword, match_case=match_case, whole_word=whole_word,
                                    in_comments=False, in_bookmarks=False, in_metadata=False)
        words = [(k, match_case, whole_word) for k in keywords]
        return self.redact_hits(document, hits, color, words=words)

    # C-026, C-011: rezultatele selectate in panou
    def redact_hits(self, document: PdfDocument, hits: Sequence[SearchHit],
                    color: str = DEFAULT_REDACTION_COLOR, *,
                    words: Sequence[tuple[str, bool, bool]] = ()) -> int:
        """Redacteaza rezultatele alese din lista; cele din comentarii, semne de
        carte si metadate nu au zona in pagina si se sar. Intoarce numarul de
        rezultate redactate (doua cuvinte care gasesc acelasi loc conteaza o data)."""
        regions: list[tuple[int, Rect]] = []
        seen: set[tuple[int, int, int]] = set()
        for hit in hits:
            key = (hit.page, hit.start, hit.length)
            if hit.source != SOURCE_TEXT or not hit.rects or key in seen:
                continue
            seen.add(key)
            regions += [(hit.page, r) for r in hit.rects]
        if regions:
            self.redact_regions(document, regions, color, words=words)
        return len(seen)

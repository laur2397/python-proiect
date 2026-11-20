"""Exceptiile nucleului.

Implementeaza SPEC_05_api_core.py, sectiunea 2. Clasele si codurile sunt
copiate din contract; nu se redenumesc.

Fiecare exceptie poarta un cod stabil (`code`). Codul merge in jurnal, in
iesirea JSON a CLI-ului (U-023) si in planul de testare. Mesajul afisat
utilizatorului se construieste in GUI din cod + parametri, ca sa fie
traductibil (Y-013). `message` e doar pentru jurnal si depanare.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


# SPEC_05 sect. 2 — baza tuturor exceptiilor. U-023 (cod in JSON), Y-013
class CoreError(Exception):
    """Baza tuturor exceptiilor nucleului."""

    code: str = "CORE_ERROR"

    def __init__(self, message: str = "", **params: Any) -> None:
        self.message = message
        self._params: Mapping[str, Any] = MappingProxyType(dict(params))
        super().__init__(message or self.code)

    @property
    def params(self) -> Mapping[str, Any]:
        """Valorile pentru interpolat in mesajul tradus. Doar citire."""
        return self._params

    def __repr__(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in self._params.items())
        sep = ", " if args and self.message else ""
        msg = repr(self.message) if self.message else ""
        return f"{type(self).__name__}({msg}{sep}{args})"


# --- intrare / fisiere ---------------------------------------------------------

# A-012
class UnsupportedFormatError(CoreError):
    """A-012: fisierul nu e intr-un format acceptat. params: path, extension."""
    code = "UNSUPPORTED_FORMAT"


# A-010
class FileCorruptError(CoreError):
    """A-010: fisierul nu poate fi deschis. params: path, detail."""
    code = "FILE_CORRUPT"


# A-011
class PasswordRequiredError(CoreError):
    """A-011: documentul cere parola si nu s-a dat niciuna."""
    code = "PASSWORD_REQUIRED"


# A-011, U-027
class WrongPasswordError(CoreError):
    """A-011: parola nu e corecta. CLI: cod de ieșire 2 (U-027)."""
    code = "WRONG_PASSWORD"


# I-001
class FileLockedError(CoreError):
    """I-001: fisierul e deschis in alta aplicatie. params: path."""
    code = "FILE_LOCKED"


# E-034, S-020
class NoWritePermissionError(CoreError):
    """E-034, S-020. params: path."""
    code = "NO_WRITE_PERMISSION"


# Y-009, X-089
class DiskFullError(CoreError):
    """Y-009, X-089."""
    code = "DISK_FULL"


# --- proiect -------------------------------------------------------------------

# J-003
class InvalidProjectError(CoreError):
    """J-003: folderul nu e un proiect valid."""
    code = "INVALID_PROJECT"


# P-029, J-003
class ProjectVersionError(CoreError):
    """P-029, J-003: proiect dintr-o versiune mai noua. params: found, supported."""
    code = "PROJECT_VERSION"


# J-055. Docstring-ul din SPEC_05 trimite la E-009, J-012, care in SPEC_01/02 sunt alte cerinte
class LastPageError(CoreError):
    """E-009, J-012: documentul trebuie sa aiba cel putin o pagina."""
    code = "LAST_PAGE"


# --- zone ----------------------------------------------------------------------

# M-009
class AreaOverlapError(CoreError):
    """M-009: zonele nu se pot suprapune. params: area_id, other_id."""
    code = "AREA_OVERLAP"


# M-008. Docstring-ul din SPEC_05 trimite la M-007, care in SPEC_02 e alta cerinta
class AreaTooSmallError(CoreError):
    """M-007: sub 8x8 px. params: w, h, min_size."""
    code = "AREA_TOO_SMALL"


# M-016. Docstring-ul din SPEC_05 trimite la M-017, care in SPEC_02 e alta cerinta
class AreaOutOfBoundsError(CoreError):
    """M-017: zona nu poate ieși din imagine."""
    code = "AREA_OUT_OF_BOUNDS"


# M-013, M-031, M-042
class WrongAreaTypeError(CoreError):
    """M-013, M-031, M-042: operatia nu e permisa pe acest tip de zona.
    params: area_type, operation, allowed_types."""
    code = "WRONG_AREA_TYPE"


# M-043
class CellsNotRectangularError(CoreError):
    """M-043: selectia de celule de unit nu e dreptunghiulara."""
    code = "CELLS_NOT_RECTANGULAR"


# M-041
class TemplateSizeMismatchError(CoreError):
    """M-041: sablonul vine de la o pagina de alta dimensiune sau rezolutie.
    Nu e fatala: apelantul poate reporni cu scale=True."""
    code = "TEMPLATE_SIZE_MISMATCH"


# --- recunoastere --------------------------------------------------------------

# P-001
class NoLanguageSelectedError(CoreError):
    """P-001: minimum o limba."""
    code = "NO_LANGUAGE"


# Y-004
class LanguageModelMissingError(CoreError):
    """Y-004: modelul limbii nu e instalat. params: language_code, expected_path."""
    code = "LANGUAGE_MODEL_MISSING"


# U-027
class RecognitionFailedError(CoreError):
    """CLI: cod de ieșire 3 (U-027). params: page_number, detail."""
    code = "RECOGNITION_FAILED"


# R-007
class NoTextFoundError(CoreError):
    """R-007: documentul nu are text care sa poata fi comparat sau exportat."""
    code = "NO_TEXT_FOUND"


# P-023
class PatternLimitError(CoreError):
    """P-023: sablonul a atins 1000 de caractere."""
    code = "PATTERN_LIMIT"


# --- export --------------------------------------------------------------------

# Q-001, U-006
class IncompatibleLayoutError(CoreError):
    """Q-001, U-006: formatul nu e permis in modul de layout cerut.
    params: layout_mode, requested_format, allowed_formats."""
    code = "INCOMPATIBLE_LAYOUT"


# A-028, I-006
class PdfAEncryptionConflictError(CoreError):
    """A-028, I-006: PDF/A nu se combina cu protectia prin parola."""
    code = "PDFA_ENCRYPTION_CONFLICT"


# I-006
class PdfAComplianceError(CoreError):
    """I-006: fisierul rezultat nu respecta standardul. params: violations."""
    code = "PDFA_COMPLIANCE"


# Q-051
class PagesNotRecognizedError(CoreError):
    """Q-051: exista pagini invalidate dupa ultima modificare.
    Nu e fatala: se foloseste ca avertisment inainte de export.
    params: page_numbers."""
    code = "PAGES_NOT_RECOGNIZED"


# --- securitate ----------------------------------------------------------------

# G-002
class SamePasswordError(CoreError):
    """G-002: parola de permisiuni trebuie sa fie diferita de cea de deschidere."""
    code = "SAME_PASSWORD"


# G-010
class NoCertificateError(CoreError):
    """G-010: nu exista un certificat cu cheie privata."""
    code = "NO_CERTIFICATE"


# G-024
class CertificateNotOwnedError(CoreError):
    """G-024: semnatura nu se poate sterge fara certificatul cu care a fost facuta."""
    code = "CERTIFICATE_NOT_OWNED"


# G-037
class TimestampUnavailableError(CoreError):
    """G-037: serverul de marca temporala nu raspunde. Apelantul decide dacă
    semneaza fara marca temporala."""
    code = "TIMESTAMP_UNAVAILABLE"


# G-021
class RedactionVerificationError(CoreError):
    """G-021: textul redactat se mai gaseste in document dupa operatie.
    Aceasta e un defect al implementarii, nu o eroare de utilizare:
    operatia se anuleaza si se raporteaza. params: page_number, found_text."""
    code = "REDACTION_VERIFICATION_FAILED"


# --- formulare -----------------------------------------------------------------

# H-013
class DuplicateFieldNameError(CoreError):
    """H-013: numele campului trebuie sa fie unic."""
    code = "DUPLICATE_FIELD_NAME"


# H-013
class InvalidFieldNameError(CoreError):
    """H-013: punct la inceput, la sfarsit sau dublat."""
    code = "INVALID_FIELD_NAME"


# H-040
class SignedFieldCopyError(CoreError):
    """H-040: doar campurile de semnatura goale se pot copia."""
    code = "SIGNED_FIELD_COPY"


# H-013
class OrphanRadioButtonError(CoreError):
    """H-013: un grup de butoane radio are nevoie de minimum doua butoane."""
    code = "ORPHAN_RADIO_BUTTON"


# --- scanare / automatizare ----------------------------------------------------

# A-040, K-004
class NoScannerError(CoreError):
    """A-040, K-004: niciun dispozitiv de scanare selectat."""
    code = "NO_SCANNER"


# K-013
class ScannerError(CoreError):
    """K-013: hartie blocata, alimentator gol, driver cazut. params: detail."""
    code = "SCANNER_ERROR"


# T-012
class TaskValidationError(CoreError):
    """T-012: pasii sarcinii nu sunt coerenti. params: step_index, reason."""
    code = "TASK_VALIDATION"


# T-002
class BuiltinNotEditableError(CoreError):
    """T-002: sarcinile si limbile livrate nu se modifica."""
    code = "BUILTIN_NOT_EDITABLE"


# X-085, T-015
class ShortcutConflictError(CoreError):
    """X-085, T-015. params: shortcut, existing_command."""
    code = "SHORTCUT_CONFLICT"


# U-027 (cod de iesire 5)
class OperationCancelledError(CoreError):
    """Aruncata cand `CancelToken` intoarce True.
    CLI: cod de ieșire 5 (U-027)."""
    code = "CANCELLED"


# Y-001
class NetworkAccessAttemptedError(CoreError):
    """Y-001. Nucleul nu face cereri de retea. Daca o componenta terta incearca,
    stratul de izolare arunca aceasta excepție, ca sa se vada la testare."""
    code = "NETWORK_ACCESS_ATTEMPTED"
